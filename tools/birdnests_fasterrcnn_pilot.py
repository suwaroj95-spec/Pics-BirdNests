from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPLIT_CSV = PROJECT_ROOT / "tmp" / "dataset_split" / "model_v1_constrained_20260707_001" / "final_ground_truth_with_split.csv"
DEFAULT_AUTHORITY_CSV = PROJECT_ROOT / "artifacts" / "model_v1_release" / "consolidated_240_20260707" / "consolidated_final_ground_truth_manifest.csv"
DEFAULT_SCOPED_MANIFEST_DIR = PROJECT_ROOT / "tmp" / "fasterrcnn_scoped_manifests" / "model_v1_constrained_20260707_001"
SCOPED_MANIFEST_FIELDS = ["source_id", "dataset_split", "original_image_path", "spot_id", "x_center", "y_center", "raw_radius"]
SEED = 20260710
TILE_SIZE = 512
TILE_OVERLAP = 128
TILE_STRIDE = TILE_SIZE - TILE_OVERLAP
NMS_IOU = 0.30
THRESHOLDS = [0.20, 0.30, 0.40, 0.50, 0.60]
NUM_CLASSES = 2
V1_2_VALIDATION_RECALL = 0.1041445271
V1_2_VALIDATION_EXTRAS_PER_MATCHED = 13.39


class PilotError(RuntimeError):
    pass


@dataclass(frozen=True)
class Spot:
    source_id: str
    dataset_split: str
    original_image_path: str
    spot_id: str
    x_center: float
    y_center: float
    raw_radius: float


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class Tile:
    tile_id: str
    source_id: str
    dataset_split: str
    original_image_path: str
    x_offset: int
    y_offset: int
    width: int
    height: int
    contained_spot_ids: tuple[str, ...]
    raw_only_confirmation: str = "RAW_IMAGE_PIXELS_ONLY"


@dataclass(frozen=True)
class Prediction:
    prediction_id: str
    source_id: str
    score: float
    box: Box
    tile_ids: tuple[str, ...]


def numeric_sort_key(value: str) -> tuple[int, str]:
    text = str(value)
    try:
        return (0, f"{int(text):012d}")
    except ValueError:
        return (1, text)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_scoped_manifests(split_csv: Path, authority_csv: Path, output_dir: Path) -> dict[str, Any]:
    split_csv, authority_csv, output_dir = split_csv.resolve(), authority_csv.resolve(), output_dir.resolve()
    train_path, validation_path, summary_path = output_dir / "train_spots.csv", output_dir / "validation_spots.csv", output_dir / "preparation_summary.json"
    existing = [path for path in (train_path, validation_path, summary_path) if path.exists()]
    if existing:
        raise PilotError(f"Refusing to overwrite immutable scoped-manifest artifacts: {', '.join(str(path) for path in existing)}")
    if not split_csv.is_file() or not authority_csv.is_file():
        raise PilotError("Authoritative split and Ground Truth manifests must both exist")
    split_rows, authority_rows = read_csv(split_csv), read_csv(authority_csv)
    authority = {(row["source_id"], row["spot_id"]): row for row in authority_rows}
    scoped: dict[str, list[dict[str, Any]]] = {"train": [], "validation": []}
    seen: set[tuple[str, str]] = set()
    coordinate_radius_mismatch_count = annotation_identity_mismatch_count = 0
    for row in split_rows:
        dataset_split = row["dataset_split"]
        if dataset_split not in scoped:
            continue
        key = (row["image_id"], row["spot_id"])
        if key in seen:
            raise PilotError(f"Duplicate scoped annotation identity: {key}")
        seen.add(key)
        auth = authority.get(key)
        if auth is None:
            annotation_identity_mismatch_count += 1; continue
        if abs(float(row["enclosing_circle_radius"]) - float(auth["raw_radius"])) > 1e-3:
            coordinate_radius_mismatch_count += 1; continue
        scoped[dataset_split].append({"source_id": row["image_id"], "dataset_split": dataset_split, "original_image_path": row["source_image"], "spot_id": row["spot_id"], "x_center": auth["center_x"], "y_center": auth["center_y"], "raw_radius": auth["raw_radius"]})
    if coordinate_radius_mismatch_count or annotation_identity_mismatch_count:
        raise PilotError(f"Scoped preparation reconciliation failed: coordinate_radius_mismatch={coordinate_radius_mismatch_count} annotation_identity_mismatch={annotation_identity_mismatch_count}")
    for rows in scoped.values(): rows.sort(key=lambda row: (numeric_sort_key(str(row["source_id"])), str(row["spot_id"])))
    train_sources = {str(row["source_id"]) for row in scoped["train"]}; validation_sources = {str(row["source_id"]) for row in scoped["validation"]}
    overlap = train_sources & validation_sources
    if overlap: raise PilotError(f"Train/validation source overlap in authoritative manifests: {sorted(overlap, key=numeric_sort_key)}")
    write_csv(train_path, SCOPED_MANIFEST_FIELDS, scoped["train"]); write_csv(validation_path, SCOPED_MANIFEST_FIELDS, scoped["validation"])
    summary = {"schema_version": 1, "mode": "non_model_scoped_manifest_preparation", "source_manifests": [{"path": str(split_csv), "sha256": sha256_file(split_csv)}, {"path": str(authority_csv), "sha256": sha256_file(authority_csv)}], "outputs": {"train": {"path": str(train_path), "sha256": sha256_file(train_path), "source_count": len(train_sources), "gt_count": len(scoped["train"]), "source_ids": sorted(train_sources, key=numeric_sort_key)}, "validation": {"path": str(validation_path), "sha256": sha256_file(validation_path), "source_count": len(validation_sources), "gt_count": len(scoped["validation"]), "source_ids": sorted(validation_sources, key=numeric_sort_key)}}, "train_validation_source_overlap_count": 0, "test_rows_written": 0, "coordinate_radius_mismatch_count": 0, "annotation_identity_mismatch_count": 0, "raw_images_opened": 0, "model_operations_run": 0}
    write_json(summary_path, summary)
    return summary


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def circle_to_box(x_center: float, y_center: float, raw_radius: float, image_width: int, image_height: int) -> Box:
    x1 = clamp(x_center - raw_radius, 0.0, float(image_width))
    y1 = clamp(y_center - raw_radius, 0.0, float(image_height))
    x2 = clamp(x_center + raw_radius, 0.0, float(image_width))
    y2 = clamp(y_center + raw_radius, 0.0, float(image_height))
    if x2 <= x1 or y2 <= y1:
        raise PilotError(f"Zero-area GT box from center=({x_center},{y_center}) radius={raw_radius} image={image_width}x{image_height}")
    return Box(x1, y1, x2, y2)


def tile_positions(length: int, tile_size: int = TILE_SIZE, overlap: int = TILE_OVERLAP) -> list[int]:
    if length <= 0:
        raise PilotError("Image dimension must be positive")
    if length <= tile_size:
        return [0]
    stride = tile_size - overlap
    starts = list(range(0, max(length - tile_size, 0) + 1, stride))
    edge = length - tile_size
    if starts[-1] != edge:
        starts.append(edge)
    return sorted(set(starts))


def generate_tiles_for_source(source_id: str, split: str, image_path: str, image_width: int, image_height: int, spots: list[Spot]) -> list[Tile]:
    tiles: list[Tile] = []
    for y in tile_positions(image_height):
        for x in tile_positions(image_width):
            w = min(TILE_SIZE, image_width - x)
            h = min(TILE_SIZE, image_height - y)
            contained = tuple(
                spot.spot_id
                for spot in sorted(spots, key=lambda item: item.spot_id)
                if x <= spot.x_center < x + w and y <= spot.y_center < y + h
            )
            tile_id = f"{source_id}__x{x:05d}_y{y:05d}"
            tiles.append(Tile(tile_id, source_id, split, image_path, x, y, w, h, contained))
    return tiles


def validate_split_isolation(tiles: list[Tile]) -> int:
    splits_by_source: dict[str, set[str]] = defaultdict(set)
    for tile in tiles:
        splits_by_source[tile.source_id].add(tile.dataset_split)
    return sum(1 for splits in splits_by_source.values() if len(splits) != 1)


def reconcile_gt_to_tiles(spots: list[Spot], tiles: list[Tile]) -> tuple[int, dict[str, int]]:
    counts = Counter(spot_id for tile in tiles for spot_id in tile.contained_spot_ids)
    missing = [spot.spot_id for spot in spots if counts[spot.spot_id] == 0]
    return len(missing), dict(counts)


def tile_box_to_original(box: Box, tile: Tile) -> Box:
    return Box(box.x1 + tile.x_offset, box.y1 + tile.y_offset, box.x2 + tile.x_offset, box.y2 + tile.y_offset)


def box_center(box: Box) -> tuple[float, float]:
    return ((box.x1 + box.x2) / 2.0, (box.y1 + box.y2) / 2.0)


def merge_duplicate_predictions(predictions: list[Prediction], iou_threshold: float = NMS_IOU) -> list[Prediction]:
    if not predictions:
        return []
    import torch
    from torchvision.ops import nms

    boxes = torch.tensor([[p.box.x1, p.box.y1, p.box.x2, p.box.y2] for p in predictions], dtype=torch.float32)
    scores = torch.tensor([p.score for p in predictions], dtype=torch.float32)
    keep = nms(boxes, scores, iou_threshold).tolist()
    merged: list[Prediction] = []
    for out_index, source_index in enumerate(keep, start=1):
        kept = predictions[source_index]
        overlaps = []
        for index, pred in enumerate(predictions):
            if index == source_index:
                continue
            if box_iou(kept.box, pred.box) > iou_threshold:
                overlaps.extend(pred.tile_ids)
        tile_ids = tuple(sorted(set(kept.tile_ids + tuple(overlaps))))
        merged.append(Prediction(f"{kept.source_id}_pred_{out_index:05d}", kept.source_id, kept.score, kept.box, tile_ids))
    return merged


def box_iou(a: Box, b: Box) -> float:
    ix1, iy1 = max(a.x1, b.x1), max(a.y1, b.y1)
    ix2, iy2 = min(a.x2, b.x2), min(a.y2, b.y2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, a.x2 - a.x1) * max(0.0, a.y2 - a.y1)
    area_b = max(0.0, b.x2 - b.x1) * max(0.0, b.y2 - b.y1)
    union = area_a + area_b - inter
    return 0.0 if union <= 0 else inter / union


def match_predictions_to_gt(spots: list[Spot], predictions: list[Prediction]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[tuple[float, str, str, Spot, Prediction]] = []
    for spot in spots:
        for pred in predictions:
            px, py = box_center(pred.box)
            distance = math.hypot(px - spot.x_center, py - spot.y_center)
            if distance <= max(12.0, spot.raw_radius):
                candidates.append((distance, spot.spot_id, pred.prediction_id, spot, pred))
    matched_gt: set[str] = set()
    matched_pred: set[str] = set()
    gt_rows: list[dict[str, Any]] = []
    pred_rows: list[dict[str, Any]] = []
    pred_match_by_id: dict[str, tuple[Spot, float]] = {}
    for distance, _spot_id, _pred_id, spot, pred in sorted(candidates, key=lambda item: (item[0], item[1], item[2])):
        if spot.spot_id in matched_gt or pred.prediction_id in matched_pred:
            continue
        matched_gt.add(spot.spot_id)
        matched_pred.add(pred.prediction_id)
        pred_match_by_id[pred.prediction_id] = (spot, distance)
        gt_rows.append(
            {
                "source_id": spot.source_id,
                "spot_id": spot.spot_id,
                "classification": "MATCHED_GROUND_TRUTH",
                "matched_prediction_id": pred.prediction_id,
                "match_distance": f"{distance:.6f}",
            }
        )
    for spot in sorted(spots, key=lambda item: (numeric_sort_key(item.source_id), item.spot_id)):
        if spot.spot_id not in matched_gt:
            gt_rows.append(
                {
                    "source_id": spot.source_id,
                    "spot_id": spot.spot_id,
                    "classification": "MISSED_GROUND_TRUTH",
                    "matched_prediction_id": "",
                    "match_distance": "",
                }
            )
    for pred in sorted(predictions, key=lambda item: (numeric_sort_key(item.source_id), -item.score, item.prediction_id)):
        if pred.prediction_id in pred_match_by_id:
            spot, distance = pred_match_by_id[pred.prediction_id]
            classification = "MATCHED_PREDICTION"
            spot_id = spot.spot_id
            match_distance = f"{distance:.6f}"
        else:
            classification = "UNVERIFIED_EXTRA_PREDICTION"
            spot_id = ""
            match_distance = ""
        pred_rows.append(
            {
                "source_id": pred.source_id,
                "prediction_id": pred.prediction_id,
                "classification": classification,
                "matched_spot_id": spot_id,
                "match_distance": match_distance,
                "score": f"{pred.score:.6f}",
                "x1": f"{pred.box.x1:.3f}",
                "y1": f"{pred.box.y1:.3f}",
                "x2": f"{pred.box.x2:.3f}",
                "y2": f"{pred.box.y2:.3f}",
                "tile_ids": ";".join(pred.tile_ids),
            }
        )
    return gt_rows, pred_rows


def select_threshold(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [row for row in metrics if int(row["reconciliation_mismatch_count"]) == 0 and int(row["tile_source_lineage_mismatch_count"]) == 0]
    candidates = valid or metrics
    return sorted(
        candidates,
        key=lambda row: (
            -float(row["spot_recall"]),
            float(row["extras_per_matched_prediction"]) if row["extras_per_matched_prediction"] != "inf" else float("inf"),
            int(row["total_predictions"]),
            float(row["threshold"]),
        ),
    )[0]


def load_spots(split_csv: Path, authority_csv: Path) -> list[Spot]:
    rows = read_csv(split_csv)
    authority_rows = read_csv(authority_csv)
    authority = {(row["source_id"], row["spot_id"]): row for row in authority_rows}
    spots: list[Spot] = []
    for row in rows:
        key = (row["image_id"], row["spot_id"])
        if key not in authority:
            raise PilotError(f"Split GT missing from authoritative manifest: {key}")
        auth = authority[key]
        radius = float(auth["raw_radius"])
        if abs(float(row["enclosing_circle_radius"]) - radius) > 1e-3:
            raise PilotError(f"Raw radius mismatch for {key}")
        spots.append(
            Spot(
                source_id=row["image_id"],
                dataset_split=row["dataset_split"],
                original_image_path=row["source_image"],
                spot_id=row["spot_id"],
                x_center=float(auth["center_x"]),
                y_center=float(auth["center_y"]),
                raw_radius=radius,
            )
        )
    return spots


def load_scoped_spots(path: Path, expected_split: str, opened_manifest_paths: list[str] | None = None) -> list[Spot]:
    if expected_split not in {"train", "validation"}: raise PilotError(f"Strict scoped loading does not permit split: {expected_split}")
    path = path.resolve()
    if not path.is_file(): raise PilotError(f"Missing required {expected_split} scoped manifest: {path}")
    if opened_manifest_paths is not None: opened_manifest_paths.append(str(path))
    rows = read_csv(path)
    if not rows: raise PilotError(f"Empty {expected_split} scoped manifest: {path}")
    missing_fields = set(SCOPED_MANIFEST_FIELDS) - set(rows[0])
    if missing_fields: raise PilotError(f"Scoped manifest missing required fields: {sorted(missing_fields)}")
    spots: list[Spot] = []; identities: set[tuple[str, str]] = set()
    for row in rows:
        dataset_split = row["dataset_split"]
        if dataset_split != expected_split: raise PilotError(f"Scoped {expected_split} manifest contains unexpected split: {dataset_split}")
        source_id, spot_id = row["source_id"], row["spot_id"]
        if not source_id or not spot_id or not row["original_image_path"]: raise PilotError("Scoped manifest contains an empty source, annotation identity, or image path")
        identity = (source_id, spot_id)
        if identity in identities: raise PilotError(f"Duplicate scoped annotation identity: {identity}")
        identities.add(identity)
        spots.append(Spot(source_id, dataset_split, row["original_image_path"], spot_id, float(row["x_center"]), float(row["y_center"]), float(row["raw_radius"])))
    return spots


def load_strict_spots(train_path: Path, validation_path: Path, opened_manifest_paths: list[str] | None = None) -> tuple[list[Spot], list[Spot]]:
    train_spots = load_scoped_spots(train_path, "train", opened_manifest_paths); validation_spots = load_scoped_spots(validation_path, "validation", opened_manifest_paths)
    overlap = {spot.source_id for spot in train_spots} & {spot.source_id for spot in validation_spots}
    if overlap: raise PilotError(f"Strict train/validation source overlap: {sorted(overlap, key=numeric_sort_key)}")
    return train_spots, validation_spots


def select_torch_device(torch_module: Any) -> Any:
    return torch_module.device("cuda" if torch_module.cuda.is_available() else "cpu")


def group_spots(spots: list[Spot]) -> dict[str, list[Spot]]:
    grouped: dict[str, list[Spot]] = defaultdict(list)
    for spot in spots:
        grouped[spot.source_id].append(spot)
    return grouped


def source_image_sizes(spots_by_source: dict[str, list[Spot]]) -> dict[str, tuple[int, int]]:
    sizes: dict[str, tuple[int, int]] = {}
    for source_id, source_spots in spots_by_source.items():
        path = PROJECT_ROOT / source_spots[0].original_image_path
        with Image.open(path) as image:
            sizes[source_id] = image.size
    return sizes


def build_tiles(spots: list[Spot], include_splits: set[str], train_empty_limit_per_source: int = 2) -> list[Tile]:
    spots_by_source = group_spots([spot for spot in spots if spot.dataset_split in include_splits])
    sizes = source_image_sizes(spots_by_source)
    selected: list[Tile] = []
    for source_id in sorted(spots_by_source, key=numeric_sort_key):
        source_spots = spots_by_source[source_id]
        split = source_spots[0].dataset_split
        if split == "test":
            raise PilotError("Refusing to load locked-test source")
        width, height = sizes[source_id]
        all_tiles = generate_tiles_for_source(source_id, split, source_spots[0].original_image_path, width, height, source_spots)
        if split == "train":
            gt_tiles = [tile for tile in all_tiles if tile.contained_spot_ids]
            empty_tiles = [tile for tile in all_tiles if not tile.contained_spot_ids][:train_empty_limit_per_source]
            selected.extend(gt_tiles + empty_tiles)
        else:
            selected.extend(all_tiles)
    return selected


def tile_lineage_rows(tiles: list[Tile]) -> list[dict[str, Any]]:
    return [
        {
            "tile_id": tile.tile_id,
            "source_id": tile.source_id,
            "dataset_split": tile.dataset_split,
            "original_image_path": tile.original_image_path,
            "tile_x_offset": tile.x_offset,
            "tile_y_offset": tile.y_offset,
            "tile_width": tile.width,
            "tile_height": tile.height,
            "contained_spot_ids": ";".join(tile.contained_spot_ids),
            "raw_only_confirmation": tile.raw_only_confirmation,
        }
        for tile in sorted(tiles, key=lambda item: (item.dataset_split, numeric_sort_key(item.source_id), item.tile_id))
    ]


class DetectionTileDataset:
    def __init__(self, tiles: list[Tile], spots_by_source: dict[str, list[Spot]]) -> None:
        self.tiles = tiles
        self.spots_by_source = spots_by_source

    def __len__(self) -> int:
        return len(self.tiles)

    def __getitem__(self, index: int) -> tuple[Any, dict[str, Any]]:
        import torch

        tile = self.tiles[index]
        image = Image.open(PROJECT_ROOT / tile.original_image_path).convert("RGB")
        crop = image.crop((tile.x_offset, tile.y_offset, tile.x_offset + tile.width, tile.y_offset + tile.height))
        array = np.asarray(crop, dtype=np.float32) / 255.0
        tensor = torch.from_numpy(array).permute(2, 0, 1)
        boxes: list[list[float]] = []
        labels: list[int] = []
        for spot in self.spots_by_source[tile.source_id]:
            if spot.spot_id not in tile.contained_spot_ids:
                continue
            full = circle_to_box(spot.x_center, spot.y_center, spot.raw_radius, image.width, image.height)
            clipped = Box(
                clamp(full.x1 - tile.x_offset, 0, tile.width),
                clamp(full.y1 - tile.y_offset, 0, tile.height),
                clamp(full.x2 - tile.x_offset, 0, tile.width),
                clamp(full.y2 - tile.y_offset, 0, tile.height),
            )
            if clipped.x2 > clipped.x1 and clipped.y2 > clipped.y1:
                boxes.append([clipped.x1, clipped.y1, clipped.x2, clipped.y2])
                labels.append(1)
        target = {
            "boxes": torch.tensor(boxes, dtype=torch.float32).reshape((-1, 4)),
            "labels": torch.tensor(labels, dtype=torch.int64),
            "image_id": torch.tensor([index], dtype=torch.int64),
            "area": torch.tensor([(b[2] - b[0]) * (b[3] - b[1]) for b in boxes], dtype=torch.float32),
            "iscrowd": torch.zeros((len(boxes),), dtype=torch.int64),
        }
        return tensor, target


def preflight(torch_home: Path) -> dict[str, Any]:
    torch_home.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TORCH_HOME", str(torch_home))
    import torch
    import torchvision
    from torchvision.models.detection import FasterRCNN_MobileNet_V3_Large_FPN_Weights, fasterrcnn_mobilenet_v3_large_fpn
    from torchvision.ops import nms

    keep = nms(torch.tensor([[0.0, 0.0, 10.0, 10.0], [1.0, 1.0, 11.0, 11.0]]), torch.tensor([0.9, 0.8]), 0.5)
    if keep.tolist() != [0]:
        raise PilotError("TorchVision NMS returned an unexpected result")
    weights = FasterRCNN_MobileNet_V3_Large_FPN_Weights.DEFAULT
    loaded = False
    load_error = ""
    try:
        _ = fasterrcnn_mobilenet_v3_large_fpn(weights=weights, weights_backbone=None)
        loaded = True
    except Exception as exc:
        load_error = f"{type(exc).__name__}: {exc}"
    return {
        "python": sys.version,
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "cuda_available": torch.cuda.is_available(),
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "pillow": Image.__version__,
        "torchvision_nms_verified": True,
        "pretrained_weight_identifier": str(weights),
        "pretrained_weight_url": weights.url,
        "pretrained_weights_loaded": loaded,
        "pretrained_load_error": load_error,
        "torch_home": str(torch_home),
    }


def build_model(weights_required: bool = True) -> Any:
    import torch
    from torchvision.models.detection import FasterRCNN_MobileNet_V3_Large_FPN_Weights, fasterrcnn_mobilenet_v3_large_fpn
    from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

    weights = FasterRCNN_MobileNet_V3_Large_FPN_Weights.DEFAULT
    try:
        model = fasterrcnn_mobilenet_v3_large_fpn(weights=weights, weights_backbone=None)
    except Exception as exc:
        if weights_required:
            raise PilotError(f"Official pretrained weights could not be loaded: {type(exc).__name__}: {exc}") from exc
        model = fasterrcnn_mobilenet_v3_large_fpn(weights=None, weights_backbone=None)
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, NUM_CLASSES)
    for parameter in model.backbone.parameters():
        parameter.requires_grad = False
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    if not trainable:
        raise PilotError("No trainable detection-head parameters found")
    return model


def save_checkpoint(path: Path, model: Any, optimizer: Any, epoch: int, config: dict[str, Any]) -> None:
    import torch

    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict(), "epoch": epoch, "config": config}, path)


def train(args: argparse.Namespace, training_dir: Path, spots: list[Spot], train_tiles: list[Tile], config: dict[str, Any]) -> dict[str, Any]:
    import torch
    from torch.utils.data import DataLoader

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    device = select_torch_device(torch)
    spots_by_source = group_spots(spots)
    dataset = DetectionTileDataset(train_tiles, spots_by_source)
    loader = DataLoader(dataset, batch_size=1, shuffle=True, num_workers=0, collate_fn=lambda batch: tuple(zip(*batch)))
    model = build_model(weights_required=True).to(device)
    optimizer = torch.optim.SGD([p for p in model.parameters() if p.requires_grad], lr=args.learning_rate, momentum=0.9, weight_decay=0.0005)
    initial = training_dir / "initial_checkpoint.pt"
    latest = training_dir / "latest_checkpoint.pt"
    final = training_dir / "final_checkpoint.pt"
    if not initial.exists():
        save_checkpoint(initial, model, optimizer, 0, config)
    loss_rows: list[dict[str, Any]] = []
    model.train()
    started = time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        total_loss = 0.0
        batches = 0
        for images, targets in loader:
            images = [image.to(device) for image in images]
            targets = [{key: value.to(device) for key, value in target.items()} for target in targets]
            losses = model(images, targets)
            loss = sum(value for value in losses.values())
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach().cpu())
            batches += 1
        row = {"epoch": epoch, "batches": batches, "total_loss": f"{total_loss:.6f}", "mean_loss": f"{(total_loss / max(1, batches)):.6f}"}
        loss_rows.append(row)
        save_checkpoint(latest, model, optimizer, epoch, config)
    save_checkpoint(final, model, optimizer, args.epochs, config)
    write_csv(training_dir / "epoch_loss.csv", ["epoch", "batches", "total_loss", "mean_loss"], loss_rows)
    hashes = {path.name: sha256_file(path) for path in [initial, latest, final] if path.exists()}
    write_json(training_dir / "checkpoint_hashes.json", hashes)
    return {"device": str(device), "runtime_seconds": round(time.perf_counter() - started, 3), "loss_rows": loss_rows, "checkpoint_hashes": hashes}


def load_final_model(checkpoint: Path) -> Any:
    import torch

    device = select_torch_device(torch)
    model = build_model(weights_required=True)
    payload = torch.load(checkpoint, map_location=device)
    model.load_state_dict(payload["model"])
    model.to(device)
    model.eval()
    return model


def infer_validation(model: Any, validation_tiles: list[Tile], thresholds: list[float]) -> tuple[dict[float, dict[str, list[Prediction]]], float]:
    import torch

    device = next(model.parameters()).device
    by_threshold: dict[float, dict[str, list[Prediction]]] = {threshold: defaultdict(list) for threshold in thresholds}
    started = time.perf_counter()
    with torch.no_grad():
        for tile in validation_tiles:
            image = Image.open(PROJECT_ROOT / tile.original_image_path).convert("RGB")
            crop = image.crop((tile.x_offset, tile.y_offset, tile.x_offset + tile.width, tile.y_offset + tile.height))
            array = np.asarray(crop, dtype=np.float32) / 255.0
            tensor = torch.from_numpy(array).permute(2, 0, 1).to(device)
            output = model([tensor])[0]
            boxes = output["boxes"].detach().cpu().numpy()
            scores = output["scores"].detach().cpu().numpy()
            labels = output["labels"].detach().cpu().numpy()
            for box_array, score, label in zip(boxes, scores, labels):
                if int(label) != 1:
                    continue
                original_box = tile_box_to_original(Box(float(box_array[0]), float(box_array[1]), float(box_array[2]), float(box_array[3])), tile)
                for threshold in thresholds:
                    if float(score) >= threshold:
                        pred = Prediction("", tile.source_id, float(score), original_box, (tile.tile_id,))
                        by_threshold[threshold][tile.source_id].append(pred)
    elapsed = time.perf_counter() - started
    merged_by_threshold: dict[float, dict[str, list[Prediction]]] = {}
    for threshold, by_source in by_threshold.items():
        merged_by_threshold[threshold] = {}
        for source_id, preds in by_source.items():
            ordered = sorted(preds, key=lambda item: (-item.score, item.tile_ids[0], item.box.x1, item.box.y1))
            merged = merge_duplicate_predictions(ordered, NMS_IOU)
            merged_by_threshold[threshold][source_id] = merged
    return merged_by_threshold, elapsed


def metrics_for_threshold(
    threshold: float,
    predictions_by_source: dict[str, list[Prediction]],
    validation_spots: list[Spot],
    validation_sources: list[str],
    inference_time: float,
    lineage_mismatch: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    all_predictions = [pred for source_id in validation_sources for pred in predictions_by_source.get(source_id, [])]
    gt_rows, pred_rows = match_predictions_to_gt(validation_spots, all_predictions)
    matched_gt = sum(1 for row in gt_rows if row["classification"] == "MATCHED_GROUND_TRUTH")
    missed_gt = len(validation_spots) - matched_gt
    matched_predictions = sum(1 for row in pred_rows if row["classification"] == "MATCHED_PREDICTION")
    extras = sum(1 for row in pred_rows if row["classification"] == "UNVERIFIED_EXTRA_PREDICTION")
    per_source_counts = [len(predictions_by_source.get(source_id, [])) for source_id in validation_sources]
    extras_per = "inf" if matched_predictions == 0 else f"{extras / matched_predictions:.6f}"
    row = {
        "threshold": f"{threshold:.2f}",
        "total_gt": len(validation_spots),
        "matched_gt": matched_gt,
        "missed_gt": missed_gt,
        "spot_recall": f"{matched_gt / max(1, len(validation_spots)):.10f}",
        "total_predictions": len(all_predictions),
        "matched_predictions": matched_predictions,
        "unverified_extras": extras,
        "extras_per_matched_prediction": extras_per,
        "predictions_per_source_min": min(per_source_counts) if per_source_counts else 0,
        "predictions_per_source_median": statistics.median(per_source_counts) if per_source_counts else 0,
        "predictions_per_source_max": max(per_source_counts) if per_source_counts else 0,
        "sources_with_zero_predictions": sum(1 for count in per_source_counts if count == 0),
        "reconciliation_mismatch_count": 0,
        "tile_source_lineage_mismatch_count": lineage_mismatch,
        "inference_time_seconds": f"{inference_time:.3f}",
    }
    source_rows = [
        {
            "source_id": source_id,
            "prediction_count": len(predictions_by_source.get(source_id, [])),
            "dataset_split": "validation",
        }
        for source_id in validation_sources
    ]
    return row, gt_rows, pred_rows, source_rows


def draw_contact_sheets(error_dir: Path, selected_gt: list[dict[str, Any]], selected_pred: list[dict[str, Any]], spots_by_id: dict[str, Spot]) -> None:
    samples = selected_gt[:8] + [row for row in selected_pred if row["classification"] == "UNVERIFIED_EXTRA_PREDICTION"][:8]
    if not samples:
        return
    page_dir = error_dir / "contact_sheets"
    page_dir.mkdir(parents=True, exist_ok=True)
    thumbs: list[Image.Image] = []
    for row in samples[:16]:
        source_id = row["source_id"]
        spot = spots_by_id.get(row.get("spot_id", "") or row.get("matched_spot_id", ""))
        image_path = PROJECT_ROOT / (spot.original_image_path if spot else next(s.original_image_path for s in spots_by_id.values() if s.source_id == source_id))
        image = Image.open(image_path).convert("RGB")
        if spot:
            cx, cy = spot.x_center, spot.y_center
        else:
            cx = (float(row["x1"]) + float(row["x2"])) / 2.0
            cy = (float(row["y1"]) + float(row["y2"])) / 2.0
        crop = image.crop((max(0, int(cx) - 96), max(0, int(cy) - 96), min(image.width, int(cx) + 96), min(image.height, int(cy) + 96))).resize((192, 192))
        draw = ImageDraw.Draw(crop)
        draw.rectangle((2, 2, 190, 190), outline=(255, 0, 0) if row["classification"].startswith("MISSED") else (0, 180, 0), width=3)
        thumbs.append(crop)
    sheet = Image.new("RGB", (4 * 192, math.ceil(len(thumbs) / 4) * 192), "white")
    for index, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((index % 4) * 192, (index // 4) * 192))
    sheet.save(page_dir / "page_001.png")


def classify_pilot(selected: dict[str, Any]) -> str:
    recall = float(selected["spot_recall"])
    extras = float("inf") if selected["extras_per_matched_prediction"] == "inf" else float(selected["extras_per_matched_prediction"])
    if recall >= 0.30 and recall > V1_2_VALIDATION_RECALL and extras <= 10 and int(selected["reconciliation_mismatch_count"]) == 0:
        return "FASTER_RCNN_PILOT_PROMISING"
    if recall > V1_2_VALIDATION_RECALL:
        return "FASTER_RCNN_PILOT_PARTIAL"
    return "FASTER_RCNN_PILOT_NOT_BETTER"


def run(args: argparse.Namespace) -> int:
    run_id = args.run_id or datetime.now().strftime("run_%Y%m%d_%H%M%S")
    training_dir = PROJECT_ROOT / "tmp" / "fasterrcnn_training" / run_id
    validation_dir = PROJECT_ROOT / "tmp" / "fasterrcnn_validation" / run_id
    cache_dir = PROJECT_ROOT / "tmp" / "fasterrcnn_prediction_cache" / run_id
    error_dir = PROJECT_ROOT / "tmp" / "fasterrcnn_error_analysis" / run_id
    torch_home = PROJECT_ROOT / "tmp" / "fasterrcnn_training" / run_id / "torch_home"
    for path in [training_dir, validation_dir, cache_dir, error_dir]:
        path.mkdir(parents=True, exist_ok=True)

    env = preflight(torch_home)
    if not env["pretrained_weights_loaded"]:
        write_json(training_dir / "training_summary.json", {"status": "FASTER_RCNN_PILOT_BLOCKED", "environment": env})
        raise PilotError(f"FASTER_RCNN_PILOT_BLOCKED: official pretrained weights failed to load: {env['pretrained_load_error']}")

    opened_manifest_paths: list[str] = []
    if args.train_scoped_manifest or args.validation_scoped_manifest:
        if not args.train_scoped_manifest or not args.validation_scoped_manifest:
            raise PilotError("Strict mode requires both --train-scoped-manifest and --validation-scoped-manifest; no legacy fallback is permitted")
        train_spots, validation_spots = load_strict_spots(Path(args.train_scoped_manifest), Path(args.validation_scoped_manifest), opened_manifest_paths)
        spots = train_spots + validation_spots
        manifest_provenance = {
            "mode": "strict_scoped_manifests",
            "legacy_complete_manifests_opened": False,
            "opened_manifest_paths": opened_manifest_paths,
            "train_source_ids": sorted({spot.source_id for spot in train_spots}, key=numeric_sort_key),
            "validation_source_ids": sorted({spot.source_id for spot in validation_spots}, key=numeric_sort_key),
            "train_gt_count": len(train_spots),
            "validation_gt_count": len(validation_spots),
        }
    else:
        spots = load_spots(DEFAULT_SPLIT_CSV, DEFAULT_AUTHORITY_CSV)
        train_spots = [spot for spot in spots if spot.dataset_split == "train"]
        validation_spots = [spot for spot in spots if spot.dataset_split == "validation"]
        manifest_provenance = {
            "mode": "legacy_non_strict",
            "legacy_complete_manifests_opened": True,
            "opened_manifest_paths": [str(DEFAULT_SPLIT_CSV.resolve()), str(DEFAULT_AUTHORITY_CSV.resolve())],
            "train_source_ids": sorted({spot.source_id for spot in train_spots}, key=numeric_sort_key),
            "validation_source_ids": sorted({spot.source_id for spot in validation_spots}, key=numeric_sort_key),
            "train_gt_count": len(train_spots),
            "validation_gt_count": len(validation_spots),
        }
    train_tiles = build_tiles(spots, {"train"}, args.empty_tiles_per_train_source)
    validation_tiles = build_tiles(spots, {"validation"}, args.empty_tiles_per_train_source)
    all_tiles = train_tiles + validation_tiles
    lineage_mismatch = validate_split_isolation(all_tiles)
    train_missing, duplication_counts = reconcile_gt_to_tiles(train_spots, train_tiles)
    validation_missing, _ = reconcile_gt_to_tiles(validation_spots, validation_tiles)
    if train_missing or validation_missing or lineage_mismatch:
        raise PilotError(f"Tile reconciliation failed: train_missing={train_missing} validation_missing={validation_missing} lineage_mismatch={lineage_mismatch}")

    write_csv(
        validation_dir / "tile_lineage.csv",
        ["tile_id", "source_id", "dataset_split", "original_image_path", "tile_x_offset", "tile_y_offset", "tile_width", "tile_height", "contained_spot_ids", "raw_only_confirmation"],
        tile_lineage_rows(all_tiles),
    )
    config = {
        "run_id": run_id,
        "seed": SEED,
        "tile_size": TILE_SIZE,
        "tile_overlap": TILE_OVERLAP,
        "batch_size": 1,
        "epochs": args.epochs,
        "num_classes": NUM_CLASSES,
        "nms_iou": NMS_IOU,
        "thresholds": THRESHOLDS,
        "backbone_frozen": True,
        "learning_rate": args.learning_rate,
        "empty_tiles_per_train_source": args.empty_tiles_per_train_source,
        "environment": env,
        "manifest_provenance": manifest_provenance,
    }
    write_json(training_dir / "training_config.json", config)
    write_csv(
        training_dir / "source_tile_counts.csv",
        ["dataset_split", "source_count", "tile_count", "gt_count"],
        [
            {"dataset_split": "train", "source_count": len({s.source_id for s in train_spots}), "tile_count": len(train_tiles), "gt_count": len(train_spots)},
            {"dataset_split": "validation", "source_count": len({s.source_id for s in validation_spots}), "tile_count": len(validation_tiles), "gt_count": len(validation_spots)},
        ],
    )
    train_summary = train(args, training_dir, train_spots, train_tiles, config)
    model = load_final_model(training_dir / "final_checkpoint.pt")
    predictions, inference_time = infer_validation(model, validation_tiles, THRESHOLDS)
    validation_sources = sorted({spot.source_id for spot in validation_spots}, key=numeric_sort_key)
    metric_rows: list[dict[str, Any]] = []
    threshold_payloads: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]] = {}
    for threshold in THRESHOLDS:
        metrics, gt_rows, pred_rows, source_rows = metrics_for_threshold(threshold, predictions[threshold], validation_spots, validation_sources, inference_time, lineage_mismatch)
        metric_rows.append(metrics)
        threshold_payloads[f"{threshold:.2f}"] = (gt_rows, pred_rows, source_rows)
    write_csv(validation_dir / "validation_metrics_by_threshold.csv", list(metric_rows[0].keys()), metric_rows)
    selected = select_threshold(metric_rows)
    selected_key = selected["threshold"]
    selected_gt, selected_pred, selected_source_rows = threshold_payloads[selected_key]
    write_json(validation_dir / "selected_validation_operating_point.json", selected)
    write_csv(validation_dir / "validation_ground_truth_coverage.csv", ["source_id", "spot_id", "classification", "matched_prediction_id", "match_distance"], selected_gt)
    write_csv(validation_dir / "validation_missed_ground_truth.csv", ["source_id", "spot_id", "classification", "matched_prediction_id", "match_distance"], [row for row in selected_gt if row["classification"] == "MISSED_GROUND_TRUTH"])
    write_csv(validation_dir / "validation_unverified_extra_predictions.csv", ["source_id", "prediction_id", "classification", "matched_spot_id", "match_distance", "score", "x1", "y1", "x2", "y2", "tile_ids"], [row for row in selected_pred if row["classification"] == "UNVERIFIED_EXTRA_PREDICTION"])
    write_csv(validation_dir / "validation_predictions_by_source.csv", ["source_id", "prediction_count", "dataset_split"], selected_source_rows)
    write_json(cache_dir / "validation_prediction_cache_summary.json", {"thresholds": THRESHOLDS, "sources": len(validation_sources)})
    pilot_classification = classify_pilot(selected)
    training_summary = {
        "status": "completed",
        "run_id": run_id,
        "environment": env,
        "train_source_count": len({spot.source_id for spot in train_spots}),
        "validation_source_count": len(validation_sources),
        "train_tile_count": len(train_tiles),
        "validation_tile_count": len(validation_tiles),
        "train_gt_count": len(train_spots),
        "validation_gt_count": len(validation_spots),
        "gt_tile_duplication_min": min(duplication_counts.values()) if duplication_counts else 0,
        "gt_tile_duplication_max": max(duplication_counts.values()) if duplication_counts else 0,
        **train_summary,
    }
    write_json(training_dir / "training_summary.json", training_summary)
    pilot_summary = {
        "run_id": run_id,
        "classification": pilot_classification,
        "selected_validation_operating_point": selected,
        "v1_2_validation_recall": V1_2_VALIDATION_RECALL,
        "v1_2_validation_extras_per_matched": V1_2_VALIDATION_EXTRAS_PER_MATCHED,
        "locked_test_accessed": False,
    }
    write_json(validation_dir / "pilot_summary.json", pilot_summary)
    spots_by_id = {spot.spot_id: spot for spot in validation_spots}
    draw_contact_sheets(error_dir, [row for row in selected_gt if row["classification"] != "MATCHED_GROUND_TRUTH"], selected_pred, spots_by_id)
    report = [
        "# Faster R-CNN Validation Pilot",
        "",
        f"- Run ID: `{run_id}`",
        f"- Classification: `{pilot_classification}`",
        f"- Selected threshold: `{selected_key}`",
        f"- Validation recall: `{selected['spot_recall']}` versus V1.2 `{V1_2_VALIDATION_RECALL}`",
        f"- Extras per matched prediction: `{selected['extras_per_matched_prediction']}` versus V1.2 `{V1_2_VALIDATION_EXTRAS_PER_MATCHED}`",
        f"- Locked test accessed: `false`",
    ]
    (validation_dir / "pilot_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "classification": pilot_classification, "selected": selected, "training_dir": str(training_dir), "validation_dir": str(validation_dir)}, indent=2))
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-scoped-manifests", action="store_true")
    parser.add_argument("--split-manifest", default=str(DEFAULT_SPLIT_CSV))
    parser.add_argument("--authority-manifest", default=str(DEFAULT_AUTHORITY_CSV))
    parser.add_argument("--scoped-output-dir", default=str(DEFAULT_SCOPED_MANIFEST_DIR))
    parser.add_argument("--train-scoped-manifest", default="")
    parser.add_argument("--validation-scoped-manifest", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=0.005)
    parser.add_argument("--empty-tiles-per-train-source", type=int, default=2)
    args = parser.parse_args(argv)
    if args.epochs != 2:
        raise PilotError("This bounded pilot must train for exactly two epochs")
    return args


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(sys.argv[1:] if argv is None else argv)
        if args.prepare_scoped_manifests:
            if args.train_scoped_manifest or args.validation_scoped_manifest:
                raise PilotError("Preparation mode cannot be combined with experiment scoped-manifest arguments")
            summary = prepare_scoped_manifests(Path(args.split_manifest), Path(args.authority_manifest), Path(args.scoped_output_dir))
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0
        return run(args)
    except PilotError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
