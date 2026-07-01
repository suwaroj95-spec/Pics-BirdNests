from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2


REQUIRED_COLUMNS = [
    "sorted_position",
    "pair_sequence",
    "source_filename",
    "source_path",
    "source_sha256",
    "role_proposed",
    "marker_color",
    "marker_evidence_score",
    "confidence_margin",
    "validation_status",
    "target_id",
    "target_filename",
    "review_required",
    "human_review_status",
]
QUEUE_FIELDS = [
    "review_order",
    "pair_sequence",
    "sorted_position",
    "source_filename",
    "copied_filename",
    "source_path",
    "source_sha256",
    "output_sha256",
    "role_proposed",
    "marker_color",
    "marker_evidence_score",
    "confidence_margin",
    "validation_status",
    "target_id",
    "target_filename",
    "human_review_status",
]
DEFAULT_SELECTION_RULE = "human_review_status = PENDING AND review_required = true"


class ReviewExportError(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def truthy(value: str) -> bool:
    return value.strip().casefold() == "true"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_image(path: Path) -> bool:
    return cv2.imread(str(path), cv2.IMREAD_COLOR) is not None


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_output_dir(output_dir: Path) -> None:
    rawpics = (repo_root() / "RawPics").resolve(strict=False)
    output = output_dir.resolve(strict=False)
    if output == rawpics or is_relative_to(output, rawpics):
        raise ReviewExportError(f"Output directory must not be RawPics or inside RawPics: {output_dir}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ReviewExportError(f"Output directory must be absent or empty: {output_dir}")


def default_output_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = repo_root() / "tmp" / "line_sorted_import" / f"manual_marker_review_{timestamp}"
    counter = 1
    output_dir = base
    while output_dir.exists():
        output_dir = repo_root() / "tmp" / "line_sorted_import" / f"manual_marker_review_{timestamp}_{counter}"
        counter += 1
    return output_dir


def load_plan(plan_csv: Path) -> list[dict[str, str]]:
    with plan_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ReviewExportError("Plan is missing required columns: " + ", ".join(missing))
        return list(reader)


def select_review_rows(rows: list[dict[str, str]], status: str = "PENDING") -> list[dict[str, str]]:
    selected = [
        row
        for row in rows
        if row["human_review_status"].strip().casefold() == status.casefold()
        and truthy(row["review_required"])
    ]
    return sorted(selected, key=lambda row: (int(row["pair_sequence"]), int(row["sorted_position"])))


def review_required_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected = [row for row in rows if truthy(row["review_required"])]
    return sorted(selected, key=lambda row: (int(row["pair_sequence"]), int(row["sorted_position"])))


def pair_sequences(rows: list[dict[str, str]]) -> list[int]:
    return sorted({int(row["pair_sequence"]) for row in rows})


def missing_rows(expected_rows: list[dict[str, str]], exported_or_selected_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    present = {
        (row["pair_sequence"], row["sorted_position"], row["source_filename"])
        for row in exported_or_selected_rows
    }
    return [
        row
        for row in expected_rows
        if (row["pair_sequence"], row["sorted_position"], row["source_filename"]) not in present
    ]


def role_conflict_pairs(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    conflicts: list[dict[str, object]] = []
    by_pair: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_pair.setdefault(row["pair_sequence"], []).append(row)
    for pair_sequence, pair_rows in sorted(by_pair.items(), key=lambda item: int(item[0])):
        roles = sorted(row["role_proposed"] for row in pair_rows)
        if roles != ["marker", "raw"]:
            conflicts.append(
                {
                    "pair_sequence": int(pair_sequence),
                    "target_ids": sorted({row["target_id"] for row in pair_rows}),
                    "roles": roles,
                    "source_filenames": [row["source_filename"] for row in sorted(pair_rows, key=lambda row: int(row["sorted_position"]))],
                }
            )
    return conflicts


def validate_selection_complete(rows: list[dict[str, str]], selected: list[dict[str, str]], status: str) -> None:
    expected = review_required_rows(rows)
    missing = missing_rows(expected, selected)
    if missing:
        details = ", ".join(
            f"pair {row['pair_sequence']} pos {row['sorted_position']} {row['source_filename']} status={row['human_review_status']}"
            for row in missing[:6]
        )
        raise ReviewExportError(
            f"Selection is incomplete for rule {DEFAULT_SELECTION_RULE}. "
            f"Expected {len(pair_sequences(expected))} review pairs/{len(expected)} rows, "
            f"but selected {len(pair_sequences(selected))} pairs/{len(selected)} rows for status={status}. "
            f"Missing: {details}"
        )


def copied_filename(row: dict[str, str]) -> str:
    return f"{int(row['pair_sequence']):04d}__{int(row['sorted_position']):04d}__{row['source_filename']}"


def validate_selected_rows(selected: list[dict[str, str]], output_dir: Path) -> None:
    validate_output_dir(output_dir)
    if len(selected) % 2:
        raise ReviewExportError(f"Selected row count must be even; found {len(selected)}.")
    by_pair: dict[str, list[dict[str, str]]] = {}
    seen_sources: set[str] = set()
    seen_outputs: set[str] = set()
    for row in selected:
        by_pair.setdefault(row["pair_sequence"], []).append(row)
        source = Path(row["source_path"])
        source_key = str(source.resolve(strict=False)).casefold()
        if source_key in seen_sources:
            raise ReviewExportError(f"Selected source appears more than once: {source}")
        seen_sources.add(source_key)
        if not source.is_file():
            raise ReviewExportError(f"Source file is missing: {source}")
        actual_hash = sha256_file(source)
        if actual_hash != row["source_sha256"]:
            raise ReviewExportError(f"Source SHA-256 changed: {source}")
        if not read_image(source):
            raise ReviewExportError(f"Selected source image is unreadable: {source}")
        output_name = copied_filename(row)
        output_key = output_name.casefold()
        if output_key in seen_outputs:
            raise ReviewExportError(f"Copied filename would collide: {output_name}")
        seen_outputs.add(output_key)
        if (output_dir / "images" / output_name).exists():
            raise ReviewExportError(f"Planned output already exists: {output_dir / 'images' / output_name}")
    for pair_sequence, pair_rows in by_pair.items():
        if len(pair_rows) != 2:
            raise ReviewExportError(f"Pair {pair_sequence} must contain exactly two selected rows.")


def finalize_staging_dir(staging_dir: Path, output_dir: Path) -> None:
    last_error: OSError | None = None
    for _ in range(5):
        try:
            staging_dir.rename(output_dir)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.25)
    try:
        shutil.move(str(staging_dir), str(output_dir))
    except OSError as exc:
        raise ReviewExportError(f"Could not finalize review export directory: {exc}") from last_error or exc


def export_review_queue(plan_csv: Path, output_dir: Path | None = None, status: str = "PENDING") -> Path:
    output = output_dir or default_output_dir()
    rows = load_plan(plan_csv)
    selected = select_review_rows(rows, status)
    validate_selection_complete(rows, selected, status)
    validate_selected_rows(selected, output)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    staging_dir = output.parent / f".{output.name}_staging_{timestamp}"
    if staging_dir.exists():
        raise ReviewExportError(f"Temporary staging directory already exists: {staging_dir}")
    images_dir = staging_dir / "images"
    images_dir.mkdir(parents=True)
    queue_rows: list[dict[str, str]] = []
    mismatch_count = 0
    try:
        for review_order, row in enumerate(selected, start=1):
            source = Path(row["source_path"])
            name = copied_filename(row)
            copied = images_dir / name
            shutil.copy2(source, copied)
            output_hash = sha256_file(copied)
            if output_hash != row["source_sha256"]:
                mismatch_count += 1
                raise ReviewExportError(f"Copied SHA-256 mismatch for {source}")
            queue_rows.append(
                {
                    "review_order": str(review_order),
                    "pair_sequence": row["pair_sequence"],
                    "sorted_position": row["sorted_position"],
                    "source_filename": row["source_filename"],
                    "copied_filename": name,
                    "source_path": row["source_path"],
                    "source_sha256": row["source_sha256"],
                    "output_sha256": output_hash,
                    "role_proposed": row["role_proposed"],
                    "marker_color": row["marker_color"],
                    "marker_evidence_score": row["marker_evidence_score"],
                    "confidence_margin": row["confidence_margin"],
                    "validation_status": row["validation_status"],
                    "target_id": row["target_id"],
                    "target_filename": row["target_filename"],
                    "human_review_status": row["human_review_status"],
                }
            )
        with (staging_dir / "review_queue.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=QUEUE_FIELDS)
            writer.writeheader()
            writer.writerows(queue_rows)
        pair_sequences = sorted({int(row["pair_sequence"]) for row in selected})
        summary = {
            "plan_csv": str(plan_csv),
            "selected_status": status,
            "selected_pair_count": len(pair_sequences),
            "selected_row_count": len(selected),
            "copied_file_count": len(queue_rows),
            "pair_sequences": pair_sequences,
            "copy_sha256_mismatch_count": mismatch_count,
            "validation_status": "OK",
            "blockers": [],
        }
        (staging_dir / "review_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if output.exists():
            output.rmdir()
        finalize_staging_dir(staging_dir, output)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    return output


def load_review_queue(review_queue_csv: Path) -> list[dict[str, str]]:
    with review_queue_csv.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_audit_report(plan_csv: Path, review_queue_csv: Path) -> Path:
    plan_rows = load_plan(plan_csv)
    exported_rows = load_review_queue(review_queue_csv)
    expected = review_required_rows(plan_rows)
    selected = select_review_rows(plan_rows)
    missing = missing_rows(expected, exported_rows)
    status_blockers = missing_rows(expected, selected)
    exported_pairs = pair_sequences(exported_rows)
    expected_pairs = pair_sequences(expected)
    root_cause = "No missing review-required rows were found."
    if status_blockers:
        root_cause = (
            "The source rename_plan.csv has review_required=true rows whose human_review_status is not PENDING. "
            "The intended selection rule excludes those rows, so the previous export contained fewer rows than "
            "the review-required count in rename_summary.json."
        )
    elif missing:
        root_cause = "The review queue is missing rows that match the intended source-plan review selection."

    report = {
        "expected_review_pair_count": len(expected_pairs),
        "expected_review_row_count": len(expected),
        "exported_review_pair_count": len(exported_pairs),
        "exported_review_row_count": len(exported_rows),
        "missing_pair_sequences": pair_sequences(missing),
        "missing_sorted_positions": [int(row["sorted_position"]) for row in missing],
        "missing_source_filenames": [row["source_filename"] for row in missing],
        "selection_rule_used": DEFAULT_SELECTION_RULE,
        "root_cause": root_cause,
        "missing_rows": [
            {
                "pair_sequence": int(row["pair_sequence"]),
                "sorted_position": int(row["sorted_position"]),
                "source_filename": row["source_filename"],
                "human_review_status": row["human_review_status"],
                "review_required": row["review_required"],
            }
            for row in missing
        ],
        "role_conflict_pairs": role_conflict_pairs(expected),
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = repo_root() / "tmp" / "line_sorted_import" / f"review_queue_audit_{timestamp}"
    counter = 1
    while output_dir.exists():
        output_dir = repo_root() / "tmp" / "line_sorted_import" / f"review_queue_audit_{timestamp}_{counter}"
        counter += 1
    output_dir.mkdir(parents=True)
    (output_dir / "review_queue_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown = [
        "# Review Queue Audit",
        "",
        f"- Plan CSV: `{plan_csv}`",
        f"- Review queue CSV: `{review_queue_csv}`",
        f"- Selection rule used: `{DEFAULT_SELECTION_RULE}`",
        f"- Expected review pairs: {report['expected_review_pair_count']}",
        f"- Expected review rows: {report['expected_review_row_count']}",
        f"- Exported review pairs: {report['exported_review_pair_count']}",
        f"- Exported review rows: {report['exported_review_row_count']}",
        f"- Missing pair sequences: {report['missing_pair_sequences']}",
        f"- Missing sorted positions: {report['missing_sorted_positions']}",
        f"- Missing source filenames: {report['missing_source_filenames']}",
        "",
        "## Root Cause",
        "",
        str(report["root_cause"]),
        "",
        "## Role Conflict Pairs",
        "",
    ]
    conflicts = report["role_conflict_pairs"]
    if conflicts:
        for conflict in conflicts:
            markdown.append(
                f"- pair_sequence {conflict['pair_sequence']}, target IDs {conflict['target_ids']}, "
                f"roles {conflict['roles']}, files {conflict['source_filenames']}"
            )
    else:
        markdown.append("- None")
    (output_dir / "review_queue_audit.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return output_dir


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export pending marker-role review images from an importer plan.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    export = subparsers.add_parser("export")
    export.add_argument("--plan-csv", required=True, type=Path)
    export.add_argument("--output-dir", type=Path)
    export.add_argument("--status", default="PENDING")
    audit = subparsers.add_parser("audit")
    audit.add_argument("--plan-csv", required=True, type=Path)
    audit.add_argument("--review-queue-csv", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "export":
            output = export_review_queue(args.plan_csv, args.output_dir, args.status)
            print(f"Review queue exported: {output}")
        elif args.command == "audit":
            output = write_audit_report(args.plan_csv, args.review_queue_csv)
            print(f"Review queue audit written: {output}")
        return 0
    except ReviewExportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
