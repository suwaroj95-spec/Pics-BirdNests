from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "tmp" / "ground_truth_finalization"
RADIUS_MIN = 16.0
RADIUS_MAX = 50.0
AUTOMATIC_MERGE_ENABLED = False

REQUIRED_MANIFEST_COLUMNS = [
    "image_id",
    "spot_id",
    "x_center",
    "y_center",
    "radius",
    "enclosing_circle_radius",
    "quality_score",
    "pass_fail_status",
    "manually_verified_alignment",
    "alignment_note",
    "label_confidence",
    "review_status",
]

FINAL_EXTRA_COLUMNS = [
    "preliminary_preview_radius",
    "preview_radius",
    "ground_truth_stage",
    "finalization_run_id",
    "finalized_at",
]

IMAGE_SUMMARY_EXTRA_COLUMNS = [
    "ground_truth_status",
    "preview_confirmation",
    "finalization_run_id",
    "finalized_at",
]

REVIEW_AUDIT_COLUMNS = [
    "image_id",
    "previous_review_status",
    "final_review_status",
    "preview_confirmed",
    "manually_verified_alignment",
    "alignment_note",
    "resolution",
    "resolution_source",
    "notes",
]

RADIUS_AUDIT_COLUMNS = [
    "image_id",
    "spot_id",
    "preliminary_preview_radius",
    "raw_enclosing_circle_radius",
    "final_ground_truth_radius",
    "preview_radius",
    "radius_changed_from_preliminary",
]


class FinalizationError(ValueError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize human-verified preliminary ground-truth labels without re-detecting markers."
    )
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--confirm-all-previews", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-id", default="")
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
        raise ValueError("Output directory must stay under tmp/ground_truth_finalization") from exc
    return output_dir


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


def clamp_preview_radius(radius: float) -> float:
    return round(max(RADIUS_MIN, min(float(radius), RADIUS_MAX)), 4)


def parse_positive_float(value: str, field_name: str, row_number: int) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise FinalizationError(f"Row {row_number}: {field_name} must be numeric") from exc
    if parsed <= 0:
        raise FinalizationError(f"Row {row_number}: {field_name} must be greater than zero")
    return parsed


def parse_float(value: str, field_name: str, row_number: int) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise FinalizationError(f"Row {row_number}: {field_name} must be numeric") from exc


def quality_grade(spot_count: int) -> tuple[int, str]:
    if spot_count <= 9:
        return 95, "PASS"
    if spot_count <= 20:
        return 90, "PASS"
    if spot_count <= 30:
        return 80, "PASS"
    return 70, "FAIL"


def ensure_columns(columns: list[str], required: list[str], label: str) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise FinalizationError(f"{label} missing required columns: {', '.join(missing)}")


def alignment_note_for(image_id: str, existing: str) -> str:
    required = (
        "non-identical frame; visually verified marker-to-defect correspondence"
        if image_id in {"1", "2"}
        else "visually verified marker-to-defect correspondence"
    )
    if required in existing:
        return existing
    if not existing:
        return required
    return f"{existing}; {required}"


def validate_inputs(
    manifest_columns: list[str],
    manifest_rows: list[dict[str, str]],
    image_rows: list[dict[str, str]],
    generation_summary: dict[str, object],
) -> None:
    ensure_columns(manifest_columns, REQUIRED_MANIFEST_COLUMNS, "ground_truth_manifest.csv")
    ensure_columns(
        list(image_rows[0].keys()) if image_rows else [],
        ["image_id", "dirty_spot_count", "quality_score", "pass_fail_status", "review_status"],
        "image_quality_summary.csv",
    )

    seen: set[tuple[str, str]] = set()
    counts: dict[str, int] = {}
    for row_number, row in enumerate(manifest_rows, start=2):
        key = (row["image_id"], row["spot_id"])
        if key in seen:
            raise FinalizationError(f"Duplicate label key found: {key[0]} / {key[1]}")
        seen.add(key)
        counts[row["image_id"]] = counts.get(row["image_id"], 0) + 1

        parse_float(row["x_center"], "x_center", row_number)
        parse_float(row["y_center"], "y_center", row_number)
        parse_positive_float(row["enclosing_circle_radius"], "enclosing_circle_radius", row_number)

        score = int(row["quality_score"])
        status = row["pass_fail_status"]
        expected_score, expected_status = quality_grade(counts[row["image_id"]])
        # Per-row image totals are checked after all counts are known.
        if status not in {"PASS", "FAIL", "REVIEW"}:
            raise FinalizationError(f"Row {row_number}: invalid pass_fail_status {status}")
        if score not in {70, 80, 90, 95}:
            raise FinalizationError(f"Row {row_number}: invalid quality_score {score}")
        _ = expected_score, expected_status

    for row in image_rows:
        image_id = row["image_id"]
        actual_count = counts.get(image_id, 0)
        declared_count = int(row["dirty_spot_count"])
        if actual_count != declared_count:
            raise FinalizationError(f"Image {image_id}: manifest count {actual_count} != summary count {declared_count}")
        expected_score, expected_status = quality_grade(declared_count)
        if int(row["quality_score"]) != expected_score or row["pass_fail_status"] != expected_status:
            raise FinalizationError(f"Image {image_id}: score/status does not match approved policy")

    for row_number, row in enumerate(manifest_rows, start=2):
        image_id = row["image_id"]
        expected_score, expected_status = quality_grade(counts[image_id])
        if int(row["quality_score"]) != expected_score or row["pass_fail_status"] != expected_status:
            raise FinalizationError(f"Row {row_number}: row score/status does not match image spot count")

    if generation_summary.get("automatic_merge_enabled") is not False:
        raise FinalizationError("Input generation summary must have automatic_merge_enabled=false")
    if int(generation_summary.get("total_dirty_spots", len(manifest_rows))) != len(manifest_rows):
        raise FinalizationError("Input row count does not match generation_summary total_dirty_spots")


def build_final_rows(
    manifest_columns: list[str],
    manifest_rows: list[dict[str, str]],
    image_columns: list[str],
    image_rows: list[dict[str, str]],
    review_rows: list[dict[str, str]],
    run_id: str,
    finalized_at: str,
) -> tuple[list[str], list[dict[str, object]], list[str], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    final_columns = manifest_columns + [column for column in FINAL_EXTRA_COLUMNS if column not in manifest_columns]
    final_manifest_rows: list[dict[str, object]] = []
    radius_audit_rows: list[dict[str, object]] = []

    for row in manifest_rows:
        preliminary_radius = float(row["radius"])
        raw_radius = float(row["enclosing_circle_radius"])
        preview_radius = clamp_preview_radius(raw_radius)
        final_row: dict[str, object] = dict(row)
        final_row["radius"] = round(raw_radius, 4)
        final_row["preliminary_preview_radius"] = row["radius"]
        final_row["preview_radius"] = preview_radius
        final_row["label_confidence"] = "human_verified_ground_truth"
        final_row["review_status"] = "final_confirmed"
        final_row["manually_verified_alignment"] = "true"
        final_row["alignment_note"] = alignment_note_for(row["image_id"], row.get("alignment_note", ""))
        final_row["ground_truth_stage"] = "final"
        final_row["finalization_run_id"] = run_id
        final_row["finalized_at"] = finalized_at
        final_manifest_rows.append(final_row)
        radius_audit_rows.append(
            {
                "image_id": row["image_id"],
                "spot_id": row["spot_id"],
                "preliminary_preview_radius": row["radius"],
                "raw_enclosing_circle_radius": row["enclosing_circle_radius"],
                "final_ground_truth_radius": round(raw_radius, 4),
                "preview_radius": preview_radius,
                "radius_changed_from_preliminary": str(abs(preliminary_radius - raw_radius) > 1e-9).lower(),
            }
        )

    final_image_columns = image_columns + [column for column in IMAGE_SUMMARY_EXTRA_COLUMNS if column not in image_columns]
    final_image_rows: list[dict[str, object]] = []
    review_by_image = {row["image_id"]: row for row in review_rows}
    review_audit_rows: list[dict[str, object]] = []

    for row in image_rows:
        final_row: dict[str, object] = dict(row)
        final_row["manually_verified_alignment"] = "true"
        final_row["alignment_note"] = alignment_note_for(row["image_id"], row.get("alignment_note", ""))
        final_row["review_status"] = "final_confirmed"
        final_row["ground_truth_status"] = "final_confirmed"
        final_row["preview_confirmation"] = "true"
        final_row["finalization_run_id"] = run_id
        final_row["finalized_at"] = finalized_at
        final_image_rows.append(final_row)

        previous_review_status = review_by_image.get(row["image_id"], {}).get(
            "notes",
            row.get("review_status", ""),
        )
        review_audit_rows.append(
            {
                "image_id": row["image_id"],
                "previous_review_status": previous_review_status,
                "final_review_status": "resolved",
                "preview_confirmed": "true",
                "manually_verified_alignment": "true",
                "alignment_note": final_row["alignment_note"],
                "resolution": "final_confirmed",
                "resolution_source": "user_manual_confirmation",
                "notes": "human preview confirmation applied to preliminary labels",
            }
        )

    return (
        final_columns,
        final_manifest_rows,
        final_image_columns,
        final_image_rows,
        review_audit_rows,
        radius_audit_rows,
    )


def finalization_report(summary: dict[str, object]) -> str:
    return f"""# Final Ground Truth Finalization Report

## 1. Purpose

รอบนี้ finalize preliminary ground-truth labels ที่ผู้ใช้ตรวจ preview แล้ว ให้เป็น final dataset version สำหรับใช้ใน Ground Truth ระยะถัดไป

## 2. Final Policy Used

- 1 Blue Marker = 1 dirty spot
- 1 dirty cluster = 1 label
- Minimum blue-component area = 20 px
- Automatic marker merge = disabled
- Quality policy: 0-9 = 95/PASS, 10-20 = 90/PASS, 21-30 = 80/PASS, 31+ = 70/FAIL, unreadable = REVIEW

## 3. Radius Policy

Final Ground Truth radius ใช้ raw `enclosing_circle_radius` จาก Blue Marker เป็น authoritative radius ทุกแถว

`preview_radius = clamp(final radius, 16, 50)` ใช้สำหรับ preview/UI เท่านั้น ไม่ใช่ segmentation mask และไม่แทนค่า final radius

## 4. Record Counts

- Input manifest rows: {summary['input_manifest_rows']}
- Final manifest rows: {summary['final_manifest_rows']}
- Input image count: {summary['input_image_count']}
- Final image count: {summary['final_image_count']}
- Total dirty spots: {summary['total_dirty_spots']}

## 5. PASS / FAIL / REVIEW Summary

- PASS images: {summary['pass_images']}
- FAIL images: {summary['fail_images']}
- REVIEW images: {summary['review_images']}
- Final confirmed images: {summary['final_confirmed_images']}
- Labels final confirmed: {summary['labels_final_confirmed']}

## 6. Image 1 and 2 Provenance

ภาพ 1 และ 2 ถูกบันทึก alignment note ว่า `non-identical frame; visually verified marker-to-defect correspondence`

## 7. Radius Migration Summary

- Raw-radius labels: {summary['raw_radius_labels']}
- Preview radii clamped low: {summary['preview_clamped_low_count']}
- Preview radii clamped high: {summary['preview_clamped_high_count']}
- Labels whose final radius differs from preliminary preview radius: {summary['radius_changed_from_preliminary_count']}

## 8. Validation Results

- Required manifest columns validated
- `(image_id, spot_id)` uniqueness validated
- Numeric x/y and raw radius validated
- Quality score and PASS/FAIL mapping validated
- Input row count preserved exactly
- Automatic merge disabled validated

## 9. Explicit Statements

- Final Ground Truth labels were created from human-verified preliminary labels.
- No Blue Marker detection was rerun.
- No original or marked image was modified.
- No model was trained.
"""


def summarize(
    final_manifest_rows: list[dict[str, object]],
    final_image_rows: list[dict[str, object]],
    radius_audit_rows: list[dict[str, object]],
    input_hashes: dict[str, str],
    output_hashes: dict[str, str],
    created_at: str,
) -> dict[str, object]:
    return {
        "input_manifest_rows": len(final_manifest_rows),
        "final_manifest_rows": len(final_manifest_rows),
        "input_image_count": len(final_image_rows),
        "final_image_count": len(final_image_rows),
        "total_dirty_spots": len(final_manifest_rows),
        "pass_images": sum(1 for row in final_image_rows if row["pass_fail_status"] == "PASS"),
        "fail_images": sum(1 for row in final_image_rows if row["pass_fail_status"] == "FAIL"),
        "review_images": sum(1 for row in final_image_rows if row["pass_fail_status"] == "REVIEW"),
        "final_confirmed_images": sum(1 for row in final_image_rows if row["ground_truth_status"] == "final_confirmed"),
        "labels_final_confirmed": sum(1 for row in final_manifest_rows if row["review_status"] == "final_confirmed"),
        "raw_radius_labels": sum(
            1
            for row in final_manifest_rows
            if abs(float(row["radius"]) - float(row["enclosing_circle_radius"])) < 1e-9
        ),
        "preview_clamped_low_count": sum(
            1 for row in radius_audit_rows if float(row["raw_enclosing_circle_radius"]) < RADIUS_MIN
        ),
        "preview_clamped_high_count": sum(
            1 for row in radius_audit_rows if float(row["raw_enclosing_circle_radius"]) > RADIUS_MAX
        ),
        "radius_changed_from_preliminary_count": sum(
            1 for row in radius_audit_rows if row["radius_changed_from_preliminary"] == "true"
        ),
        "automatic_merge_enabled": AUTOMATIC_MERGE_ENABLED,
        "input_file_hashes": input_hashes,
        "output_file_hashes": output_hashes,
        "created_at": created_at,
    }


def finalize_ground_truth(input_dir: Path, output_dir: Path, confirm_all_previews: bool, run_id: str = "") -> dict[str, object]:
    if not confirm_all_previews:
        raise FinalizationError("--confirm-all-previews is required before finalization")

    manifest_path = input_dir / "ground_truth_manifest.csv"
    image_summary_path = input_dir / "image_quality_summary.csv"
    review_queue_path = input_dir / "review_queue.csv"
    generation_summary_path = input_dir / "generation_summary.json"
    for path in (manifest_path, image_summary_path, review_queue_path, generation_summary_path):
        if not path.exists():
            raise FileNotFoundError(f"Required input missing: {path}")

    manifest_columns, manifest_rows = read_csv(manifest_path)
    image_columns, image_rows = read_csv(image_summary_path)
    _, review_rows = read_csv(review_queue_path)
    generation_summary = json.loads(generation_summary_path.read_text(encoding="utf-8"))
    validate_inputs(manifest_columns, manifest_rows, image_rows, generation_summary)

    finalized_at = datetime.now().isoformat(timespec="seconds")
    finalization_run_id = run_id or f"final_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    (
        final_columns,
        final_manifest_rows,
        final_image_columns,
        final_image_rows,
        review_audit_rows,
        radius_audit_rows,
    ) = build_final_rows(
        manifest_columns,
        manifest_rows,
        image_columns,
        image_rows,
        review_rows,
        finalization_run_id,
        finalized_at,
    )

    if len(final_manifest_rows) != len(manifest_rows):
        raise FinalizationError("Final manifest row count changed unexpectedly")

    input_hashes = {
        "ground_truth_manifest.csv": file_sha256(manifest_path),
        "image_quality_summary.csv": file_sha256(image_summary_path),
        "review_queue.csv": file_sha256(review_queue_path),
        "generation_summary.json": file_sha256(generation_summary_path),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    final_manifest_path = output_dir / "final_ground_truth_manifest.csv"
    final_image_path = output_dir / "final_image_quality_summary.csv"
    review_audit_path = output_dir / "review_resolution_audit.csv"
    radius_audit_path = output_dir / "radius_migration_audit.csv"
    summary_path = output_dir / "finalization_summary.json"
    report_path = output_dir / "finalization_report.md"

    write_csv(final_manifest_path, final_columns, final_manifest_rows)
    write_csv(final_image_path, final_image_columns, final_image_rows)
    write_csv(review_audit_path, REVIEW_AUDIT_COLUMNS, review_audit_rows)
    write_csv(radius_audit_path, RADIUS_AUDIT_COLUMNS, radius_audit_rows)

    output_hashes = {
        "final_ground_truth_manifest.csv": file_sha256(final_manifest_path),
        "final_image_quality_summary.csv": file_sha256(final_image_path),
        "review_resolution_audit.csv": file_sha256(review_audit_path),
        "radius_migration_audit.csv": file_sha256(radius_audit_path),
    }
    summary = summarize(
        final_manifest_rows,
        final_image_rows,
        radius_audit_rows,
        input_hashes,
        output_hashes,
        finalized_at,
    )
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    output_hashes["finalization_summary.json"] = file_sha256(summary_path)
    summary["output_file_hashes"] = output_hashes
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(finalization_report(summary), encoding="utf-8")
    return summary


def main() -> None:
    args = parse_args()
    input_dir = resolve_project_path(args.input_dir)
    output_dir = resolve_output_dir(args.output_dir)
    if args.dry_run:
        if not args.confirm_all_previews:
            raise FinalizationError("--confirm-all-previews is required before finalization")
        print(f"Dry run only. Input directory exists: {input_dir.exists()}")
        return

    summary = finalize_ground_truth(
        input_dir,
        output_dir,
        confirm_all_previews=args.confirm_all_previews,
        run_id=args.run_id,
    )
    print(f"Finalization complete: {output_dir}")
    print(f"Final labels: {summary['final_manifest_rows']}")
    print(
        "Image status counts: "
        f"PASS={summary['pass_images']} FAIL={summary['fail_images']} REVIEW={summary['review_images']}"
    )
    print(
        "Radius migration: "
        f"changed={summary['radius_changed_from_preliminary_count']} "
        f"low_clamp={summary['preview_clamped_low_count']} "
        f"high_clamp={summary['preview_clamped_high_count']}"
    )


if __name__ == "__main__":
    main()
