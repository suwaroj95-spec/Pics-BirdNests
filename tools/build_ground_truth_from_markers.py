from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crop_clean_patches import (  # noqa: E402
    MIN_BLUE_COMPONENT_AREA,
    detect_blue_mask,
    original_for_marked,
)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
OUTPUT_ROOT = PROJECT_ROOT / "tmp" / "ground_truth_builder"
RADIUS_MIN = 16.0
RADIUS_MAX = 50.0
AUTOMATIC_MERGE_ENABLED = False

GROUND_TRUTH_COLUMNS = [
    "image_id",
    "source_image",
    "marked_image",
    "spot_id",
    "x_center",
    "y_center",
    "radius",
    "component_area",
    "enclosing_circle_radius",
    "quality_score",
    "pass_fail_status",
    "manually_verified_alignment",
    "alignment_note",
    "marker_source",
    "label_confidence",
    "review_status",
    "notes",
]

IMAGE_SUMMARY_COLUMNS = [
    "image_id",
    "source_image",
    "marked_image",
    "dirty_spot_count",
    "quality_score",
    "pass_fail_status",
    "manually_verified_alignment",
    "alignment_note",
    "preview_path",
    "review_status",
    "notes",
]

REVIEW_QUEUE_COLUMNS = [
    "image_id",
    "reason",
    "priority",
    "recommended_action",
    "manual_review_required",
    "source_image",
    "preview_path",
    "notes",
]


@dataclass(frozen=True)
class ImagePair:
    image_id: str
    original_path: Path
    marked_path: Path


@dataclass(frozen=True)
class PairDiscovery:
    pairs: list[ImagePair]
    missing_originals: list[str]
    missing_marked: list[str]
    unsupported_extensions: list[str]


@dataclass(frozen=True)
class MarkerLabel:
    image_id: str
    spot_id: str
    x_center: float
    y_center: float
    radius: float
    component_area: int
    enclosing_circle_radius: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build preliminary ground-truth point/circle labels from verified Blue Markers. "
            "No model is trained and source images are never modified."
        )
    )
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--marker-analysis-dir", required=True)
    parser.add_argument("--review-image-ids", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-previews", action="store_true")
    return parser.parse_args()


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError(f"Path must stay inside project root: {value}") from exc
    return resolved


def resolve_output_dir(value: str) -> Path:
    output_dir = resolve_project_path(value)
    try:
        output_dir.relative_to(OUTPUT_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("Output directory must stay under tmp/ground_truth_builder") from exc
    return output_dir


def natural_image_key(path: Path) -> tuple[int, str]:
    stem = path.stem[:-1] if path.stem.endswith("m") else path.stem
    return (int(stem), path.name) if stem.isdigit() else (10**9, path.name.lower())


def discover_image_pairs(raw_dir: Path) -> PairDiscovery:
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw directory not found: {raw_dir}")
    if not raw_dir.is_dir():
        raise NotADirectoryError(f"Raw path is not a directory: {raw_dir}")

    image_files = [
        path
        for path in raw_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    unsupported = sorted(
        path.name
        for path in raw_dir.iterdir()
        if path.is_file() and path.suffix.lower() not in SUPPORTED_EXTENSIONS
    )

    original_files = [path for path in image_files if not path.stem.endswith("m")]
    original_lookup = {path.name.lower(): path for path in original_files}
    marked_files = sorted(
        [path for path in image_files if path.stem.endswith("m")],
        key=natural_image_key,
    )

    pairs: list[ImagePair] = []
    missing_originals: list[str] = []
    paired_originals: set[Path] = set()
    for marked_path in marked_files:
        original_path = original_for_marked(marked_path)
        original = original_lookup.get(original_path.name.lower())
        if original is None:
            missing_originals.append(marked_path.name)
            continue
        paired_originals.add(original)
        pairs.append(ImagePair(original.stem, original, marked_path))

    missing_marked = sorted(original.name for original in original_files if original not in paired_originals)
    return PairDiscovery(pairs, missing_originals, missing_marked, unsupported)


def read_image(path: Path) -> np.ndarray | None:
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


def quality_grade(spot_count: int) -> tuple[int, str]:
    if spot_count <= 9:
        return 95, "PASS"
    if spot_count <= 20:
        return 90, "PASS"
    if spot_count <= 30:
        return 80, "PASS"
    return 70, "FAIL"


def clamp_radius(radius: float) -> float:
    return round(max(RADIUS_MIN, min(float(radius), RADIUS_MAX)), 4)


def alignment_note_for(image_id: str) -> str:
    if image_id in {"1", "2"}:
        return "non-identical frame; visually verified marker-to-defect correspondence"
    return "visually verified marker-to-defect correspondence"


def detect_marker_labels(marked_image: np.ndarray, image_id: str) -> list[MarkerLabel]:
    blue_mask = detect_blue_mask(marked_image)
    component_count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        (blue_mask > 0).astype(np.uint8),
        connectivity=8,
    )

    marker_labels: list[MarkerLabel] = []
    for label in range(1, component_count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < MIN_BLUE_COMPONENT_AREA:
            continue

        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        center_x = round(float(centroids[label][0]), 4)
        center_y = round(float(centroids[label][1]), 4)

        component_mask = (labels[y : y + height, x : x + width] == label).astype(np.uint8)
        contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            contour = max(contours, key=cv2.contourArea)
            (_, _), enclosing_radius = cv2.minEnclosingCircle(contour)
        else:
            enclosing_radius = max(width, height) / 2.0

        marker_labels.append(
            MarkerLabel(
                image_id=image_id,
                spot_id=f"{image_id}_spot_{len(marker_labels) + 1:03d}",
                x_center=center_x,
                y_center=center_y,
                radius=clamp_radius(enclosing_radius),
                component_area=area,
                enclosing_circle_radius=round(float(enclosing_radius), 4),
            )
        )

    return marker_labels


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def preview_relative_path(output_dir: Path, preview_path: Path) -> str:
    return str(preview_path.relative_to(output_dir)).replace("\\", "/")


def make_preview(
    original_image: np.ndarray,
    labels: list[MarkerLabel],
    destination: Path,
    image_id: str,
    quality_score: int,
    pass_fail_status: str,
) -> None:
    preview = original_image.copy()
    border_color = (0, 170, 0) if pass_fail_status == "PASS" else (0, 0, 255)
    cv2.rectangle(preview, (0, 0), (preview.shape[1] - 1, preview.shape[0] - 1), border_color, 12)
    for label in labels:
        center = (int(round(label.x_center)), int(round(label.y_center)))
        radius = int(round(label.radius))
        cv2.circle(preview, center, radius, (0, 255, 255), 3)
        cv2.circle(preview, center, 2, (0, 0, 255), -1)
        cv2.putText(
            preview,
            label.spot_id.rsplit("_", 1)[-1],
            (center[0] + radius + 4, max(24, center[1])),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

    label_text = f"{image_id}: {len(labels)} spots | {quality_score}% | {pass_fail_status}"
    cv2.putText(
        preview,
        label_text,
        (24, 48),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.05,
        border_color,
        3,
        cv2.LINE_AA,
    )
    cv2.imwrite(str(destination), preview)


def read_marker_analysis(marker_analysis_dir: Path) -> dict[str, object]:
    summary_path = marker_analysis_dir / "distribution_summary.json"
    if not summary_path.exists():
        return {}
    return json.loads(summary_path.read_text(encoding="utf-8"))


def review_priority(reasons: list[str], status: str) -> str:
    if status == "FAIL":
        return "high"
    if any("missing" in reason or "invalid" in reason or "detection_failure" in reason for reason in reasons):
        return "high"
    return "medium"


def add_review_row(
    rows: list[dict[str, object]],
    image_id: str,
    reasons: list[str],
    status: str,
    source_image: str,
    preview_path: str,
    notes: str,
) -> None:
    if not reasons:
        return
    rows.append(
        {
            "image_id": image_id,
            "reason": "; ".join(dict.fromkeys(reasons)),
            "priority": review_priority(reasons, status),
            "recommended_action": "confirm preview circles before finalizing",
            "manual_review_required": "true",
            "source_image": source_image,
            "preview_path": preview_path,
            "notes": notes,
        }
    )


def ground_truth_report(summary: dict[str, object], output_dir: Path) -> str:
    return f"""# Ground Truth Builder Report

## 1. Purpose

รอบนี้สร้าง preliminary ground-truth labels จาก Blue Marker ที่ผู้ใช้ยืนยันแล้วว่า marker สอดคล้องกับจุดสกปรกจริงบนภาพ original โดยไม่ train model และไม่แก้ไขภาพต้นฉบับ

## 2. Policy Values Used

- Minimum blue-component area: {MIN_BLUE_COMPONENT_AREA} px
- Automatic marker merge: disabled
- Radius rule: clamp(enclosing_circle_radius, {int(RADIUS_MIN)}, {int(RADIUS_MAX)})
- Quality rule: 0-9 = 95/PASS, 10-20 = 90/PASS, 21-30 = 80/PASS, 31+ = 70/FAIL
- Images 1 and 2: non-identical frame; visually verified marker-to-defect correspondence

## 3. Pair Discovery Summary

- Pair count: {summary['pair_count']}
- Processed images: {summary['processed_images']}
- Skipped images: {summary['skipped_images']}

## 4. Marker Detection Summary

- Total dirty spots generated: {summary['total_dirty_spots']}
- Minimum component area: {summary['minimum_component_area']} px
- Marker source: blue_marker
- Label confidence: preliminary_verified

## 5. Image Score Summary

- PASS images: {summary['pass_images']}
- FAIL images: {summary['fail_images']}
- REVIEW images: {summary['review_images']}

## 6. Review Queue

- Images with review rows: {summary['review_queue_images']}
- Images with manual alignment note: {summary['images_with_manual_alignment_note']}

## 7. Output Files

- `ground_truth_manifest.csv`: one row per dirty spot
- `image_quality_summary.csv`: one row per original image
- `review_queue.csv`: images needing preview confirmation or attention
- `generation_summary.json`: machine-readable generation summary
- `previews/`: original-image previews with point/circle labels

## 8. Important Limitations

- This run generates preliminary ground-truth labels.
- No model was trained.
- Preview confirmation is required before labels are final.
- Circle radius is for point/circle label visualization only; it is not a segmentation boundary.
- No automatic warp, translation, or coordinate correction was applied.

Output directory: `{output_dir}`
"""


def build_ground_truth(
    raw_dir: Path,
    output_dir: Path,
    marker_analysis_dir: Path,
    review_image_ids: set[str] | None = None,
    dry_run: bool = False,
    no_previews: bool = False,
) -> dict[str, object]:
    review_image_ids = review_image_ids or set()
    marker_analysis = read_marker_analysis(marker_analysis_dir)
    outlier_images = marker_analysis.get("outlier_images", {}) if isinstance(marker_analysis, dict) else {}
    large_marker_images = set(outlier_images.get("large_marker_images", []))
    high_spot_count_images = set(outlier_images.get("high_spot_count_images", []))

    discovery = discover_image_pairs(raw_dir)
    if dry_run:
        return {
            "pair_count": len(discovery.pairs),
            "processed_images": 0,
            "skipped_images": len(discovery.pairs),
            "total_dirty_spots": 0,
            "pass_images": 0,
            "fail_images": 0,
            "review_images": 0,
            "images_with_manual_alignment_note": 0,
            "minimum_component_area": MIN_BLUE_COMPONENT_AREA,
            "radius_rule": f"clamp(enclosing_circle_radius, {int(RADIUS_MIN)}, {int(RADIUS_MAX)})",
            "automatic_merge_enabled": AUTOMATIC_MERGE_ENABLED,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    preview_dir = output_dir / "previews"
    if not no_previews:
        preview_dir.mkdir(exist_ok=True)

    manifest_rows: list[dict[str, object]] = []
    image_rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    skipped_images = 0

    for pair in discovery.pairs:
        original = read_image(pair.original_path)
        marked = read_image(pair.marked_path)
        reasons: list[str] = []

        if original is None or marked is None:
            skipped_images += 1
            reasons.append("missing_or_unreadable_image")
            add_review_row(
                review_rows,
                pair.image_id,
                reasons,
                "REVIEW",
                pair.original_path.name,
                "",
                "could not read original or marked image",
            )
            continue

        if original.shape[:2] != marked.shape[:2]:
            reasons.append("invalid_dimension_mismatch")

        labels = detect_marker_labels(marked, pair.image_id)
        if not labels:
            reasons.append("detection_failure_no_blue_marker")

        quality_score, pass_fail_status = quality_grade(len(labels))
        alignment_note = alignment_note_for(pair.image_id)
        if pair.image_id in {"1", "2"}:
            reasons.append("non-identical frame; manually verified marker-to-defect correspondence")
        if pair.image_id in review_image_ids:
            reasons.append("explicitly requested for review")
        if pair.image_id in high_spot_count_images:
            reasons.append("marker-analysis high spot-count outlier")
        if pair.image_id in large_marker_images or any(label.enclosing_circle_radius > RADIUS_MAX for label in labels):
            reasons.append("marker radius exceeds preview clamp; confirm circle labels")
        if pass_fail_status == "FAIL":
            reasons.append("31+ dirty spots; verify FAIL-grade count before finalizing")

        preview_name = f"{pair.image_id}_ground_truth_preview.jpg"
        preview_path = preview_dir / preview_name
        preview_rel = preview_relative_path(output_dir, preview_path) if not no_previews else ""
        if not no_previews:
            make_preview(original, labels, preview_path, pair.image_id, quality_score, pass_fail_status)

        for label in labels:
            manifest_rows.append(
                {
                    "image_id": pair.image_id,
                    "source_image": pair.original_path.name,
                    "marked_image": pair.marked_path.name,
                    "spot_id": label.spot_id,
                    "x_center": label.x_center,
                    "y_center": label.y_center,
                    "radius": label.radius,
                    "component_area": label.component_area,
                    "enclosing_circle_radius": label.enclosing_circle_radius,
                    "quality_score": quality_score,
                    "pass_fail_status": pass_fail_status,
                    "manually_verified_alignment": "true",
                    "alignment_note": alignment_note,
                    "marker_source": "blue_marker",
                    "label_confidence": "preliminary_verified",
                    "review_status": "pending_preview_confirmation",
                    "notes": "no automatic merge; no warp; no coordinate correction",
                }
            )

        image_rows.append(
            {
                "image_id": pair.image_id,
                "source_image": pair.original_path.name,
                "marked_image": pair.marked_path.name,
                "dirty_spot_count": len(labels),
                "quality_score": quality_score,
                "pass_fail_status": pass_fail_status,
                "manually_verified_alignment": "true",
                "alignment_note": alignment_note,
                "preview_path": preview_rel,
                "review_status": "pending_preview_confirmation",
                "notes": "preliminary ground-truth labels from blue markers",
            }
        )
        add_review_row(
            review_rows,
            pair.image_id,
            reasons,
            pass_fail_status,
            pair.original_path.name,
            preview_rel,
            "preview confirmation required before labels are final",
        )

    for missing in discovery.missing_originals:
        add_review_row(review_rows, missing, ["missing_original"], "REVIEW", "", "", "missing original pair")
    for missing in discovery.missing_marked:
        add_review_row(review_rows, missing, ["missing_marked"], "REVIEW", missing, "", "missing marked pair")

    summary = {
        "pair_count": len(discovery.pairs),
        "processed_images": len(image_rows),
        "skipped_images": skipped_images,
        "total_dirty_spots": len(manifest_rows),
        "pass_images": sum(1 for row in image_rows if row["pass_fail_status"] == "PASS"),
        "fail_images": sum(1 for row in image_rows if row["pass_fail_status"] == "FAIL"),
        "review_images": sum(1 for row in image_rows if row["pass_fail_status"] == "REVIEW"),
        "images_with_manual_alignment_note": sum(
            1
            for row in image_rows
            if row["alignment_note"] == "non-identical frame; visually verified marker-to-defect correspondence"
        ),
        "minimum_component_area": MIN_BLUE_COMPONENT_AREA,
        "radius_rule": f"clamp(enclosing_circle_radius, {int(RADIUS_MIN)}, {int(RADIUS_MAX)})",
        "automatic_merge_enabled": AUTOMATIC_MERGE_ENABLED,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "review_queue_images": [row["image_id"] for row in review_rows],
        "missing_originals": discovery.missing_originals,
        "missing_marked": discovery.missing_marked,
        "unsupported_extensions": discovery.unsupported_extensions,
    }

    write_csv(output_dir / "ground_truth_manifest.csv", GROUND_TRUTH_COLUMNS, manifest_rows)
    write_csv(output_dir / "image_quality_summary.csv", IMAGE_SUMMARY_COLUMNS, image_rows)
    write_csv(output_dir / "review_queue.csv", REVIEW_QUEUE_COLUMNS, review_rows)
    (output_dir / "generation_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "ground_truth_builder_report.md").write_text(
        ground_truth_report(summary, output_dir),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    args = parse_args()
    raw_dir = resolve_project_path(args.raw_dir)
    output_dir = resolve_output_dir(args.output_dir)
    marker_analysis_dir = resolve_project_path(args.marker_analysis_dir)
    review_ids = {item.strip() for item in args.review_image_ids.split(",") if item.strip()}
    summary = build_ground_truth(
        raw_dir,
        output_dir,
        marker_analysis_dir,
        review_image_ids=review_ids,
        dry_run=args.dry_run,
        no_previews=args.no_previews,
    )
    print(f"Ground Truth Builder complete: {output_dir}")
    print(f"Pairs processed: {summary['processed_images']} / {summary['pair_count']}")
    print(f"Total dirty spots: {summary['total_dirty_spots']}")
    print(
        "Image status counts: "
        f"PASS={summary['pass_images']} FAIL={summary['fail_images']} REVIEW={summary['review_images']}"
    )


if __name__ == "__main__":
    main()
