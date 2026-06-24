from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


BLUE_HSV_LOWER = (90, 50, 50)
BLUE_HSV_UPPER = (140, 255, 255)
MINIMUM_COMPONENT_AREA = 20
BLUE_MARKER_DETECTION_SOURCE = (
    "Mirrors crop_clean_patches.py BLUE_HSV_LOWER=(90,50,50), "
    "BLUE_HSV_UPPER=(140,255,255), detect_blue_mask MORPH_CLOSE 5x5 ellipse, "
    "and MIN_BLUE_COMPONENT_AREA=20; also matches tools/analyze_blue_marker_distribution.py usage."
)

VALID_LABELS = {"dirty_positive", "clean_negative"}
PRIMARY_OUTPUTS = [
    "crop_marker_leakage_manifest.csv",
    "marker_leakage_summary.csv",
    "marker_like_candidates.csv",
]
RECOMMENDED_ACTION = "visually confirm whether blue region is annotation marker or natural image content"

REQUIRED_LINEAGE_COLUMNS = [
    "output_file",
    "label",
    "resolved_image_id",
    "resolved_source_image",
    "dataset_split",
    "pass_fail_status",
    "lineage_status",
]

ADDED_MANIFEST_COLUMNS = [
    "blue_pixel_count",
    "blue_pixel_fraction",
    "blue_component_count",
    "largest_blue_component_area",
    "marker_like_component_count",
    "marker_contamination_status",
    "audit_result",
    "audit_notes",
]

SUMMARY_COLUMNS = [
    "dataset_split",
    "crop_label",
    "pass_fail_status",
    "crop_count",
    "none_count",
    "low_blue_signal_count",
    "marker_like_count",
    "marker_like_rate",
    "max_largest_blue_component_area",
]

CANDIDATE_COLUMNS = [
    "crop_path",
    "image_id",
    "source_image",
    "dataset_split",
    "crop_label",
    "pass_fail_status",
    "blue_pixel_count",
    "blue_pixel_fraction",
    "blue_component_count",
    "largest_blue_component_area",
    "marker_like_component_count",
    "review_sample_path",
    "recommended_action",
    "notes",
]


class AuditError(RuntimeError):
    pass


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_output_empty(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise AuditError(f"Output directory already contains files: {output_dir}")


def require_columns(columns: list[str], required: list[str], source_name: str) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise AuditError(f"{source_name} missing required columns: {', '.join(missing)}")


def safe_crop_path(crops_dir: Path, crop_path_text: str) -> Path:
    if not crop_path_text:
        raise AuditError("Crop row has empty output_file")
    crops_root = crops_dir.resolve()
    candidate = (crops_root / crop_path_text).resolve()
    try:
        candidate.relative_to(crops_root)
    except ValueError as exc:
        raise AuditError(f"Crop path is outside the allowed Crops directory: {crop_path_text}") from exc
    return candidate


def detect_blue_mask(image: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    blue_mask = cv2.inRange(
        hsv,
        np.array(BLUE_HSV_LOWER, dtype=np.uint8),
        np.array(BLUE_HSV_UPPER, dtype=np.uint8),
    )
    return cv2.morphologyEx(
        blue_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    )


def analyze_blue_components(image: np.ndarray) -> dict[str, object]:
    blue_mask = detect_blue_mask(image)
    blue_pixel_count = int(np.count_nonzero(blue_mask))
    image_area = int(image.shape[0] * image.shape[1])
    blue_pixel_fraction = blue_pixel_count / image_area if image_area else 0.0
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (blue_mask > 0).astype(np.uint8),
        connectivity=8,
    )

    components: list[dict[str, int]] = []
    largest_area = 0
    marker_like_count = 0
    for label in range(1, component_count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        largest_area = max(largest_area, area)
        if area >= MINIMUM_COMPONENT_AREA:
            marker_like_count += 1
        components.append({"area": area, "x": x, "y": y, "width": width, "height": height})

    if blue_pixel_count == 0:
        status = "none"
    elif marker_like_count == 0:
        status = "low_blue_signal"
    else:
        status = "marker_like"

    return {
        "blue_mask": blue_mask,
        "components": components,
        "blue_pixel_count": blue_pixel_count,
        "blue_pixel_fraction": blue_pixel_fraction,
        "blue_component_count": len(components),
        "largest_blue_component_area": largest_area,
        "marker_like_component_count": marker_like_count,
        "marker_contamination_status": status,
    }


def preflight_and_analyze(crops_dir: Path, lineage_manifest: Path) -> tuple[list[str], list[dict[str, object]], dict[str, str]]:
    columns, lineage_rows = read_csv(lineage_manifest)
    require_columns(columns, REQUIRED_LINEAGE_COLUMNS, lineage_manifest.name)
    metadata_path = crops_dir / "metadata.csv"
    if not metadata_path.exists():
        raise AuditError(f"Missing crop metadata: {metadata_path}")

    analyzed_rows: list[dict[str, object]] = []
    for index, row in enumerate(lineage_rows, start=2):
        crop_path = safe_crop_path(crops_dir, row["output_file"])
        if not crop_path.exists():
            raise AuditError(f"Missing crop file at lineage row {index}: {row['output_file']}")
        if not row["resolved_image_id"] or row["lineage_status"] == "unresolved":
            raise AuditError(f"Unresolved lineage at row {index}: {row['output_file']}")
        if not row["dataset_split"]:
            raise AuditError(f"Missing dataset_split at row {index}: {row['output_file']}")
        if row["label"] not in VALID_LABELS:
            raise AuditError(f"Invalid crop label at row {index}: {row['label']}")

        image = cv2.imread(str(crop_path), cv2.IMREAD_COLOR)
        if image is None:
            raise AuditError(f"Unreadable crop image at row {index}: {row['output_file']}")
        analysis = analyze_blue_components(image)
        status = str(analysis["marker_contamination_status"])
        audit_result = "review_candidate" if status == "marker_like" else "pass"
        notes = (
            "marker-like blue component detected; human review required"
            if status == "marker_like"
            else "no marker-like blue component above approved area threshold"
        )

        output_row = dict(row)
        output_row.update(
            {
                "crop_abs_path": str(crop_path),
                "blue_mask": analysis["blue_mask"],
                "blue_components": analysis["components"],
                "blue_pixel_count": analysis["blue_pixel_count"],
                "blue_pixel_fraction": f"{float(analysis['blue_pixel_fraction']):.8f}",
                "blue_component_count": analysis["blue_component_count"],
                "largest_blue_component_area": analysis["largest_blue_component_area"],
                "marker_like_component_count": analysis["marker_like_component_count"],
                "marker_contamination_status": status,
                "audit_result": audit_result,
                "audit_notes": notes,
            }
        )
        analyzed_rows.append(output_row)

    input_hashes = {
        "crops_metadata": file_sha256(metadata_path),
        "crop_lineage_manifest": file_sha256(lineage_manifest),
    }
    return columns, analyzed_rows, input_hashes


def build_summary_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["dataset_split"]), str(row["label"]), str(row["pass_fail_status"]))].append(row)

    summary_rows: list[dict[str, object]] = []
    for (dataset_split, crop_label, pass_fail_status), group_rows in sorted(grouped.items()):
        counts = Counter(str(row["marker_contamination_status"]) for row in group_rows)
        crop_count = len(group_rows)
        marker_like_count = counts["marker_like"]
        max_area = max(int(row["largest_blue_component_area"]) for row in group_rows) if group_rows else 0
        summary_rows.append(
            {
                "dataset_split": dataset_split,
                "crop_label": crop_label,
                "pass_fail_status": pass_fail_status,
                "crop_count": crop_count,
                "none_count": counts["none"],
                "low_blue_signal_count": counts["low_blue_signal"],
                "marker_like_count": marker_like_count,
                "marker_like_rate": f"{(marker_like_count / crop_count if crop_count else 0.0):.8f}",
                "max_largest_blue_component_area": max_area,
            }
        )
    return summary_rows


def draw_review_sample(row: dict[str, object], output_path: Path) -> None:
    image = cv2.imread(str(row["crop_abs_path"]), cv2.IMREAD_COLOR)
    if image is None:
        raise AuditError(f"Could not reload crop for review sample: {row['output_file']}")

    for component in row["blue_components"]:
        if int(component["area"]) < MINIMUM_COMPONENT_AREA:
            continue
        x = int(component["x"])
        y = int(component["y"])
        width = int(component["width"])
        height = int(component["height"])
        cv2.rectangle(image, (x, y), (x + width - 1, y + height - 1), (0, 255, 255), 2)

    label_lines = [
        f"{row['output_file']}",
        f"label={row['label']} image_id={row['resolved_image_id']} split={row['dataset_split']}",
        f"largest_blue_component_area={row['largest_blue_component_area']}",
    ]
    y = 18
    for text in label_lines:
        cv2.putText(image, text, (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(image, text, (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        y += 18

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), image):
        raise AuditError(f"Could not write review sample: {output_path}")


def build_candidates(rows: list[dict[str, object]], review_dir: Path, sample_limit_per_group: int) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    emitted_by_group: Counter[tuple[str, str]] = Counter()

    for row in rows:
        if row["marker_contamination_status"] != "marker_like":
            continue
        group = (str(row["dataset_split"]), str(row["label"]))
        review_sample_path = ""
        if emitted_by_group[group] < sample_limit_per_group:
            emitted_by_group[group] += 1
            sample_name = f"{row['dataset_split']}_{row['label']}_{emitted_by_group[group]:03d}_{Path(str(row['output_file'])).stem}.jpg"
            sample_path = review_dir / sample_name
            draw_review_sample(row, sample_path)
            review_sample_path = str(sample_path)

        candidates.append(
            {
                "crop_path": row["output_file"],
                "image_id": row["resolved_image_id"],
                "source_image": row["resolved_source_image"],
                "dataset_split": row["dataset_split"],
                "crop_label": row["label"],
                "pass_fail_status": row["pass_fail_status"],
                "blue_pixel_count": row["blue_pixel_count"],
                "blue_pixel_fraction": row["blue_pixel_fraction"],
                "blue_component_count": row["blue_component_count"],
                "largest_blue_component_area": row["largest_blue_component_area"],
                "marker_like_component_count": row["marker_like_component_count"],
                "review_sample_path": review_sample_path,
                "recommended_action": RECOMMENDED_ACTION,
                "notes": "candidate only; blue region may be annotation marker or natural image content",
            }
        )
    return candidates


def report_text(summary: dict[str, object], summary_rows: list[dict[str, object]]) -> str:
    class_rates = {
        "dirty_positive": "0.00000000",
        "clean_negative": "0.00000000",
    }
    class_counts: dict[str, Counter[str]] = defaultdict(Counter)
    split_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in summary_rows:
        label = str(row["crop_label"])
        split = str(row["dataset_split"])
        class_counts[label]["crop_count"] += int(row["crop_count"])
        class_counts[label]["marker_like_count"] += int(row["marker_like_count"])
        split_counts[split]["crop_count"] += int(row["crop_count"])
        split_counts[split]["marker_like_count"] += int(row["marker_like_count"])
    for label, counts in class_counts.items():
        if counts["crop_count"]:
            class_rates[label] = f"{counts['marker_like_count'] / counts['crop_count']:.8f}"

    concentration = "ไม่พบ marker-like candidate"
    if summary["marker_like_count"]:
        dirty = int(summary["marker_like_dirty_positive_count"])
        clean = int(summary["marker_like_clean_negative_count"])
        if dirty and clean:
            concentration = "พบ marker-like candidate ทั้งใน dirty_positive และ clean_negative"
        elif dirty:
            concentration = "marker-like candidate กระจุกใน dirty_positive"
        elif clean:
            concentration = "marker-like candidate กระจุกใน clean_negative"

    split_lines = []
    for split in ["train", "validation", "test"]:
        counts = split_counts[split]
        split_lines.append(f"- {split}: crops {counts['crop_count']}, marker-like {counts['marker_like_count']}")

    return f"""# Crop Marker Leakage Audit

## วัตถุประสงค์
ตรวจว่า crop image ที่มีอยู่มี pixel หรือ component สีฟ้าที่คล้าย Blue Marker annotation หรือไม่ เพื่อป้องกันไม่ให้โมเดล classification ในอนาคตเรียนรู้ artifact จากการ annotate แทนสิ่งสกปรกจริง

## Logic ที่ใช้ตรวจ Blue Marker
ใช้ช่วงสี HSV จาก pipeline เดิม: lower {BLUE_HSV_LOWER}, upper {BLUE_HSV_UPPER}; mask ผ่าน MORPH_CLOSE ด้วย elliptical kernel 5x5 และนับ component ที่มีพื้นที่ตั้งแต่ {MINIMUM_COMPONENT_AREA} px เป็น marker-like candidate

## จำนวนที่ตรวจ
- Crops inspected: {summary['crop_count']}
- dirty_positive: {summary['dirty_positive_count']}
- clean_negative: {summary['clean_negative_count']}

## ผลตาม split
{chr(10).join(split_lines)}

## ผลตาม class
- dirty_positive marker-like rate: {class_rates['dirty_positive']}
- clean_negative marker-like rate: {class_rates['clean_negative']}
- การกระจุกตัว: {concentration}

## Candidate
- none: {summary['none_count']}
- low_blue_signal: {summary['low_blue_signal_count']}
- marker_like: {summary['marker_like_count']}
- marker-like rate: {summary['marker_like_rate']}

## Decision
{summary['decision']}

## Next Action
หาก decision เป็น MANUAL_REVIEW_REQUIRED ให้เปิด review samples และตรวจด้วยสายตาว่าพื้นที่สีฟ้าเป็น marker annotation หรือเป็นสีธรรมชาติของภาพ ก่อนนำ crop เหล่านี้ไปใช้ train model

No crop, source image, label, Ground Truth, or split manifest was modified.
No model was trained.
This audit detects marker-like blue regions; human review is required before treating a candidate as annotation leakage.
"""


def create_outputs(
    output_dir: Path,
    lineage_columns: list[str],
    rows: list[dict[str, object]],
    input_hashes: dict[str, str],
    sample_limit_per_group: int,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=False)
    review_dir = output_dir / "review_samples"
    review_dir.mkdir()

    manifest_path = output_dir / "crop_marker_leakage_manifest.csv"
    summary_csv_path = output_dir / "marker_leakage_summary.csv"
    candidates_path = output_dir / "marker_like_candidates.csv"
    summary_json_path = output_dir / "marker_leakage_summary.json"
    report_path = output_dir / "marker_leakage_report.md"

    manifest_columns = lineage_columns + [column for column in ADDED_MANIFEST_COLUMNS if column not in lineage_columns]
    public_rows = []
    for row in rows:
        public_rows.append({column: row.get(column, "") for column in manifest_columns})
    summary_rows = build_summary_rows(rows)
    candidates = build_candidates(rows, review_dir, sample_limit_per_group)

    write_csv(manifest_path, manifest_columns, public_rows)
    write_csv(summary_csv_path, SUMMARY_COLUMNS, summary_rows)
    write_csv(candidates_path, CANDIDATE_COLUMNS, candidates)

    split_counts = Counter(str(row["dataset_split"]) for row in rows)
    label_counts = Counter(str(row["label"]) for row in rows)
    status_counts = Counter(str(row["marker_contamination_status"]) for row in rows)
    marker_like_count = status_counts["marker_like"]
    decision = "SAFE_TO_TRAIN" if marker_like_count == 0 else "MANUAL_REVIEW_REQUIRED"

    summary = {
        "crop_count": len(rows),
        "train_crop_count": split_counts["train"],
        "validation_crop_count": split_counts["validation"],
        "test_crop_count": split_counts["test"],
        "dirty_positive_count": label_counts["dirty_positive"],
        "clean_negative_count": label_counts["clean_negative"],
        "none_count": status_counts["none"],
        "low_blue_signal_count": status_counts["low_blue_signal"],
        "marker_like_count": marker_like_count,
        "marker_like_dirty_positive_count": sum(1 for row in rows if row["label"] == "dirty_positive" and row["marker_contamination_status"] == "marker_like"),
        "marker_like_clean_negative_count": sum(1 for row in rows if row["label"] == "clean_negative" and row["marker_contamination_status"] == "marker_like"),
        "marker_like_rate": f"{(marker_like_count / len(rows) if rows else 0.0):.8f}",
        "decision": decision,
        "minimum_component_area": MINIMUM_COMPONENT_AREA,
        "blue_marker_detection_source": BLUE_MARKER_DETECTION_SOURCE,
        "input_file_hashes": input_hashes,
        "output_hash_scope": "primary_csv_artifacts_only",
        "output_file_hashes": {
            "crop_marker_leakage_manifest.csv": file_sha256(manifest_path),
            "marker_leakage_summary.csv": file_sha256(summary_csv_path),
            "marker_like_candidates.csv": file_sha256(candidates_path),
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    summary_json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(report_text(summary, summary_rows), encoding="utf-8")
    return summary


def audit_crop_marker_leakage(
    crops_dir: Path,
    lineage_manifest: Path,
    output_dir: Path,
    sample_limit_per_group: int,
    enforce_empty_output: bool = True,
) -> dict[str, object]:
    if enforce_empty_output:
        ensure_output_empty(output_dir)
    lineage_columns, rows, input_hashes = preflight_and_analyze(crops_dir, lineage_manifest)
    return create_outputs(output_dir, lineage_columns, rows, input_hashes, sample_limit_per_group)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit crop images for marker-like blue pixel leakage.")
    parser.add_argument("--crops-dir", type=Path, required=True)
    parser.add_argument("--lineage-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-limit-per-group", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        summary = audit_crop_marker_leakage(
            args.crops_dir,
            args.lineage_manifest,
            args.output_dir,
            args.sample_limit_per_group,
            enforce_empty_output=True,
        )
    except AuditError as exc:
        raise SystemExit(f"BLOCKED_BY_INPUT_ERROR: {exc}") from exc

    print(f"Crop marker leakage audit complete: {args.output_dir.resolve()}")
    print(f"Crop rows: {summary['crop_count']}")
    print(
        "Split crop counts: "
        f"train={summary['train_crop_count']} "
        f"validation={summary['validation_crop_count']} "
        f"test={summary['test_crop_count']}"
    )
    print(
        "Contamination status counts: "
        f"none={summary['none_count']} "
        f"low_blue_signal={summary['low_blue_signal_count']} "
        f"marker_like={summary['marker_like_count']}"
    )
    print(f"Decision: {summary['decision']}")


if __name__ == "__main__":
    main()
