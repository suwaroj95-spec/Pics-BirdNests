from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "handoff" / "prototype_v1" / "prototype_runtime_config.json"
ALLOWED_THRESHOLDS = {0.125, 0.175}
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
SCHEMA_VERSION = "birdnests.prototype.predictions.v1"


class InferenceCliError(RuntimeError):
    pass


def positive_threshold(value: str) -> float:
    try:
        threshold = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--threshold must be numeric") from exc
    if threshold not in ALLOWED_THRESHOLDS:
        allowed = ", ".join(f"{item:.3f}" for item in sorted(ALLOWED_THRESHOLDS))
        raise argparse.ArgumentTypeError(f"--threshold must be one of: {allowed}")
    return threshold


def device_option(value: str) -> str:
    normalized = value.lower()
    if normalized not in {"cpu", "cuda"}:
        raise argparse.ArgumentTypeError("--device must be cpu or cuda")
    return normalized


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the BirdNests frozen Faster R-CNN engineering Prototype on an image or directory.",
    )
    parser.add_argument("--input", required=True, help="Input image file or directory.")
    parser.add_argument("--output", required=True, help="Output directory.")
    parser.add_argument("--checkpoint", required=True, help="Frozen checkpoint path.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Runtime config JSON path.")
    parser.add_argument("--threshold", type=positive_threshold, default=0.125, help="Operating threshold: 0.125 or 0.175.")
    parser.add_argument("--device", type=device_option, default="cpu", help="cpu or cuda.")
    parser.add_argument("--save-json", default="predictions.json", help="Output JSON filename or path.")
    parser.add_argument("--save-preview", default="", help="Optional preview output directory.")
    return parser


def discover_inputs(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise InferenceCliError(f"Unsupported image suffix: {path.suffix}")
        return [path]
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES)
        if not files:
            raise InferenceCliError(f"No supported image files found in {path}")
        return files
    raise InferenceCliError(f"Input path does not exist: {path}")


def validate_existing_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise InferenceCliError(f"{label} does not exist or is not a regular file ({path})")
    return path


def validate_args(args: argparse.Namespace) -> dict[str, Any]:
    input_path = Path(args.input)
    output_dir = Path(args.output)
    checkpoint = validate_existing_file(Path(args.checkpoint), "checkpoint")
    config = validate_existing_file(Path(args.config), "config")
    inputs = discover_inputs(input_path)
    if args.save_json.lower().endswith((".png", ".jpg", ".jpeg")):
        raise InferenceCliError("--save-json must be a JSON path or filename")
    return {
        "input_path": input_path,
        "output_dir": output_dir,
        "checkpoint": checkpoint,
        "config": config,
        "inputs": inputs,
        "threshold": float(args.threshold),
        "device": args.device,
        "save_json": args.save_json,
        "save_preview": args.save_preview,
    }


def output_json_path(output_dir: Path, save_json: str) -> Path:
    candidate = Path(save_json)
    if candidate.is_absolute():
        return candidate
    return output_dir / candidate


def sanitize_source_id(path: Path) -> str:
    return path.name


def make_empty_payload(config: dict[str, Any], checkpoint_sha256: str, source: Path, width: int, height: int, threshold: float, warnings: list[str]) -> dict[str, Any]:
    model = config.get("model", {})
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": model.get("prototype_status", "FASTER_RCNN_PILOT_PROMISING"),
        "checkpoint_sha256": checkpoint_sha256,
        "source_file": sanitize_source_id(source),
        "source_width": width,
        "source_height": height,
        "threshold": f"{threshold:.3f}",
        "coordinate_system": "pixel coordinates in original source image, origin at top-left",
        "predictions": [],
        "runtime_warnings": warnings,
    }


def draw_preview(source: Path, predictions: list[dict[str, Any]], preview_dir: Path, threshold: float) -> None:
    preview_dir.mkdir(parents=True, exist_ok=True)
    image = Image.open(source).convert("RGB")
    draw = ImageDraw.Draw(image)
    for pred in predictions:
        box = [pred["x1"], pred["y1"], pred["x2"], pred["y2"]]
        draw.rectangle(box, outline=(0, 190, 220), width=3)
        draw.text((pred["x1"], max(0, pred["y1"] - 14)), f"{pred['score']:.3f} @ {threshold:.3f}", fill=(0, 120, 150))
    draw.text((12, 12), "Engineering Prototype - no Ground Truth assumption", fill=(0, 120, 150))
    image.save(preview_dir / f"{source.stem}_prototype_preview.jpg", quality=92)


def load_checkpoint_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_inference(validated: dict[str, Any]) -> dict[str, Any]:
    import numpy as np
    import torch

    from tools.birdnests_fasterrcnn_pilot import (
        Box,
        Prediction,
        build_model,
        merge_duplicate_predictions,
        tile_box_to_original,
        tile_positions,
    )

    if validated["device"] == "cuda" and not torch.cuda.is_available():
        raise InferenceCliError("CUDA was requested but torch.cuda.is_available() is false")
    device = torch.device(validated["device"])
    config = json.loads(validated["config"].read_text(encoding="utf-8"))
    checkpoint_sha256 = load_checkpoint_sha256(validated["checkpoint"])
    model = build_model(weights_required=False)
    payload = torch.load(validated["checkpoint"], map_location=device)
    if "model" not in payload:
        raise InferenceCliError("Checkpoint payload does not contain a 'model' state dictionary")
    model.load_state_dict(payload["model"])
    model.to(device)
    model.eval()

    tile_settings = config.get("tile_settings", {})
    tile_size = int(tile_settings.get("tile_size", 512))
    tile_overlap = int(tile_settings.get("tile_overlap", 128))
    nms_iou = float(config.get("merge_settings", {}).get("cross_tile_merge_nms_iou", 0.3))
    threshold = float(validated["threshold"])
    all_outputs = []

    with torch.no_grad():
        for source in validated["inputs"]:
            image = Image.open(source).convert("RGB")
            width, height = image.size
            raw_predictions: list[Prediction] = []
            for y in tile_positions(height, tile_size, tile_overlap):
                for x in tile_positions(width, tile_size, tile_overlap):
                    crop_width = min(tile_size, width - x)
                    crop_height = min(tile_size, height - y)
                    crop = image.crop((x, y, x + crop_width, y + crop_height))
                    array = np.asarray(crop, dtype=np.float32) / 255.0
                    tensor = torch.from_numpy(array).permute(2, 0, 1).to(device)
                    output = model([tensor])[0]
                    boxes = output["boxes"].detach().cpu().numpy()
                    scores = output["scores"].detach().cpu().numpy()
                    labels = output["labels"].detach().cpu().numpy()
                    tile = type("TileRef", (), {"x_offset": x, "y_offset": y})()
                    tile_id = f"{source.stem}__x{x:05d}_y{y:05d}"
                    for box_array, score, label in zip(boxes, scores, labels):
                        if int(label) != 1 or float(score) < threshold:
                            continue
                        original_box = tile_box_to_original(Box(float(box_array[0]), float(box_array[1]), float(box_array[2]), float(box_array[3])), tile)
                        raw_predictions.append(Prediction("", sanitize_source_id(source), float(score), original_box, (tile_id,)))
            merged = merge_duplicate_predictions(sorted(raw_predictions, key=lambda item: (-item.score, item.tile_ids[0])), nms_iou)
            payload_item = make_empty_payload(config, checkpoint_sha256, source, width, height, threshold, [])
            for index, pred in enumerate(merged, start=1):
                center_x = (pred.box.x1 + pred.box.x2) / 2.0
                center_y = (pred.box.y1 + pred.box.y2) / 2.0
                payload_item["predictions"].append({
                    "prediction_id": f"{source.stem}_pred_{index:05d}",
                    "score": round(float(pred.score), 6),
                    "x1": round(float(pred.box.x1), 3),
                    "y1": round(float(pred.box.y1), 3),
                    "x2": round(float(pred.box.x2), 3),
                    "y2": round(float(pred.box.y2), 3),
                    "center_x": round(center_x, 3),
                    "center_y": round(center_y, 3),
                })
            if validated["save_preview"]:
                draw_preview(source, payload_item["predictions"], validated["output_dir"] / validated["save_preview"], threshold)
            all_outputs.append(payload_item)
    return {
        "schema_version": SCHEMA_VERSION,
        "runtime_disclaimer": "Engineering Prototype output. No Ground Truth or expert-confirmed assumption is made.",
        "sources": all_outputs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validated = validate_args(args)
        validated["output_dir"].mkdir(parents=True, exist_ok=True)
        payload = run_inference(validated)
        json_path = output_json_path(validated["output_dir"], validated["save_json"])
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "PROTOTYPE_INFERENCE_COMPLETE", "output_json": str(json_path)}, indent=2))
        return 0
    except InferenceCliError as exc:
        print(f"PROTOTYPE_INFERENCE_FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
