from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "tmp" / "dataset_split"
SPLIT_POLICY_VERSION = "source_level_80_10_10_v1"
EXPECTED_SOURCE_COUNT = 15
EXPECTED_PASS_COUNT = 11
EXPECTED_FAIL_COUNT = 4
EXPECTED_REVIEW_COUNT = 0
APPROVED_ALLOCATION = {
    "train": {"PASS": 9, "FAIL": 3},
    "validation": {"PASS": 1, "FAIL": 0},
    "test": {"PASS": 1, "FAIL": 1},
}

SOURCE_SPLIT_COLUMNS = [
    "image_id",
    "source_image",
    "marked_image",
    "dataset_split",
    "stratification_group",
    "dirty_spot_count",
    "quality_score",
    "pass_fail_status",
    "ground_truth_status",
    "split_seed",
    "split_policy_version",
    "notes",
]

LEAKAGE_AUDIT_COLUMNS = [
    "image_id",
    "label_rows",
    "assigned_split",
    "distinct_split_count",
    "leakage_detected",
    "validation_result",
    "notes",
]

REQUIRED_LABEL_COLUMNS = [
    "image_id",
    "spot_id",
    "quality_score",
    "pass_fail_status",
    "review_status",
    "label_confidence",
    "ground_truth_stage",
]

REQUIRED_IMAGE_COLUMNS = [
    "image_id",
    "source_image",
    "marked_image",
    "dirty_spot_count",
    "quality_score",
    "pass_fail_status",
    "ground_truth_status",
]


class SplitError(ValueError):
    pass


@dataclass(frozen=True)
class SourceRecord:
    image_id: str
    source_image: str
    marked_image: str
    dirty_spot_count: int
    quality_score: int
    pass_fail_status: str
    ground_truth_status: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic source-level dataset split manifests from final ground truth."
    )
    parser.add_argument("--finalization-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, required=True)
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
        raise ValueError("Output directory must stay under tmp/dataset_split") from exc
    return output_dir


def ensure_output_empty(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SplitError(f"Output directory already contains files: {output_dir}")


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


def ensure_columns(columns: list[str], required: list[str], label: str) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise SplitError(f"{label} missing required columns: {', '.join(missing)}")


def image_sort_key(image_id: str) -> tuple[int, str]:
    return (int(image_id), image_id) if image_id.isdigit() else (10**9, image_id)


def load_inputs(finalization_dir: Path) -> tuple[list[str], list[dict[str, str]], list[dict[str, str]], dict[str, object], dict[str, str]]:
    manifest_path = finalization_dir / "final_ground_truth_manifest.csv"
    image_summary_path = finalization_dir / "final_image_quality_summary.csv"
    summary_path = finalization_dir / "finalization_summary.json"
    report_path = finalization_dir / "finalization_report.md"
    for path in (manifest_path, image_summary_path, summary_path, report_path):
        if not path.exists():
            raise FileNotFoundError(f"Required input missing: {path}")

    manifest_columns, manifest_rows = read_csv(manifest_path)
    _, image_rows = read_csv(image_summary_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    input_hashes = {
        "final_ground_truth_manifest.csv": file_sha256(manifest_path),
        "final_image_quality_summary.csv": file_sha256(image_summary_path),
        "finalization_summary.json": file_sha256(summary_path),
        "finalization_report.md": file_sha256(report_path),
    }
    return manifest_columns, manifest_rows, image_rows, summary, input_hashes


def validate_final_ground_truth(
    manifest_columns: list[str],
    manifest_rows: list[dict[str, str]],
    image_rows: list[dict[str, str]],
    finalization_summary: dict[str, object],
) -> list[SourceRecord]:
    ensure_columns(manifest_columns, REQUIRED_LABEL_COLUMNS, "final_ground_truth_manifest.csv")
    ensure_columns(list(image_rows[0].keys()) if image_rows else [], REQUIRED_IMAGE_COLUMNS, "final_image_quality_summary.csv")

    seen_labels: set[tuple[str, str]] = set()
    labels_by_image: dict[str, list[dict[str, str]]] = {}
    for row in manifest_rows:
        key = (row["image_id"], row["spot_id"])
        if key in seen_labels:
            raise SplitError(f"Duplicate label key found: {key[0]} / {key[1]}")
        seen_labels.add(key)
        if row["ground_truth_stage"] != "final":
            raise SplitError(f"Image {row['image_id']} label is not final")
        if row["review_status"] != "final_confirmed":
            raise SplitError(f"Image {row['image_id']} label review_status is not final_confirmed")
        if row["label_confidence"] != "human_verified_ground_truth":
            raise SplitError(f"Image {row['image_id']} label confidence is not human_verified_ground_truth")
        labels_by_image.setdefault(row["image_id"], []).append(row)

    records: list[SourceRecord] = []
    image_ids = {row["image_id"] for row in image_rows}
    if image_ids != {str(i) for i in range(1, 16)}:
        raise SplitError("Input image IDs must be exactly 1-15")

    for row in image_rows:
        image_id = row["image_id"]
        label_rows = labels_by_image.get(image_id, [])
        if len(label_rows) != int(row["dirty_spot_count"]):
            raise SplitError(f"Image {image_id}: label count does not match dirty_spot_count")
        label_statuses = {label["pass_fail_status"] for label in label_rows}
        label_counts = {label["quality_score"] for label in label_rows}
        if len(label_statuses) != 1 or row["pass_fail_status"] not in label_statuses:
            raise SplitError(f"Image {image_id}: inconsistent PASS/FAIL status")
        if len(label_counts) != 1 or row["quality_score"] not in label_counts:
            raise SplitError(f"Image {image_id}: inconsistent quality score")
        if row["ground_truth_status"] != "final_confirmed":
            raise SplitError(f"Image {image_id}: ground_truth_status is not final_confirmed")
        records.append(
            SourceRecord(
                image_id=image_id,
                source_image=row["source_image"],
                marked_image=row["marked_image"],
                dirty_spot_count=int(row["dirty_spot_count"]),
                quality_score=int(row["quality_score"]),
                pass_fail_status=row["pass_fail_status"],
                ground_truth_status=row["ground_truth_status"],
            )
        )

    pass_count = sum(1 for record in records if record.pass_fail_status == "PASS")
    fail_count = sum(1 for record in records if record.pass_fail_status == "FAIL")
    review_count = sum(1 for record in records if record.pass_fail_status == "REVIEW")
    if len(records) != EXPECTED_SOURCE_COUNT:
        raise SplitError(f"Expected {EXPECTED_SOURCE_COUNT} sources, found {len(records)}")
    if pass_count != EXPECTED_PASS_COUNT or fail_count != EXPECTED_FAIL_COUNT or review_count != EXPECTED_REVIEW_COUNT:
        raise SplitError(
            f"Expected PASS/FAIL/REVIEW {EXPECTED_PASS_COUNT}/{EXPECTED_FAIL_COUNT}/{EXPECTED_REVIEW_COUNT}, "
            f"found {pass_count}/{fail_count}/{review_count}"
        )
    if int(finalization_summary.get("total_dirty_spots", len(manifest_rows))) != len(manifest_rows):
        raise SplitError("Finalization summary total_dirty_spots does not match manifest rows")
    return sorted(records, key=lambda record: image_sort_key(record.image_id))


def build_assignments(records: list[SourceRecord], seed: int) -> dict[str, str]:
    grouped = {
        "PASS": [record for record in records if record.pass_fail_status == "PASS"],
        "FAIL": [record for record in records if record.pass_fail_status == "FAIL"],
    }
    rng = random.Random(seed)
    for values in grouped.values():
        values.sort(key=lambda record: image_sort_key(record.image_id))
        rng.shuffle(values)

    assignments: dict[str, str] = {}
    pass_records = grouped["PASS"]
    fail_records = grouped["FAIL"]
    split_plan = [
        ("train", pass_records[:9] + fail_records[:3]),
        ("validation", pass_records[9:10]),
        ("test", pass_records[10:11] + fail_records[3:4]),
    ]
    for split, split_records in split_plan:
        for record in split_records:
            assignments[record.image_id] = split
    if set(assignments) != {record.image_id for record in records}:
        raise SplitError("Split assignment did not cover every source image")
    return assignments


def split_report(summary: dict[str, object], assignments: dict[str, str]) -> str:
    by_split = {
        split: sorted([image_id for image_id, assigned in assignments.items() if assigned == split], key=image_sort_key)
        for split in ("train", "validation", "test")
    }
    return f"""# Source-level Dataset Split Report

## 1. Purpose

รอบนี้สร้าง source-level split manifests จาก final Ground Truth dataset โดยให้ทุก label จาก `image_id` เดียวกันอยู่ split เดียวกันเสมอ

## 2. Split Policy

- Split policy version: `{SPLIT_POLICY_VERSION}`
- Deterministic seed: `{summary['seed']}`
- TRAIN = 9 PASS + 3 FAIL = 12 source images
- VALIDATION = 1 PASS + 0 FAIL = 1 source image
- TEST = 1 PASS + 1 FAIL = 2 source images

## 3. Counts Per Split

- Train sources: {summary['train_source_count']}, labels: {summary['train_label_count']}
- Validation sources: {summary['validation_source_count']}, labels: {summary['validation_label_count']}
- Test sources: {summary['test_source_count']}, labels: {summary['test_label_count']}

## 4. PASS / FAIL Distribution

- Train: PASS {summary['train_pass_images']}, FAIL {summary['train_fail_images']}
- Validation: PASS {summary['validation_pass_images']}, FAIL {summary['validation_fail_images']}
- Test: PASS {summary['test_pass_images']}, FAIL {summary['test_fail_images']}

## 5. Source IDs

- Train: {', '.join(by_split['train'])}
- Validation: {', '.join(by_split['validation'])}
- Test: {', '.join(by_split['test'])}

## 6. Leakage Validation

Leakage detected: {summary['leakage_detected']}

ทุก source image มี `distinct_split_count = 1` ใน audit

## 7. Why Validation Has No FAIL Image

ชุดข้อมูลนี้มีเพียง 15 source images และ user-approved 80/10/10 split ทำให้ validation มีได้เพียง 1 source image จึงไม่สามารถแทนทั้ง PASS และ FAIL ได้พร้อมกัน โดย policy เลือกให้ FAIL ส่วนใหญ่ไป train และให้ test มีทั้ง PASS และ FAIL

## 8. Limitations

- 15 source images are not enough for reliable model-performance claims
- 1 validation source and 2 test sources are only suitable for pilot development
- future data collection should add more independent source images before any deployment decision

## 9. Explicit Statements

- No image pixels were read or modified.
- No labels were altered.
- No model was trained.
- All labels from one source image remain in one split.
"""


def create_outputs(
    output_dir: Path,
    manifest_columns: list[str],
    manifest_rows: list[dict[str, str]],
    records: list[SourceRecord],
    assignments: dict[str, str],
    seed: int,
    input_hashes: dict[str, str],
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    label_counts_by_image: dict[str, int] = {}
    for row in manifest_rows:
        label_counts_by_image[row["image_id"]] = label_counts_by_image.get(row["image_id"], 0) + 1

    source_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    for record in records:
        split = assignments[record.image_id]
        source_rows.append(
            {
                "image_id": record.image_id,
                "source_image": record.source_image,
                "marked_image": record.marked_image,
                "dataset_split": split,
                "stratification_group": record.pass_fail_status,
                "dirty_spot_count": record.dirty_spot_count,
                "quality_score": record.quality_score,
                "pass_fail_status": record.pass_fail_status,
                "ground_truth_status": "final_confirmed",
                "split_seed": seed,
                "split_policy_version": SPLIT_POLICY_VERSION,
                "notes": "source-level split; all labels from this image_id stay together",
            }
        )
        audit_rows.append(
            {
                "image_id": record.image_id,
                "label_rows": label_counts_by_image.get(record.image_id, 0),
                "assigned_split": split,
                "distinct_split_count": 1,
                "leakage_detected": "false",
                "validation_result": "pass",
                "notes": "all labels for image_id assigned to one split",
            }
        )

    final_columns = manifest_columns + [
        column for column in ("dataset_split", "split_seed", "split_policy_version") if column not in manifest_columns
    ]
    final_rows: list[dict[str, object]] = []
    for row in manifest_rows:
        new_row: dict[str, object] = dict(row)
        new_row["dataset_split"] = assignments[row["image_id"]]
        new_row["split_seed"] = seed
        new_row["split_policy_version"] = SPLIT_POLICY_VERSION
        final_rows.append(new_row)

    source_path = output_dir / "source_split_manifest.csv"
    final_path = output_dir / "final_ground_truth_with_split.csv"
    audit_path = output_dir / "split_leakage_audit.csv"
    summary_path = output_dir / "split_summary.json"
    report_path = output_dir / "split_report.md"
    write_csv(source_path, SOURCE_SPLIT_COLUMNS, source_rows)
    write_csv(final_path, final_columns, final_rows)
    write_csv(audit_path, LEAKAGE_AUDIT_COLUMNS, audit_rows)

    def count_sources(split: str, status: str | None = None) -> int:
        return sum(
            1
            for record in records
            if assignments[record.image_id] == split and (status is None or record.pass_fail_status == status)
        )

    def count_labels(split: str) -> int:
        return sum(1 for row in final_rows if row["dataset_split"] == split)

    created_at = datetime.now().isoformat(timespec="seconds")
    output_hashes = {
        "source_split_manifest.csv": file_sha256(source_path),
        "final_ground_truth_with_split.csv": file_sha256(final_path),
        "split_leakage_audit.csv": file_sha256(audit_path),
    }
    summary: dict[str, object] = {
        "seed": seed,
        "split_policy_version": SPLIT_POLICY_VERSION,
        "source_image_count": len(records),
        "label_count": len(final_rows),
        "train_source_count": count_sources("train"),
        "validation_source_count": count_sources("validation"),
        "test_source_count": count_sources("test"),
        "train_label_count": count_labels("train"),
        "validation_label_count": count_labels("validation"),
        "test_label_count": count_labels("test"),
        "train_pass_images": count_sources("train", "PASS"),
        "train_fail_images": count_sources("train", "FAIL"),
        "validation_pass_images": count_sources("validation", "PASS"),
        "validation_fail_images": count_sources("validation", "FAIL"),
        "test_pass_images": count_sources("test", "PASS"),
        "test_fail_images": count_sources("test", "FAIL"),
        "leakage_detected": False,
        "input_file_hashes": input_hashes,
        "output_file_hashes": output_hashes,
        "created_at": created_at,
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    output_hashes["split_summary.json"] = file_sha256(summary_path)
    summary["output_file_hashes"] = output_hashes
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(split_report(summary, assignments), encoding="utf-8")
    return summary


def build_source_level_split(finalization_dir: Path, output_dir: Path, seed: int, enforce_empty_output: bool = True) -> dict[str, object]:
    if enforce_empty_output:
        ensure_output_empty(output_dir)
    manifest_columns, manifest_rows, image_rows, finalization_summary, input_hashes = load_inputs(finalization_dir)
    records = validate_final_ground_truth(manifest_columns, manifest_rows, image_rows, finalization_summary)
    assignments = build_assignments(records, seed)
    return create_outputs(output_dir, manifest_columns, manifest_rows, records, assignments, seed, input_hashes)


def main() -> None:
    args = parse_args()
    finalization_dir = resolve_project_path(args.finalization_dir)
    output_dir = resolve_output_dir(args.output_dir)
    summary = build_source_level_split(finalization_dir, output_dir, args.seed)
    print(f"Dataset split complete: {output_dir}")
    print(
        "Source counts: "
        f"train={summary['train_source_count']} "
        f"validation={summary['validation_source_count']} "
        f"test={summary['test_source_count']}"
    )
    print(
        "Label counts: "
        f"train={summary['train_label_count']} "
        f"validation={summary['validation_label_count']} "
        f"test={summary['test_label_count']}"
    )


if __name__ == "__main__":
    main()
