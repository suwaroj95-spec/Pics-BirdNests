from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "tmp" / "crop_lineage_audit"

LINEAGE_COLUMNS = [
    "resolved_image_id",
    "resolved_source_image",
    "dataset_split",
    "pass_fail_status",
    "lineage_status",
    "traceability_level",
    "audit_notes",
]

SPLIT_SUMMARY_COLUMNS = [
    "dataset_split",
    "crop_category",
    "pass_fail_status",
    "source_image_count",
    "crop_count",
]

LEAKAGE_AUDIT_COLUMNS = [
    "image_id",
    "source_image",
    "crop_count",
    "distinct_split_count",
    "leakage_detected",
    "validation_result",
    "notes",
]

DIRTY_TRACE_COLUMNS = [
    "crop_path",
    "resolved_image_id",
    "resolved_source_image",
    "spot_id",
    "traceability_level",
    "match_method",
    "validation_result",
    "notes",
]


class LineageAuditError(ValueError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only audit of crop dataset lineage against source-level split.")
    parser.add_argument("--crops-dir", required=True)
    parser.add_argument("--split-dir", required=True)
    parser.add_argument("--finalization-dir", required=True)
    parser.add_argument("--output-dir", required=True)
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
        raise ValueError("Output directory must stay under tmp/crop_lineage_audit") from exc
    return output_dir


def ensure_output_empty(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise LineageAuditError(f"Output directory already contains files: {output_dir}")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
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


def normalize_image_id(value: str) -> str:
    value = str(value).strip()
    if value.endswith(".jpg") or value.endswith(".jpeg") or value.endswith(".png"):
        value = Path(value).stem
    if value.endswith("m") and value[:-1].isdigit():
        value = value[:-1]
    return str(int(value)) if value.isdigit() else value


def required_columns(columns: list[str], required: list[str], label: str) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise LineageAuditError(f"{label} missing required columns: {', '.join(missing)}")


def load_inputs(crops_dir: Path, split_dir: Path, finalization_dir: Path) -> dict[str, object]:
    paths = {
        "crop_metadata": crops_dir / "metadata.csv",
        "source_split": split_dir / "source_split_manifest.csv",
        "final_with_split": split_dir / "final_ground_truth_with_split.csv",
        "split_summary": split_dir / "split_summary.json",
        "final_manifest": finalization_dir / "final_ground_truth_manifest.csv",
        "final_image_summary": finalization_dir / "final_image_quality_summary.csv",
    }
    for path in paths.values():
        if not path.exists():
            raise FileNotFoundError(f"Required input missing: {path}")

    crop_columns, crop_rows = read_csv(paths["crop_metadata"])
    split_columns, split_rows = read_csv(paths["source_split"])
    final_columns, final_rows = read_csv(paths["final_manifest"])
    final_image_columns, final_image_rows = read_csv(paths["final_image_summary"])
    final_split_columns, final_split_rows = read_csv(paths["final_with_split"])
    split_summary = json.loads(paths["split_summary"].read_text(encoding="utf-8"))

    required_columns(crop_columns, ["source_id", "source_image", "output_file", "label"], "Crops/metadata.csv")
    required_columns(split_columns, ["image_id", "source_image", "dataset_split", "pass_fail_status"], "source_split_manifest.csv")
    required_columns(final_columns, ["image_id", "spot_id"], "final_ground_truth_manifest.csv")
    required_columns(final_image_columns, ["image_id", "pass_fail_status"], "final_image_quality_summary.csv")
    required_columns(final_split_columns, ["image_id", "dataset_split"], "final_ground_truth_with_split.csv")

    input_hashes = {name: file_sha256(path) for name, path in paths.items()}
    return {
        "crop_columns": crop_columns,
        "crop_rows": crop_rows,
        "split_rows": split_rows,
        "final_rows": final_rows,
        "final_image_rows": final_image_rows,
        "final_split_rows": final_split_rows,
        "split_summary": split_summary,
        "input_hashes": input_hashes,
    }


def final_spot_lookup(final_rows: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(row["image_id"], row["spot_id"]) for row in final_rows}


def candidate_spot_id(image_id: str, dirty_spot_id: str) -> str:
    value = str(dirty_spot_id).strip()
    if not value:
        return ""
    if value.isdigit():
        return f"{image_id}_spot_{int(value):03d}"
    return value


def build_lineage(
    crop_columns: list[str],
    crop_rows: list[dict[str, str]],
    split_rows: list[dict[str, str]],
    final_rows: list[dict[str, str]],
    final_image_rows: list[dict[str, str]],
    final_split_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    split_by_id = {row["image_id"]: row for row in split_rows}
    final_image_ids = {row["image_id"] for row in final_image_rows}
    split_image_ids = {row["image_id"] for row in split_rows}
    final_split_ids = {row["image_id"] for row in final_split_rows}
    if final_image_ids != split_image_ids or final_image_ids != final_split_ids:
        raise LineageAuditError("Final Ground Truth image IDs and split manifest image IDs do not agree")

    final_spots = final_spot_lookup(final_rows)
    output_counts = Counter(row.get("output_file", "") for row in crop_rows)
    lineage_rows: list[dict[str, object]] = []
    dirty_trace_rows: list[dict[str, object]] = []
    unresolved = 0

    for row in crop_rows:
        image_id = normalize_image_id(row.get("source_id") or row.get("source_image", ""))
        split = split_by_id.get(image_id)
        notes: list[str] = []
        lineage_status = "resolved"
        traceability = "source-level only"
        if not image_id or split is None:
            lineage_status = "unresolved"
            traceability = "not traceable"
            unresolved += 1
            notes.append("unknown image_id or missing split assignment")
        if output_counts[row.get("output_file", "")] > 1:
            lineage_status = "warning"
            notes.append("duplicate crop path appears in metadata")

        label = row.get("label", "")
        spot_id = ""
        match_method = ""
        validation_result = "pass"
        trace_notes = ""
        if label == "dirty_positive":
            spot_id = candidate_spot_id(image_id, row.get("dirty_spot_id", ""))
            if spot_id and (image_id, spot_id) in final_spots:
                traceability = "exact"
                match_method = "source_id + dirty_spot_id -> final spot_id"
                trace_notes = "dirty_spot_id maps to final Ground Truth spot_id"
            else:
                traceability = "source-level only" if lineage_status != "unresolved" else "not traceable"
                match_method = "source_id only" if lineage_status != "unresolved" else ""
                validation_result = "warning" if lineage_status != "unresolved" else "fail"
                spot_id = ""
                trace_notes = "no exact final spot_id evidence in metadata"
            dirty_trace_rows.append(
                {
                    "crop_path": row.get("output_file", ""),
                    "resolved_image_id": image_id,
                    "resolved_source_image": row.get("source_image", ""),
                    "spot_id": spot_id,
                    "traceability_level": traceability,
                    "match_method": match_method,
                    "validation_result": validation_result,
                    "notes": trace_notes,
                }
            )
        elif label == "clean_negative":
            traceability = "source-level only" if lineage_status != "unresolved" else "not traceable"
            notes.append("clean-negative source split is traceable; defect-free status is not re-proven by this audit")

        enriched = dict(row)
        enriched.update(
            {
                "resolved_image_id": image_id,
                "resolved_source_image": row.get("source_image", ""),
                "dataset_split": "" if split is None else split["dataset_split"],
                "pass_fail_status": "" if split is None else split["pass_fail_status"],
                "lineage_status": lineage_status,
                "traceability_level": traceability,
                "audit_notes": "; ".join(notes),
            }
        )
        lineage_rows.append(enriched)

    split_sets_by_image: dict[str, set[str]] = defaultdict(set)
    crop_counts_by_image: Counter[str] = Counter()
    source_image_by_id: dict[str, str] = {}
    for row in lineage_rows:
        image_id = str(row["resolved_image_id"])
        if not image_id:
            continue
        crop_counts_by_image[image_id] += 1
        source_image_by_id[image_id] = str(row["resolved_source_image"])
        if row["dataset_split"]:
            split_sets_by_image[image_id].add(str(row["dataset_split"]))

    leakage_rows: list[dict[str, object]] = []
    for image_id in sorted(split_image_ids, key=lambda value: int(value) if value.isdigit() else 10**9):
        distinct_count = len(split_sets_by_image.get(image_id, set()))
        leakage = distinct_count > 1
        missing = crop_counts_by_image.get(image_id, 0) == 0
        leakage_rows.append(
            {
                "image_id": image_id,
                "source_image": source_image_by_id.get(image_id, split_by_id[image_id]["source_image"]),
                "crop_count": crop_counts_by_image.get(image_id, 0),
                "distinct_split_count": distinct_count,
                "leakage_detected": str(leakage).lower(),
                "validation_result": "fail" if leakage or missing else "pass",
                "notes": "all crops for image_id map to one split" if not leakage and not missing else "missing crops or split leakage",
            }
        )

    summary_counter: Counter[tuple[str, str, str]] = Counter()
    sources_by_group: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in lineage_rows:
        key = (str(row["dataset_split"]), row.get("label", ""), str(row["pass_fail_status"]))
        summary_counter[key] += 1
        if row["resolved_image_id"]:
            sources_by_group[key].add(str(row["resolved_image_id"]))
    split_summary_rows = [
        {
            "dataset_split": key[0],
            "crop_category": key[1],
            "pass_fail_status": key[2],
            "source_image_count": len(sources_by_group[key]),
            "crop_count": count,
        }
        for key, count in sorted(summary_counter.items())
    ]

    stats = {
        "unresolved": unresolved,
        "duplicate_crop_paths": sum(1 for path, count in output_counts.items() if path and count > 1),
    }
    return lineage_rows, split_summary_rows, leakage_rows, dirty_trace_rows, stats


def decide_reuse(
    lineage_rows: list[dict[str, object]],
    leakage_rows: list[dict[str, object]],
    dirty_trace_rows: list[dict[str, object]],
    duplicate_crop_paths: int,
) -> str:
    if any(row["lineage_status"] == "unresolved" for row in lineage_rows):
        return "INSUFFICIENT_LINEAGE"
    if any(row["leakage_detected"] == "true" for row in leakage_rows):
        return "REBUILD_REQUIRED"
    if duplicate_crop_paths:
        return "REUSE_WITH_SPLIT_MANIFEST_ONLY"
    if any(row["traceability_level"] != "exact" for row in dirty_trace_rows):
        return "REUSE_WITH_SPLIT_MANIFEST_ONLY"
    return "REUSE_AS_IS"


def report_text(
    crop_columns: list[str],
    summary: dict[str, object],
    reuse_decision: str,
) -> str:
    blockers = []
    if summary["unresolved_crop_rows"]:
        blockers.append("มี crop rows ที่ resolve source image ไม่ได้")
    if summary["leakage_detected"]:
        blockers.append("พบ split leakage")
    if summary["untraceable_dirty_positive_count"]:
        blockers.append("มี dirty-positive crop ที่ map spot แบบ exact ไม่ได้")
    if not blockers:
        blockers.append("ไม่พบ blocker สำหรับการ reuse ตาม split manifest ปัจจุบัน")
    return f"""# Crop Dataset Lineage Audit Report

## 1. Purpose

ตรวจสอบว่า crop dataset เดิมใน `Crops/metadata.csv` สามารถ trace กลับไปยัง source image และ source-level split ที่ finalized แล้วได้อย่างปลอดภัยหรือไม่ โดยไม่อ่าน image pixels และไม่แก้ไฟล์ข้อมูลเดิม

## 2. Actual Metadata Columns Found

`{', '.join(crop_columns)}`

## 3. Crop Lineage Findings

- Crop metadata rows: {summary['crop_metadata_rows']}
- Resolved crop rows: {summary['resolved_crop_rows']}
- Unresolved crop rows: {summary['unresolved_crop_rows']}
- Duplicate crop path count: {summary['duplicate_crop_path_count']}

## 4. Split Assignment Counts

- Train crops: {summary['train_crop_count']}
- Validation crops: {summary['validation_crop_count']}
- Test crops: {summary['test_crop_count']}

## 5. Dirty-positive Traceability Quality

- Dirty-positive crops: {summary['dirty_positive_count']}
- Exact traceability: {summary['exact_dirty_positive_traceability_count']}
- Source-level only: {summary['source_level_dirty_positive_traceability_count']}
- Not traceable: {summary['untraceable_dirty_positive_count']}

## 6. Clean-negative Traceability Quality

Clean-negative crops map safely to source image and split when `source_id/source_image` is present, but this audit does not claim that a clean-negative crop is defect-free unless traceability proves it.

## 7. Leakage Audit Result

Leakage detected: {summary['leakage_detected']}

## 8. Reuse Decision

`{reuse_decision}`

## 9. Exact Blockers

- {'; '.join(blockers)}

## 10. Recommended Next Action

Use `final_ground_truth_with_split.csv` / `source_split_manifest.csv` as the authority for any future training job, and if crops are reused, join crop rows to `crop_lineage_manifest.csv` so train/validation/test never mix source images.

## 11. Explicit Statements

- No crop or source image was modified.
- No Ground Truth or split manifest was modified.
- No model was trained.
- This audit does not claim that a clean-negative crop is defect-free unless traceability proves it.
"""


def create_outputs(
    output_dir: Path,
    crop_columns: list[str],
    lineage_rows: list[dict[str, object]],
    split_summary_rows: list[dict[str, object]],
    leakage_rows: list[dict[str, object]],
    dirty_trace_rows: list[dict[str, object]],
    input_hashes: dict[str, str],
    stats: dict[str, object],
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    lineage_path = output_dir / "crop_lineage_manifest.csv"
    split_summary_path = output_dir / "crop_split_summary.csv"
    leakage_path = output_dir / "crop_leakage_audit.csv"
    dirty_trace_path = output_dir / "dirty_positive_traceability_audit.csv"
    summary_path = output_dir / "crop_reuse_summary.json"
    report_path = output_dir / "crop_reuse_report.md"

    write_csv(lineage_path, crop_columns + [column for column in LINEAGE_COLUMNS if column not in crop_columns], lineage_rows)
    write_csv(split_summary_path, SPLIT_SUMMARY_COLUMNS, split_summary_rows)
    write_csv(leakage_path, LEAKAGE_AUDIT_COLUMNS, leakage_rows)
    write_csv(dirty_trace_path, DIRTY_TRACE_COLUMNS, dirty_trace_rows)

    duplicate_crop_path_count = int(stats.get("duplicate_crop_paths", 0))
    reuse_decision = decide_reuse(lineage_rows, leakage_rows, dirty_trace_rows, duplicate_crop_path_count)
    counts_by_split = Counter(str(row["dataset_split"]) for row in lineage_rows)
    dirty_counts = Counter(str(row["traceability_level"]) for row in dirty_trace_rows)
    label_counts = Counter(row.get("label", "") for row in lineage_rows)
    output_hashes = {
        "crop_lineage_manifest.csv": file_sha256(lineage_path),
        "crop_split_summary.csv": file_sha256(split_summary_path),
        "crop_leakage_audit.csv": file_sha256(leakage_path),
        "dirty_positive_traceability_audit.csv": file_sha256(dirty_trace_path),
    }
    summary = {
        "crop_metadata_rows": len(lineage_rows),
        "resolved_crop_rows": sum(1 for row in lineage_rows if row["lineage_status"] != "unresolved"),
        "unresolved_crop_rows": sum(1 for row in lineage_rows if row["lineage_status"] == "unresolved"),
        "train_crop_count": counts_by_split["train"],
        "validation_crop_count": counts_by_split["validation"],
        "test_crop_count": counts_by_split["test"],
        "dirty_positive_count": label_counts["dirty_positive"],
        "clean_negative_count": label_counts["clean_negative"],
        "exact_dirty_positive_traceability_count": dirty_counts["exact"],
        "source_level_dirty_positive_traceability_count": dirty_counts["source-level only"],
        "untraceable_dirty_positive_count": dirty_counts["not traceable"],
        "leakage_detected": any(row["leakage_detected"] == "true" for row in leakage_rows),
        "reuse_decision": reuse_decision,
        "duplicate_crop_path_count": duplicate_crop_path_count,
        "input_file_hashes": input_hashes,
        "output_hash_scope": "primary_csv_artifacts_only",
        "output_file_hashes": output_hashes,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(report_text(crop_columns, summary, reuse_decision), encoding="utf-8")
    return summary


def audit_crop_lineage(crops_dir: Path, split_dir: Path, finalization_dir: Path, output_dir: Path, enforce_empty_output: bool = True) -> dict[str, object]:
    if enforce_empty_output:
        ensure_output_empty(output_dir)
    inputs = load_inputs(crops_dir, split_dir, finalization_dir)
    lineage_rows, split_summary_rows, leakage_rows, dirty_trace_rows, stats = build_lineage(
        inputs["crop_columns"],
        inputs["crop_rows"],
        inputs["split_rows"],
        inputs["final_rows"],
        inputs["final_image_rows"],
        inputs["final_split_rows"],
    )
    return create_outputs(
        output_dir,
        inputs["crop_columns"],
        lineage_rows,
        split_summary_rows,
        leakage_rows,
        dirty_trace_rows,
        inputs["input_hashes"],
        stats,
    )


def main() -> None:
    args = parse_args()
    crops_dir = resolve_project_path(args.crops_dir)
    split_dir = resolve_project_path(args.split_dir)
    finalization_dir = resolve_project_path(args.finalization_dir)
    output_dir = resolve_output_dir(args.output_dir)
    summary = audit_crop_lineage(crops_dir, split_dir, finalization_dir, output_dir)
    print(f"Crop lineage audit complete: {output_dir}")
    print(f"Crop rows: {summary['crop_metadata_rows']}")
    print(f"Resolved/unresolved: {summary['resolved_crop_rows']} / {summary['unresolved_crop_rows']}")
    print(
        "Split crop counts: "
        f"train={summary['train_crop_count']} "
        f"validation={summary['validation_crop_count']} "
        f"test={summary['test_crop_count']}"
    )
    print(f"Reuse decision: {summary['reuse_decision']}")


if __name__ == "__main__":
    main()
