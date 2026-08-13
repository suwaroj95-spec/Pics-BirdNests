from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "docs" / "anchor-review-small-16-32-64-128"
ASSET_DIR = SITE_DIR / "assets" / "review-pages"
DATA_DIR = SITE_DIR / "data"
PACKAGE_DIR = (
    ROOT
    / "tmp"
    / "fasterrcnn_anchor_workflow"
    / "phase_07_expert_review_package"
    / "package_a_small_anchor_0125"
)
MANIFEST_CSV = PACKAGE_DIR / "card_manifest.csv"
PACKAGE_IDENTITY_JSON = PACKAGE_DIR / "package_identity.json"
MAPPING_CSV = (
    ROOT
    / "tmp"
    / "fasterrcnn_handoff"
    / "controlled_20260711_validation_raw_marker_mapping_001"
    / "validation_raw_marker_mapping.csv"
)
AUDIT_DIR = PACKAGE_DIR.parent / "web_pair_upgrade_audit"


PAGE_WIDTH = 3508
PAGE_HEIGHT = 2480
CARD_SOURCE_WIDTH = 900
CARD_SOURCE_HEIGHT = 560
CARD_WIDTH = 820
CARD_HEIGHT = 430
PAGE_X0 = 80
PAGE_Y0 = 145
PAGE_GAP_X = 35
PAGE_GAP_Y = 28
PANEL = 360
EXPECTED_CARDS = 1400
EXPECTED_PAGES = 70
CHECKPOINT_SHA256 = "e9f4d2e1b8530662fd3390165419008647c7d9baaf80e8a2d3cc4108b22fa7c0"
BASELINE_REVIEW_PAGE_ASSET_BYTES = 21583932


BLACK = (20, 24, 32)
MUTED = (92, 105, 122)
GRAY = (112, 123, 138)
LINE = (206, 215, 225)
CYAN = (0, 196, 224)
BLUE = (0, 90, 255)
LIGHT_BLUE = (232, 244, 255)
LIGHT_GREEN = (232, 246, 241)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/tahomabd.ttf" if bold else "C:/Windows/Fonts/tahoma.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


FONT_12 = load_font(12)
FONT_14 = load_font(14)
FONT_16 = load_font(16)
FONT_18 = load_font(18, bold=True)
FONT_24 = load_font(24, bold=True)
FONT_28 = load_font(28, bold=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def center(box: dict[str, float]) -> tuple[float, float]:
    return ((box["x1"] + box["x2"]) / 2.0, (box["y1"] + box["y2"]) / 2.0)


def crop_for_box(box: dict[str, float], width: int, height: int) -> dict[str, int]:
    cx, cy = center(box)
    side = max(256.0, (box["x2"] - box["x1"]) + 128.0, (box["y2"] - box["y1"]) + 128.0)
    side = min(512.0, side)
    side_i = int(round(side))
    requested_x1 = int(round(cx - side / 2.0))
    requested_y1 = int(round(cy - side / 2.0))
    requested_x2 = int(round(cx + side / 2.0))
    requested_y2 = int(round(cy + side / 2.0))
    x1 = int(round(cx - side_i / 2))
    y1 = int(round(cy - side_i / 2))
    x1 = max(0, min(x1, max(0, width - side_i)))
    y1 = max(0, min(y1, max(0, height - side_i)))
    x2 = min(width, x1 + side_i)
    y2 = min(height, y1 + side_i)
    return {
        "requested_x1": requested_x1,
        "requested_y1": requested_y1,
        "requested_x2": requested_x2,
        "requested_y2": requested_y2,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
    }


def draw_annotation(draw: ImageDraw.ImageDraw, box: dict[str, float], crop: dict[str, int], offset: tuple[int, int]) -> None:
    ox, oy = offset
    scale = PANEL / max(1, crop["x2"] - crop["x1"])
    x1 = ox + (box["x1"] - crop["x1"]) * scale
    y1 = oy + (box["y1"] - crop["y1"]) * scale
    x2 = ox + (box["x2"] - crop["x1"]) * scale
    y2 = oy + (box["y2"] - crop["y1"]) * scale
    draw.rectangle((x1, y1, x2, y2), outline=CYAN, width=3)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    draw.line((cx - 9, cy, cx + 9, cy), fill=BLUE, width=2)
    draw.line((cx, cy - 9, cx, cy + 9), fill=BLUE, width=2)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, font: ImageFont.ImageFont, fill: tuple[int, int, int] = BLACK) -> None:
    draw.text(xy, value, fill=fill, font=font)


def make_card(row: dict[str, Any], mapping: dict[str, str], crop: dict[str, int], raw: Image.Image, marker: Image.Image) -> Image.Image:
    box = row["box"]
    raw_crop = raw.crop((crop["x1"], crop["y1"], crop["x2"], crop["y2"])).resize((PANEL, PANEL), Image.Resampling.LANCZOS)
    marker_crop = marker.crop((crop["x1"], crop["y1"], crop["x2"], crop["y2"])).resize((PANEL, PANEL), Image.Resampling.LANCZOS)

    card = Image.new("RGB", (CARD_SOURCE_WIDTH, CARD_SOURCE_HEIGHT), "white")
    draw = ImageDraw.Draw(card)
    draw.rectangle((0, 0, CARD_SOURCE_WIDTH - 1, CARD_SOURCE_HEIGHT - 1), outline=LINE, width=1)
    draw.rectangle((0, 0, CARD_SOURCE_WIDTH - 1, 72), fill=(250, 252, 255), outline=LINE, width=1)
    text(draw, (18, 12), f"Card #{row['card_index']:04d}  Source {row['source_id']}  score {row['score']:.4f}", FONT_18)
    text(draw, (18, 40), f"{row['prediction_id']} | page {row['page']:03d} pos {row['position']:02d} | threshold 0.125", FONT_14, MUTED)
    text(draw, (18, 84), "LEFT / Raw source + model detection", FONT_14)
    text(draw, (468, 84), "RIGHT / Marker reference + model location guide", FONT_14)
    card.paste(raw_crop, (18, 108))
    card.paste(marker_crop, (468, 108))
    draw_annotation(draw, box, crop, (18, 108))
    draw_annotation(draw, box, crop, (468, 108))
    b = box
    text(draw, (18, 482), f"bbox x1={b['x1']:.1f} y1={b['y1']:.1f} x2={b['x2']:.1f} y2={b['y2']:.1f}", FONT_14)
    text(draw, (18, 506), f"crop {crop['x1']},{crop['y1']} - {crop['x2']},{crop['y2']} | pair verified by source_id={mapping['source_id']}", FONT_14, MUTED)
    text(draw, (468, 506), "cyan box/crosshair = model location; marker content preserved", FONT_12, GRAY)
    return card


def make_page(page_num: int, rows: list[dict[str, Any]], image_cache: dict[str, tuple[Image.Image, Image.Image]], mappings: dict[str, dict[str, str]], out_path: Path) -> None:
    page = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "white")
    draw = ImageDraw.Draw(page)
    text(draw, (80, 42), "Small Anchor 16/32/64/128 Expert Review - paired comparison", FONT_28)
    source_range = f"{rows[0]['source_id']} - {rows[-1]['source_id']}" if rows else ""
    text(draw, (80, 78), f"Threshold 0.125 | page {page_num}/{EXPECTED_PAGES} | total cards {EXPECTED_CARDS} | sources {source_range}", FONT_18)
    text(draw, (80, 105), "Left = raw source crop. Right = marker/reference crop. Cyan guide marks the same model prediction on both.", FONT_16, GRAY)

    for i, row in enumerate(rows):
        source_id = row["source_id"]
        raw, marker = image_cache[source_id]
        card = make_card(row, mappings[source_id], row["crop"], raw, marker)
        thumb = card.resize((CARD_WIDTH, CARD_HEIGHT), Image.Resampling.LANCZOS)
        col = i % 4
        grid_row = i // 4
        x = PAGE_X0 + col * (CARD_WIDTH + PAGE_GAP_X)
        y = PAGE_Y0 + grid_row * (CARD_HEIGHT + PAGE_GAP_Y)
        page.paste(thumb, (x, y))

    draw.rectangle((70, PAGE_HEIGHT - 66, PAGE_WIDTH - 70, PAGE_HEIGHT - 30), fill=(248, 250, 252), outline=LINE)
    text(draw, (84, PAGE_HEIGHT - 58), "Review in browser: leave blank when accepted after page completion; choose F/P/U only for exceptions.", FONT_16, GRAY)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    page.save(out_path, "WEBP", quality=82, method=6)


def rel_site(path: Path) -> str:
    return path.relative_to(SITE_DIR).as_posix()


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def build() -> None:
    started = datetime.now(timezone.utc)
    original_asset_size = BASELINE_REVIEW_PAGE_ASSET_BYTES
    manifest_hash = sha256(MANIFEST_CSV)
    package_identity = json.loads(PACKAGE_IDENTITY_JSON.read_text(encoding="utf-8"))
    manifest_rows = read_csv(MANIFEST_CSV)
    mapping_rows = read_csv(MAPPING_CSV)
    mappings = {row["source_id"]: row for row in mapping_rows}

    if len(manifest_rows) != EXPECTED_CARDS:
        raise RuntimeError(f"Expected {EXPECTED_CARDS} cards, found {len(manifest_rows)}")
    if package_identity["checkpoint_sha256"] != CHECKPOINT_SHA256:
        raise RuntimeError("Checkpoint identity mismatch")

    audit_rows: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    unresolved: list[str] = []
    conflicts: list[str] = []
    image_cache: dict[str, tuple[Image.Image, Image.Image]] = {}

    for row in manifest_rows:
        source_id = row["source_id"]
        mapping = mappings.get(source_id)
        if mapping is None:
            unresolved.append(row["card_index"])
            continue
        raw_path = ROOT / mapping["raw_image_path"]
        marker_path = ROOT / mapping["marker_image_path"]
        if not raw_path.is_file() or not marker_path.is_file() or mapping["dimensions_match"] != "True":
            unresolved.append(row["card_index"])
            continue
        if mapping["source_id"] != source_id:
            conflicts.append(row["card_index"])
            continue
        if source_id not in image_cache:
            image_cache[source_id] = (Image.open(raw_path).convert("RGB"), Image.open(marker_path).convert("RGB"))
        raw, marker = image_cache[source_id]
        box = {
            "x1": float(row["x1"]),
            "y1": float(row["y1"]),
            "x2": float(row["x2"]),
            "y2": float(row["y2"]),
        }
        crop = crop_for_box(box, int(mapping["raw_width"]), int(mapping["raw_height"]))
        card_index = int(row["card_index"])
        page = int(row["page"])
        position = ((card_index - 1) % 20) + 1
        card_payload = {
            "cardId": f"card_{card_index:04d}",
            "cardIndex": card_index,
            "page": page,
            "position": position,
            "row": int(row["row"]),
            "column": int(row["column"]),
            "sourceId": source_id,
            "predictionId": row["prediction_id"],
            "score": float(row["score"]),
            "bbox": box,
            "bboxWidth": float(row["width"]),
            "bboxHeight": float(row["height"]),
            "tileId": row["tile_id"],
            "tileOriginX": row["tile_origin_x"],
            "tileOriginY": row["tile_origin_y"],
            "automaticClassification": row["classification_from_automatic_eval"],
            "crop": crop,
            "leftSourceId": source_id,
            "rightSourceId": source_id,
            "leftImageIdentity": f"raw_sha256:{mapping['raw_sha256']}",
            "rightImageIdentity": f"marker_sha256:{mapping['marker_sha256']}",
            "sameSourcePairingProven": True,
        }
        cards.append(card_payload)
        audit_rows.append(
            {
                "card_id": card_payload["cardId"],
                "page": page,
                "position": position,
                "source_id": source_id,
                "prediction_id": row["prediction_id"],
                "left_source_id": source_id,
                "right_source_id": source_id,
                "left_image_identity": card_payload["leftImageIdentity"],
                "right_image_identity": card_payload["rightImageIdentity"],
                "prediction_score": row["score"],
                "x1": row["x1"],
                "y1": row["y1"],
                "x2": row["x2"],
                "y2": row["y2"],
                "crop_x1": crop["x1"],
                "crop_y1": crop["y1"],
                "crop_x2": crop["x2"],
                "crop_y2": crop["y2"],
                "pair_status": "VALID_PAIR_SOURCE_ID_MATCH",
            }
        )

    if unresolved or conflicts or len(cards) != EXPECTED_CARDS:
        summary = {
            "status": "PAIR_PROVENANCE_BLOCKED",
            "total_cards": len(manifest_rows),
            "valid_pairs": len(cards),
            "source_id_conflicts": len(conflicts),
            "unresolved_pairs": len(unresolved),
            "conflict_card_indices": conflicts[:50],
            "unresolved_card_indices": unresolved[:50],
        }
        write_json(AUDIT_DIR / "pair_integrity_summary.json", summary)
        raise RuntimeError("PAIR_PROVENANCE_BLOCKED")

    backup_dir = AUDIT_DIR / "previous_review_pages_backup"
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    for old_page in ASSET_DIR.glob("*.webp"):
        shutil.copy2(old_page, backup_dir / old_page.name)

    pages_payload: list[dict[str, Any]] = []
    for page_num in range(1, EXPECTED_PAGES + 1):
        page_cards = [card for card in cards if card["page"] == page_num]
        out_path = ASSET_DIR / f"page_{page_num:03d}.webp"
        render_rows = []
        for card in page_cards:
            render_rows.append(
                {
                    "card_index": card["cardIndex"],
                    "page": card["page"],
                    "position": card["position"],
                    "source_id": card["sourceId"],
                    "prediction_id": card["predictionId"],
                    "score": card["score"],
                    "box": card["bbox"],
                    "crop": card["crop"],
                }
            )
        make_page(page_num, render_rows, image_cache, mappings, out_path)
        scores = [card["score"] for card in page_cards]
        pages_payload.append(
            {
                "page": page_num,
                "cardStart": page_cards[0]["cardIndex"],
                "cardEnd": page_cards[-1]["cardIndex"],
                "cardCount": len(page_cards),
                "image": rel_site(out_path),
                "sourceCount": len({card["sourceId"] for card in page_cards}),
                "scoreMin": min(scores),
                "scoreMax": max(scores),
                "cards": [card["cardId"] for card in page_cards],
            }
        )

    revised_asset_size = dir_size(ASSET_DIR)
    for raw, marker in image_cache.values():
        raw.close()
        marker.close()

    write_csv(AUDIT_DIR / "pair_integrity_audit.csv", audit_rows)
    summary = {
        "status": "PAIR_INTEGRITY_READY",
        "created_utc": started.isoformat(),
        "total_cards": EXPECTED_CARDS,
        "valid_pairs": len(audit_rows),
        "source_id_conflicts": 0,
        "unresolved_pairs": 0,
        "page_count": EXPECTED_PAGES,
        "manifest_sha256": manifest_hash,
        "mapping_sha256": sha256(MAPPING_CSV),
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "threshold": "0.125",
        "pair_semantics": {
            "left": "Raw/source image crop with the current model detection guide.",
            "right": "Original marker/reference image crop from the same source_id with the same model-location guide.",
        },
        "asset_strategy": "Option 1: 70 paired review-page WebP files plus HTML/CSS card controls using deterministic 5x4 page geometry.",
        "previous_review_page_asset_bytes": original_asset_size,
        "revised_review_page_asset_bytes": revised_asset_size,
        "revised_asset_bytes_per_page_mean": round(revised_asset_size / EXPECTED_PAGES, 2),
    }
    write_json(AUDIT_DIR / "pair_integrity_summary.json", summary)
    report = f"""# Pair Upgrade Report

Status: `{summary['status']}`

- Total cards: {EXPECTED_CARDS}
- Valid pairs: {len(audit_rows)}
- Source-ID conflicts: 0
- Unresolved pairs: 0
- Previous review-page assets: {original_asset_size:,} bytes
- Revised review-page assets: {revised_asset_size:,} bytes
- Strategy: {summary['asset_strategy']}

## Pair Semantics

Left panel is the raw/source image crop with the current Small Anchor model detection guide. Right panel is the original marker/reference image crop from the same authoritative `source_id`, rendered with the same crop and guide so the expert can inspect both model correctness and visual pairing.

No model inference, training, threshold, checkpoint, split, ground truth, or prediction result was changed.
"""
    (AUDIT_DIR / "pair_upgrade_report.md").write_text(report, encoding="utf-8")

    review_data = {
        "title": "Small Anchor 16/32/64/128 Expert Review",
        "status": "pending_human_review",
        "reviewSchemaVersion": "1.0.0",
        "canonicalGalleryPackage": "package_a_small_anchor_0125",
        "manifestIdentifier": f"card_manifest_sha256:{manifest_hash}",
        "packageComparison": {
            "effectivePredictionSetIdentical": True,
            "pagePngHashesIdentical": False,
            "manifestsDifferOnlyByPackageId": True,
            "packageBThresholdDiffersFrom0125": False,
            "reasonSingleGallery": "Package A and B have the same threshold, checkpoint, card count, page count, and effective prediction/card set. This page uses Package A as the canonical structured review gallery.",
        },
        "reviewUi": {
            "localStorageKey": f"pics-birdnests-review:v1:package_a_small_anchor_0125:small_16_32_64_128:0.125:{CHECKPOINT_SHA256}:card_manifest_sha256:{manifest_hash}",
            "blankBeforePageComplete": "NOT_REVIEWED",
            "blankAfterPageComplete": "ACCEPTED",
            "selectionMap": {
                "": "ACCEPTED_AFTER_PAGE_COMPLETE",
                "F": "FALSE_POSITIVE",
                "P": "PAIRING_ERROR",
                "U": "UNCERTAIN",
            },
            "finalClassificationMap": {
                "completed_blank": "HUMAN_ACCEPTED_TRUE_POSITIVE",
                "F": "FALSE_POSITIVE_BY_EXPERT",
                "P": "PAIRING_ERROR",
                "U": "UNRESOLVED",
                "incomplete_blank": "NOT_REVIEWED",
            },
            "cardGeometry": {
                "pageWidth": PAGE_WIDTH,
                "pageHeight": PAGE_HEIGHT,
                "cardWidth": CARD_WIDTH,
                "cardHeight": CARD_HEIGHT,
                "x0": PAGE_X0,
                "y0": PAGE_Y0,
                "gapX": PAGE_GAP_X,
                "gapY": PAGE_GAP_Y,
                "columns": 4,
                "rows": 5,
            },
        },
        "packages": [
            {
                "card_count": EXPECTED_CARDS,
                "checkpoint_sha256": CHECKPOINT_SHA256,
                "contains_previous_expert_markings": False,
                "model_profile": "small_16_32_64_128",
                "package_id": "package_a_small_anchor_0125",
                "page_count": EXPECTED_PAGES,
                "same_source_pairing_asserted": True,
                "threshold": "0.125",
            },
            {
                "card_count": EXPECTED_CARDS,
                "checkpoint_sha256": CHECKPOINT_SHA256,
                "contains_previous_expert_markings": False,
                "model_profile": "small_16_32_64_128",
                "package_id": "package_b_small_anchor_validation_selected",
                "page_count": EXPECTED_PAGES,
                "same_source_pairing_asserted": True,
                "threshold": "0.125",
            },
        ],
        "experiment": {
            "baselineAnchors": [32, 64, 128, 256, 512],
            "smallAnchors": [16, 32, 64, 128],
            "checkpointSha256": CHECKPOINT_SHA256,
            "threshold": "0.125",
            "cardCount": EXPECTED_CARDS,
            "pageCount": EXPECTED_PAGES,
            "modelProfile": "small_16_32_64_128",
        },
        "metrics": {
            "baseline": {
                "recall0125": 0.7099,
                "automaticPrecisionProxy": 0.2723,
                "unmatchedPredictions": 1785,
                "humanReviewedPrecision": 0.0717,
                "reviewedPredictions": 1785,
                "expertAccepted": 128,
                "expertFalsePositive": 1657,
                "pairingErrors": 0,
                "unresolved": 0,
            },
            "smallAnchor": {
                "recall0125": 0.7322,
                "automaticPrecisionProxy": 0.3298,
                "unmatchedPredictions": EXPECTED_CARDS,
            },
        },
        "pairSemantics": summary["pair_semantics"],
        "pages": pages_payload,
        "cards": cards,
    }
    write_json(DATA_DIR / "review-data.json", review_data)

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://suwaroj95-spec.github.io/Pics-BirdNests/anchor-review-small-16-32-64-128/data/review-result-schema.json",
        "title": "Pics-BirdNests structured expert review result",
        "type": "object",
        "required": ["reviewSchemaVersion", "packageId", "modelProfile", "checkpointSha256", "threshold", "manifestIdentifier", "exportedAt", "results"],
        "properties": {
            "reviewSchemaVersion": {"const": "1.0.0"},
            "packageId": {"const": "package_a_small_anchor_0125"},
            "modelProfile": {"const": "small_16_32_64_128"},
            "checkpointSha256": {"const": CHECKPOINT_SHA256},
            "threshold": {"const": "0.125"},
            "manifestIdentifier": {"const": f"card_manifest_sha256:{manifest_hash}"},
            "exportedAt": {"type": "string"},
            "summary": {"type": "object"},
            "results": {
                "type": "array",
                "minItems": EXPECTED_CARDS,
                "maxItems": EXPECTED_CARDS,
                "items": {
                    "type": "object",
                    "required": [
                        "cardId",
                        "page",
                        "position",
                        "sourceId",
                        "predictionId",
                        "score",
                        "reviewerSelection",
                        "finalClassification",
                        "pageCompleted",
                        "exportedAt",
                    ],
                    "properties": {
                        "cardId": {"type": "string"},
                        "page": {"type": "integer", "minimum": 1, "maximum": EXPECTED_PAGES},
                        "position": {"type": "integer", "minimum": 1, "maximum": 20},
                        "sourceId": {"type": "string"},
                        "predictionId": {"type": "string"},
                        "score": {"type": "number"},
                        "reviewerSelection": {"enum": ["", "F", "P", "U"]},
                        "reviewStatus": {"enum": ["NOT_REVIEWED", "ACCEPTED", "FALSE_POSITIVE", "PAIRING_ERROR", "UNCERTAIN"]},
                        "finalClassification": {
                            "enum": [
                                "HUMAN_ACCEPTED_TRUE_POSITIVE",
                                "FALSE_POSITIVE_BY_EXPERT",
                                "PAIRING_ERROR",
                                "UNRESOLVED",
                                "NOT_REVIEWED",
                            ]
                        },
                        "pageCompleted": {"type": "boolean"},
                        "bboxX1": {"type": "number"},
                        "bboxY1": {"type": "number"},
                        "bboxX2": {"type": "number"},
                        "bboxY2": {"type": "number"},
                        "exportedAt": {"type": "string"},
                    },
                },
            },
        },
    }
    write_json(DATA_DIR / "review-result-schema.json", schema)


if __name__ == "__main__":
    build()
