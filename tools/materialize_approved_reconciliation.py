from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
FUTURE_START_ID = 16
APPROVED_EXCLUSIONS = (
    ("S__3956902_2.jpg", "DUP-0001", 32),
    ("S__10690658_1.jpg", "DUP-0029", 200),
)
PLAN_FIELDS = [
    "original_sort_position",
    "source_filename",
    "source_path",
    "sha256",
    "duplicate_group_id",
    "approved_action",
    "reason",
    "retained",
    "output_filename",
    "output_path",
    "readable_image",
    "width",
    "height",
    "validation_status",
]
MANIFEST_FIELDS = [
    "original_sort_position",
    "source_filename",
    "source_sha256",
    "output_filename",
    "output_sha256",
    "duplicate_group_id",
    "approved_action",
    "retained",
    "input_directory",
    "output_directory",
    "timestamp",
    "operation_mode",
]


class MaterializationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApprovedExclusion:
    filename: str
    duplicate_group_id: str
    original_sort_position: int


APPROVED_MANIFEST = tuple(
    ApprovedExclusion(filename=name, duplicate_group_id=group_id, original_sort_position=position)
    for name, group_id, position in APPROVED_EXCLUSIONS
)


def natural_sort_key(name: str) -> list[tuple[int, object]]:
    parts = re.split(r"(\d+)", name.casefold())
    key: list[tuple[int, object]] = []
    for part in parts:
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part))
    return key


def discover_images(input_dir: Path) -> list[Path]:
    if not input_dir.is_dir():
        raise MaterializationError(f"Input directory does not exist: {input_dir}")
    files = [
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files, key=lambda path: natural_sort_key(path.name))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_image_size(path: Path) -> tuple[bool, int, int]:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        return False, 0, 0
    height, width = image.shape[:2]
    return True, int(width), int(height)


def truthy(value: str) -> bool:
    return value.strip().casefold() == "true"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_for_safety(path: Path) -> Path:
    return path.resolve(strict=False)


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_output_dir(output_dir: Path) -> None:
    rawpics = resolve_for_safety(repo_root() / "RawPics")
    output = resolve_for_safety(output_dir)
    if output == rawpics or is_relative_to(output, rawpics):
        raise MaterializationError(f"Output directory must not be RawPics or inside RawPics: {output_dir}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise MaterializationError(f"Output directory must be absent or empty: {output_dir}")


def load_audit_records(audit_dir: Path) -> list[dict[str, str]]:
    plan_path = audit_dir / "reconciliation_plan.csv"
    if not plan_path.is_file():
        raise MaterializationError(f"Missing reconciliation plan: {plan_path}")
    with plan_path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def approved_by_filename() -> dict[str, ApprovedExclusion]:
    approved = {item.filename: item for item in APPROVED_MANIFEST}
    if len(approved) != len(APPROVED_MANIFEST):
        raise MaterializationError("Approved exclusion manifest contains duplicate filenames.")
    positions = [item.original_sort_position for item in APPROVED_MANIFEST]
    if len(set(positions)) != len(positions):
        raise MaterializationError("Approved exclusion manifest contains duplicate positions.")
    return approved


def validate_approved_decision(
    audit_rows: list[dict[str, str]],
    files_by_position: dict[int, Path],
    hashes_by_name: dict[str, str],
) -> None:
    approved = approved_by_filename()
    audit_by_name = {row["source_filename"]: row for row in audit_rows}
    if len(audit_by_name) != len(audit_rows):
        raise MaterializationError("Audit plan contains duplicate source filenames.")

    blockers: list[str] = []
    for exclusion in APPROVED_MANIFEST:
        row = audit_by_name.get(exclusion.filename)
        if row is None:
            blockers.append(f"Approved exclusion missing from audit: {exclusion.filename}")
            continue
        source = Path(row["source_path"])
        if not source.is_file():
            blockers.append(f"Approved source file does not exist: {source}")
        if row["source_filename"] != exclusion.filename:
            blockers.append(f"Filename mismatch for approved exclusion: {exclusion.filename}")
        if int(row["original_sort_position"]) != exclusion.original_sort_position:
            blockers.append(f"Position mismatch for {exclusion.filename}")
        if row["duplicate_group_id"] != exclusion.duplicate_group_id:
            blockers.append(f"Duplicate group mismatch for {exclusion.filename}")
        if truthy(row.get("is_unique_sha256", "")):
            blockers.append(f"Approved exclusion is marked unique SHA-256: {exclusion.filename}")
        if int(row.get("duplicate_group_size") or "1") < 2:
            blockers.append(f"Approved exclusion is not in a duplicate group: {exclusion.filename}")
        if files_by_position.get(exclusion.original_sort_position, Path()).name != exclusion.filename:
            blockers.append(f"Input sort position {exclusion.original_sort_position} is not {exclusion.filename}")
        actual_hash = hashes_by_name.get(exclusion.filename)
        if actual_hash is None:
            blockers.append(f"Approved source file not found in input directory: {exclusion.filename}")
        elif actual_hash != row["sha256"]:
            blockers.append(f"SHA-256 mismatch for {exclusion.filename}")

    excluded_names = set(approved)
    if len(excluded_names) != 2:
        blockers.append("Approved decision must exclude exactly two files.")
    for name in excluded_names:
        if name not in audit_by_name:
            blockers.append(f"Approved exclusion has no audit row: {name}")

    if blockers:
        raise MaterializationError("; ".join(blockers))


def build_plan(
    input_dir: Path,
    audit_dir: Path,
    output_dir: Path,
    expected_input_files: int | None = None,
    expected_retained_files: int | None = None,
    expected_pairs: int | None = None,
) -> tuple[list[dict[str, str]], dict[str, object]]:
    validate_output_dir(output_dir)
    files = discover_images(input_dir)
    if expected_input_files is not None and len(files) != expected_input_files:
        raise MaterializationError(f"Expected {expected_input_files} input files but found {len(files)}.")

    rows: list[dict[str, str]] = []
    files_by_position = {position: path for position, path in enumerate(files, start=1)}
    hashes_by_name: dict[str, str] = {}
    audit_rows = load_audit_records(audit_dir)
    audit_by_name = {row["source_filename"]: row for row in audit_rows}
    approved = approved_by_filename()

    for position, path in enumerate(files, start=1):
        source_hash = sha256_file(path)
        hashes_by_name[path.name] = source_hash
        readable, width, height = read_image_size(path)
        audit_row = audit_by_name.get(path.name, {})
        exclusion = approved.get(path.name)
        retained = exclusion is None
        action = "KEEP" if retained else "EXCLUDE_APPROVED_EXACT_DUPLICATE"
        reason = "Approved exact duplicate exclusion." if exclusion else "Retained by approved decision."
        validation_status = "OK" if readable or not retained else "IMAGE_READ_ERROR"
        rows.append(
            {
                "original_sort_position": str(position),
                "source_filename": path.name,
                "source_path": str(path),
                "sha256": source_hash,
                "duplicate_group_id": audit_row.get("duplicate_group_id", ""),
                "approved_action": action,
                "reason": reason,
                "retained": "true" if retained else "false",
                "output_filename": path.name if retained else "",
                "output_path": str(output_dir / path.name) if retained else "",
                "readable_image": "true" if readable else "false",
                "width": str(width),
                "height": str(height),
                "validation_status": validation_status,
            }
        )

    validate_approved_decision(audit_rows, files_by_position, hashes_by_name)
    retained_rows = [row for row in rows if row["retained"] == "true"]
    read_errors = [row["source_filename"] for row in retained_rows if row["readable_image"] != "true"]
    if read_errors:
        raise MaterializationError("Retained images are unreadable: " + "; ".join(read_errors[:5]))

    target_names: set[str] = set()
    for row in retained_rows:
        target_name = row["output_filename"]
        folded = target_name.casefold()
        if folded in target_names:
            raise MaterializationError(f"Output filename conflict: {target_name}")
        target_names.add(folded)
        if (output_dir / target_name).exists():
            raise MaterializationError(f"Planned output already exists: {output_dir / target_name}")

    retained_count = len(retained_rows)
    pair_count = retained_count // 2
    if expected_retained_files is not None and retained_count != expected_retained_files:
        raise MaterializationError(f"Expected {expected_retained_files} retained files but found {retained_count}.")
    if retained_count % 2:
        raise MaterializationError(f"Retained file count must be even; found {retained_count}.")
    if expected_pairs is not None and pair_count != expected_pairs:
        raise MaterializationError(f"Expected {expected_pairs} pairs but found {pair_count}.")

    future_end_id = FUTURE_START_ID + pair_count - 1 if pair_count else FUTURE_START_ID - 1
    summary = {
        "original_file_count": len(files),
        "approved_exclusion_count": len(APPROVED_MANIFEST),
        "retained_file_count": retained_count,
        "retained_file_count_even": retained_count % 2 == 0,
        "projected_adjacent_pair_count": pair_count,
        "future_start_id": FUTURE_START_ID,
        "future_end_id": future_end_id,
        "approved_exclusions": [
            {
                "source_filename": item.filename,
                "duplicate_group_id": item.duplicate_group_id,
                "original_sort_position": item.original_sort_position,
            }
            for item in APPROVED_MANIFEST
        ],
        "validation_status": "OK",
        "blockers": [],
    }
    return rows, summary


def write_preflight(rows: list[dict[str, str]], summary: dict[str, object], root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    preflight_dir = root / "tmp" / "approved_reconciliation" / f"preflight_{timestamp}"
    counter = 1
    while preflight_dir.exists():
        preflight_dir = root / "tmp" / "approved_reconciliation" / f"preflight_{timestamp}_{counter}"
        counter += 1
    preflight_dir.mkdir(parents=True)
    with (preflight_dir / "approved_reconciliation_plan.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PLAN_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (preflight_dir / "approved_reconciliation_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return preflight_dir


def load_plan(plan_csv: Path) -> list[dict[str, str]]:
    with plan_csv.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_apply_rows(rows: list[dict[str, str]], output_dir: Path) -> list[dict[str, str]]:
    if not rows:
        raise MaterializationError("Plan is empty.")
    validate_output_dir(output_dir)
    approved = approved_by_filename()
    excluded = [row for row in rows if row["retained"] == "false"]
    excluded_names = {row["source_filename"] for row in excluded}
    if excluded_names != set(approved):
        raise MaterializationError("Plan exclusions do not exactly match the approved decision.")
    if len(excluded) != len(approved):
        raise MaterializationError("Plan contains duplicate or missing exclusion rows.")

    retained_rows = [row for row in rows if row["retained"] == "true"]
    if len(retained_rows) != 368:
        raise MaterializationError(f"Retained file count must be exactly 368; found {len(retained_rows)}.")

    target_names: set[str] = set()
    for row in rows:
        source = Path(row["source_path"])
        if not source.is_file():
            raise MaterializationError(f"Source file is missing: {source}")
        actual_hash = sha256_file(source)
        if actual_hash != row["sha256"]:
            raise MaterializationError(f"Source SHA-256 changed: {source}")
        if row["retained"] == "false":
            exclusion = approved.get(row["source_filename"])
            if exclusion is None:
                raise MaterializationError(f"Unapproved exclusion in plan: {row['source_filename']}")
            if row["approved_action"] != "EXCLUDE_APPROVED_EXACT_DUPLICATE":
                raise MaterializationError(f"Invalid exclusion action for {row['source_filename']}")
            if int(row["original_sort_position"]) != exclusion.original_sort_position:
                raise MaterializationError(f"Exclusion position mismatch for {row['source_filename']}")
            if row["duplicate_group_id"] != exclusion.duplicate_group_id:
                raise MaterializationError(f"Exclusion duplicate group mismatch for {row['source_filename']}")
            continue
        readable, _, _ = read_image_size(source)
        if not readable:
            raise MaterializationError(f"Retained source image is unreadable: {source}")
        output_filename = row["output_filename"]
        if output_filename != row["source_filename"]:
            raise MaterializationError(f"Output filename must preserve source filename: {row['source_filename']}")
        folded = output_filename.casefold()
        if folded in target_names:
            raise MaterializationError(f"Duplicate target filename in plan: {output_filename}")
        target_names.add(folded)
        if (output_dir / output_filename).exists():
            raise MaterializationError(f"Target already exists: {output_dir / output_filename}")
    return retained_rows


def apply_plan(plan_csv: Path, output_dir: Path, apply_confirmed: bool) -> Path:
    if not apply_confirmed:
        raise MaterializationError("apply requires the explicit --apply flag; no files were changed.")
    rows = load_plan(plan_csv)
    retained_rows = validate_apply_rows(rows, output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    staging_dir = output_dir.parent / f".{output_dir.name}_staging_{timestamp}"
    if staging_dir.exists():
        raise MaterializationError(f"Temporary staging directory already exists: {staging_dir}")
    staging_dir.mkdir(parents=True)
    manifest_rows: list[dict[str, str]] = []
    try:
        for row in retained_rows:
            source = Path(row["source_path"])
            staged = staging_dir / row["output_filename"]
            shutil.copy2(source, staged)
            output_sha = sha256_file(staged)
            if output_sha != row["sha256"]:
                raise MaterializationError(f"Copied SHA-256 mismatch for {source}")
            manifest_rows.append(
                {
                    "original_sort_position": row["original_sort_position"],
                    "source_filename": row["source_filename"],
                    "source_sha256": row["sha256"],
                    "output_filename": row["output_filename"],
                    "output_sha256": output_sha,
                    "duplicate_group_id": row["duplicate_group_id"],
                    "approved_action": row["approved_action"],
                    "retained": row["retained"],
                    "input_directory": str(source.parent),
                    "output_directory": str(output_dir),
                    "timestamp": timestamp,
                    "operation_mode": "copy",
                }
            )
        with (staging_dir / "approved_reconciliation_manifest.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            writer.writerows(manifest_rows)
        summary = {
            "materialized_files": len(retained_rows),
            "approved_exclusion_count": len(APPROVED_MANIFEST),
            "projected_adjacent_pair_count": len(retained_rows) // 2,
            "future_start_id": FUTURE_START_ID,
            "future_end_id": FUTURE_START_ID + (len(retained_rows) // 2) - 1,
            "output_dir": str(output_dir),
            "operation_mode": "copy",
            "timestamp": timestamp,
        }
        (staging_dir / "approved_reconciliation_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        if output_dir.exists():
            output_dir.rmdir()
        finalize_staging_dir(staging_dir, output_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    return output_dir


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
        raise MaterializationError(f"Could not finalize staged output directory: {exc}") from last_error or exc


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the approved LINE duplicate reconciliation staging set.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--input-dir", required=True, type=Path)
    preflight.add_argument("--audit-dir", required=True, type=Path)
    preflight.add_argument("--output-dir", required=True, type=Path)
    preflight.add_argument("--expected-input-files", type=int)
    preflight.add_argument("--expected-retained-files", type=int)
    preflight.add_argument("--expected-pairs", type=int)
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--plan-csv", required=True, type=Path)
    apply_parser.add_argument("--output-dir", required=True, type=Path)
    apply_parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "preflight":
            rows, summary = build_plan(
                input_dir=args.input_dir,
                audit_dir=args.audit_dir,
                output_dir=args.output_dir,
                expected_input_files=args.expected_input_files,
                expected_retained_files=args.expected_retained_files,
                expected_pairs=args.expected_pairs,
            )
            preflight_dir = write_preflight(rows, summary, repo_root())
            print(f"Preflight written: {preflight_dir}")
        elif args.command == "apply":
            output_dir = apply_plan(args.plan_csv, args.output_dir, args.apply)
            print(f"Materialized staging dataset: {output_dir}")
        return 0
    except MaterializationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
