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


APPROVED_QUARANTINE = {
    17: (32, "33", "both images are marker images; no valid matching raw image exists"),
    72: (87, "", "raw and marker are different source images"),
    74: (89, "", "raw and marker are different source images"),
    83: (98, "", "raw and marker are different source images"),
    87: (102, "", "raw and marker are different source images"),
    88: (103, "", "raw and marker are different source images"),
    89: (104, "", "raw and marker are different source images"),
    100: (115, "", "exact duplicate within pair"),
    101: (116, "", "exact duplicate within pair"),
    102: (117, "", "exact duplicate within pair"),
}
APPROVED_ROLE_SWAP = {95: (110, "the two images are a valid pair, but current raw/marker roles are reversed")}
PLAN_REQUIRED = [
    "sorted_position",
    "pair_sequence",
    "source_filename",
    "source_path",
    "source_sha256",
    "width",
    "height",
    "role_proposed",
    "marker_color",
    "target_id",
]
RESOLUTION_FIELDS = [
    "pair_sequence",
    "original_target_id",
    "decision",
    "preferred_reference_sorted_position",
    "reason",
]
RESOLUTION_V2_FIELDS = RESOLUTION_FIELDS + ["source_v1_target_id"]
FINAL_PLAN_FIELDS = [
    "final_pair_sequence",
    "final_target_id",
    "final_role",
    "final_marker_color",
    "final_output_filename",
    "original_pair_sequence",
    "original_target_id",
    "original_sorted_position",
    "source_filename",
    "source_path",
    "source_sha256",
    "source_extension",
    "source_width",
    "source_height",
    "resolution_source",
    "validation_status",
]
QUARANTINE_FIELDS = [
    "original_pair_sequence",
    "original_target_id",
    "original_sorted_position",
    "source_filename",
    "source_path",
    "source_sha256",
    "quarantine_reason",
    "preferred_reference",
    "preferred_reference_sorted_position",
    "training_eligible",
]
MANIFEST_FIELDS = [
    "final_pair_sequence",
    "final_target_id",
    "final_role",
    "final_marker_color",
    "source_filename",
    "source_sha256",
    "output_filename",
    "output_sha256",
    "original_pair_sequence",
    "original_target_id",
    "resolution_source",
    "operation_mode",
    "timestamp",
]


class FinalBatchError(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_plan(plan_csv: Path) -> list[dict[str, str]]:
    with plan_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in PLAN_REQUIRED if field not in (reader.fieldnames or [])]
        if missing:
            raise FinalBatchError("Plan is missing required columns: " + ", ".join(missing))
        return list(reader)


def rows_by_pair(rows: list[dict[str, str]]) -> dict[int, list[dict[str, str]]]:
    pairs: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        pairs.setdefault(int(row["pair_sequence"]), []).append(row)
    return dict(sorted(pairs.items()))


def is_v2_resolution(resolution_csv: Path) -> bool:
    return resolution_csv.stem.endswith("_v2")


def default_v1_final_plan_csv() -> Path:
    return repo_root() / "tmp" / "final_training_red_batch" / "preflight_20260701_114656" / "final_training_plan.csv"


def load_resolution(
    resolution_csv: Path,
    pairs: dict[int, list[dict[str, str]]],
    v1_final_plan_csv: Path | None = None,
) -> tuple[dict[int, tuple[int, str, str, str]], dict[int, tuple[int, str]]]:
    rows = load_csv(resolution_csv)
    allowed_schemas = {tuple(RESOLUTION_FIELDS), tuple(RESOLUTION_V2_FIELDS)}
    if not rows:
        raise FinalBatchError("Resolution CSV is empty.")
    if tuple(rows[0].keys()) not in allowed_schemas or any(tuple(row.keys()) != tuple(rows[0].keys()) for row in rows):
        raise FinalBatchError("Resolution CSV columns do not match the required schema.")
    seen: set[int] = set()
    quarantine: dict[int, tuple[int, str, str, str]] = {}
    swaps: dict[int, tuple[int, str]] = {}
    for row in rows:
        pair = int(row["pair_sequence"])
        if pair in seen:
            raise FinalBatchError(f"Duplicate resolution decision for pair {pair}.")
        seen.add(pair)
        decision = row["decision"]
        if decision == "QUARANTINE_PAIR":
            quarantine[pair] = (
                int(row["original_target_id"]),
                row["preferred_reference_sorted_position"],
                row["reason"],
                row.get("source_v1_target_id", ""),
            )
        elif decision == "INCLUDE_WITH_ROLE_SWAP":
            swaps[pair] = (int(row["original_target_id"]), row["reason"])
        else:
            raise FinalBatchError(f"Invalid resolution decision: {decision}")
    for pair, pair_rows in pairs.items():
        if len(pair_rows) != 2:
            raise FinalBatchError(f"Source plan pair {pair} must contain exactly two rows.")
        target_ids = {int(row["target_id"]) for row in pair_rows}
        if len(target_ids) != 1:
            raise FinalBatchError(f"Source plan pair {pair} has inconsistent target IDs.")
        if pair in quarantine and next(iter(target_ids)) != quarantine[pair][0]:
            raise FinalBatchError(f"Target ID mismatch for quarantined pair {pair}.")
        if pair in swaps and next(iter(target_ids)) != swaps[pair][0]:
            raise FinalBatchError(f"Target ID mismatch for role-swap pair {pair}.")
    if is_v2_resolution(resolution_csv):
        validate_v2_resolution(quarantine, swaps, v1_final_plan_csv or default_v1_final_plan_csv())
    return quarantine, swaps


def validate_v2_resolution(
    quarantine: dict[int, tuple[int, str, str, str]],
    swaps: dict[int, tuple[int, str]],
    v1_final_plan_csv: Path,
) -> None:
    expected_pairs = {17, 72, 74, 83, 85, 87, 88, 89, 93, 95, 100, 101, 102}
    expected_v1 = {96: (85, 100), 101: (93, 108), 103: (95, 110)}
    if set(quarantine) != expected_pairs:
        raise FinalBatchError("V2 resolution must quarantine exactly the approved 13 source pairs.")
    if swaps:
        raise FinalBatchError("V2 resolution must not contain any role-swap decisions.")
    if 95 not in quarantine:
        raise FinalBatchError("V2 resolution must quarantine pair 95.")
    by_v1_id = map_v1_targets_to_original_pairs(v1_final_plan_csv, sorted(expected_v1))
    for v1_target_id, expected in expected_v1.items():
        if by_v1_id.get(v1_target_id) != expected:
            raise FinalBatchError(f"V1 target ID {v1_target_id} did not map to original pair/target {expected}.")
    for pair, (target_id, _preferred, reason, source_v1_id) in quarantine.items():
        if source_v1_id:
            v1_id = int(source_v1_id)
            if expected_v1.get(v1_id) != (pair, target_id):
                raise FinalBatchError(f"V2 source_v1_target_id {v1_id} does not match pair {pair}.")
            if reason != "confirmed_mismatched_raw_marker_pair_from_red_preflight":
                raise FinalBatchError(f"V2 quarantine reason is invalid for pair {pair}.")


def map_v1_targets_to_original_pairs(v1_final_plan_csv: Path, target_ids: list[int]) -> dict[int, tuple[int, int]]:
    rows = load_csv(v1_final_plan_csv)
    result: dict[int, tuple[int, int]] = {}
    for target_id in target_ids:
        matching = [row for row in rows if int(row["final_target_id"]) == target_id]
        if len(matching) != 2:
            raise FinalBatchError(f"V1 target ID {target_id} must map to exactly two rows.")
        original_pairs = {int(row["original_pair_sequence"]) for row in matching}
        original_targets = {int(row["original_target_id"]) for row in matching}
        if len(original_pairs) != 1 or len(original_targets) != 1:
            raise FinalBatchError(f"V1 target ID {target_id} has inconsistent original provenance.")
        result[target_id] = (next(iter(original_pairs)), next(iter(original_targets)))
    return result


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_output_dir(output_dir: Path, input_dir: Path) -> None:
    output = output_dir.resolve(strict=False)
    root = repo_root()
    forbidden = [
        (root / "RawPics").resolve(strict=False),
        (root / "New_RawPics_birdnest_1").resolve(strict=False),
        input_dir.resolve(strict=False),
    ]
    for forbidden_dir in forbidden:
        if output == forbidden_dir or is_relative_to(output, forbidden_dir):
            raise FinalBatchError(f"Output directory is not allowed: {output_dir}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FinalBatchError(f"Output directory must be absent or empty: {output_dir}")


def final_name(final_id: int, role: str, extension: str) -> str:
    return f"{final_id}m{extension}" if role == "marker" else f"{final_id}{extension}"


def validate_source_row(row: dict[str, str]) -> tuple[int, int]:
    source = Path(row["source_path"])
    if not source.is_file():
        raise FinalBatchError(f"Source file is missing: {source}")
    if sha256_file(source) != row["source_sha256"]:
        raise FinalBatchError(f"Source SHA-256 mismatch: {source}")
    readable, width, height = read_image_size(source)
    if not readable:
        raise FinalBatchError(f"Source image is unreadable: {source}")
    return width, height


def build_preflight(
    plan_csv: Path,
    input_dir: Path,
    resolution_csv: Path,
    output_dir: Path,
    start_id: int,
    expected_source_pairs: int | None = None,
    expected_quarantined_pairs: int | None = None,
    expected_final_pairs: int | None = None,
    expected_final_files: int | None = None,
    v1_final_plan_csv: Path | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, object]]:
    validate_output_dir(output_dir, input_dir)
    rows = load_plan(plan_csv)
    pairs = rows_by_pair(rows)
    quarantine, swaps = load_resolution(resolution_csv, pairs, v1_final_plan_csv)
    source_pair_count = len(pairs)
    if sorted(pairs) != list(range(1, source_pair_count + 1)):
        raise FinalBatchError("Source plan pair sequences must be contiguous.")
    if expected_source_pairs is not None and source_pair_count != expected_source_pairs:
        raise FinalBatchError(f"Expected {expected_source_pairs} source pairs but found {source_pair_count}.")
    if expected_quarantined_pairs is not None and len(quarantine) != expected_quarantined_pairs:
        raise FinalBatchError("Quarantined pair count does not match expected value.")

    final_rows: list[dict[str, str]] = []
    quarantine_rows: list[dict[str, str]] = []
    used_sources: set[str] = set()
    target_names: set[str] = set()
    final_pair_sequence = 0
    hash_mismatches = 0
    for original_pair, pair_rows in pairs.items():
        ordered = sorted(pair_rows, key=lambda row: int(row["sorted_position"]))
        original_target_id = ordered[0]["target_id"]
        widths_heights = [validate_source_row(row) for row in ordered]
        if original_pair in quarantine:
            target_id, preferred_position, reason, _source_v1_id = quarantine[original_pair]
            for row in ordered:
                quarantine_rows.append(
                    {
                        "original_pair_sequence": str(original_pair),
                        "original_target_id": str(target_id),
                        "original_sorted_position": row["sorted_position"],
                        "source_filename": row["source_filename"],
                        "source_path": row["source_path"],
                        "source_sha256": row["source_sha256"],
                        "quarantine_reason": reason,
                        "preferred_reference": "true" if row["sorted_position"] == preferred_position else "false",
                        "preferred_reference_sorted_position": preferred_position,
                        "training_eligible": "false",
                    }
                )
            continue
        roles = [row["role_proposed"] for row in ordered]
        if sorted(roles) != ["marker", "raw"]:
            raise FinalBatchError(f"Included pair {original_pair} must have exactly one raw and one marker.")
        if widths_heights[0] != widths_heights[1]:
            raise FinalBatchError(f"Included pair {original_pair} has mismatched dimensions.")
        if ordered[0]["source_sha256"] == ordered[1]["source_sha256"]:
            raise FinalBatchError(f"Included pair {original_pair} has duplicate SHA-256 values.")
        for row in ordered:
            key = str(Path(row["source_path"]).resolve(strict=False)).casefold()
            if key in used_sources:
                raise FinalBatchError(f"Source image reused in final plan: {row['source_path']}")
            used_sources.add(key)

        final_pair_sequence += 1
        final_target_id = start_id + final_pair_sequence - 1
        swap = original_pair in swaps
        for row, (width, height) in zip(ordered, widths_heights):
            final_role = "raw" if row["role_proposed"] == "marker" else "marker" if swap else row["role_proposed"]
            if not swap:
                final_role = row["role_proposed"]
            final_marker_color = "red" if final_role == "marker" else ""
            output_name = final_name(final_target_id, final_role, Path(row["source_path"]).suffix)
            if output_name.casefold() in target_names or (output_dir / output_name).exists():
                raise FinalBatchError(f"Output filename collision: {output_name}")
            target_names.add(output_name.casefold())
            final_rows.append(
                {
                    "final_pair_sequence": str(final_pair_sequence),
                    "final_target_id": str(final_target_id),
                    "final_role": final_role,
                    "final_marker_color": final_marker_color,
                    "final_output_filename": output_name,
                    "original_pair_sequence": str(original_pair),
                    "original_target_id": str(original_target_id),
                    "original_sorted_position": row["sorted_position"],
                    "source_filename": row["source_filename"],
                    "source_path": row["source_path"],
                    "source_sha256": row["source_sha256"],
                    "source_extension": Path(row["source_path"]).suffix,
                    "source_width": str(width),
                    "source_height": str(height),
                    "resolution_source": "INCLUDE_WITH_ROLE_SWAP" if swap else "SOURCE_PLAN_APPROVED",
                    "validation_status": "OK",
                }
            )

    final_pair_count = len(final_rows) // 2
    if expected_final_pairs is not None and final_pair_count != expected_final_pairs:
        raise FinalBatchError(f"Expected {expected_final_pairs} final pairs but found {final_pair_count}.")
    if expected_final_files is not None and len(final_rows) != expected_final_files:
        raise FinalBatchError(f"Expected {expected_final_files} final files but found {len(final_rows)}.")
    summary = {
        "source_pair_count": source_pair_count,
        "quarantined_pair_count": len(quarantine),
        "final_training_pair_count": final_pair_count,
        "final_training_file_count": len(final_rows),
        "final_id_start": start_id,
        "final_id_end": start_id + final_pair_count - 1,
        "role_swap_pair_sequences": sorted(swaps),
        "quarantined_pair_sequences": sorted(quarantine),
        "duplicate_source_reuse_count": 0,
        "source_hash_mismatch_count": hash_mismatches,
        "validation_status": "OK",
        "blockers": [],
    }
    return final_rows, quarantine_rows, summary


def write_preflight(
    final_rows: list[dict[str, str]],
    quarantine_rows: list[dict[str, str]],
    summary: dict[str, object],
    version: str = "",
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    root_name = "final_training_red_batch_v2" if version == "v2" else "final_training_red_batch"
    suffix = "_v2" if version == "v2" else ""
    out = repo_root() / "tmp" / root_name / f"preflight_{timestamp}"
    counter = 1
    while out.exists():
        out = repo_root() / "tmp" / root_name / f"preflight_{timestamp}_{counter}"
        counter += 1
    out.mkdir(parents=True)
    write_csv(out / f"final_training_plan{suffix}.csv", FINAL_PLAN_FIELDS, final_rows)
    write_csv(out / f"quarantine_manifest{suffix}.csv", QUARANTINE_FIELDS, quarantine_rows)
    (out / f"final_training_preflight_summary{suffix}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = [
        "# Final Training Red Batch Preflight",
        "",
        f"- Source pairs: {summary['source_pair_count']}",
        f"- Quarantined pairs: {summary['quarantined_pair_count']}",
        f"- Final training pairs: {summary['final_training_pair_count']}",
        f"- Final files: {summary['final_training_file_count']}",
        f"- Final ID range: {summary['final_id_start']}-{summary['final_id_end']}",
        f"- Role swap pairs: {summary['role_swap_pair_sequences']}",
        f"- Quarantined pairs: {summary['quarantined_pair_sequences']}",
    ]
    (out / f"final_training_preflight_report{suffix}.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return out


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def validate_apply_rows(rows: list[dict[str, str]], output_dir: Path) -> None:
    if not rows or len(rows) % 2:
        raise FinalBatchError(f"Final file count must be positive and even; found {len(rows)}.")
    by_pair: dict[str, list[dict[str, str]]] = {}
    names: set[str] = set()
    ids = sorted({int(row["final_target_id"]) for row in rows})
    if ids != list(range(min(ids), max(ids) + 1)):
        raise FinalBatchError("Final IDs must be contiguous.")
    for row in rows:
        by_pair.setdefault(row["final_pair_sequence"], []).append(row)
        source = Path(row["source_path"])
        if not source.is_file() or sha256_file(source) != row["source_sha256"]:
            raise FinalBatchError(f"Source hash mismatch during apply: {source}")
        readable, _, _ = read_image_size(source)
        if not readable:
            raise FinalBatchError(f"Source image unreadable during apply: {source}")
        name = row["final_output_filename"]
        if name.casefold() in names or (output_dir / name).exists():
            raise FinalBatchError(f"Output filename collision: {name}")
        names.add(name.casefold())
    if len(by_pair) != len(ids):
        raise FinalBatchError(f"Final pair count must match target ID count; found {len(by_pair)} pairs and {len(ids)} IDs.")
    for pair, pair_rows in by_pair.items():
        if len(pair_rows) != 2 or sorted(row["final_role"] for row in pair_rows) != ["marker", "raw"]:
            raise FinalBatchError(f"Final pair {pair} must have exactly one raw and one marker.")


def finalize_staging_dir(staging_dir: Path, output_dir: Path) -> None:
    last_error: OSError | None = None
    for attempt in range(5):
        try:
            staging_dir.rename(output_dir)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.2 * (attempt + 1))
    raise FinalBatchError(f"Could not finalize staged output directory after 5 retries: {last_error}")


def apply_plan(plan_csv: Path, output_dir: Path, apply_confirmed: bool) -> Path:
    if not apply_confirmed:
        raise FinalBatchError("apply requires the explicit --apply flag; no files were changed.")
    rows = load_csv(plan_csv)
    source_dirs = {Path(row["source_path"]).parent.resolve(strict=False) for row in rows}
    for source_dir in source_dirs:
        output = output_dir.resolve(strict=False)
        if output == source_dir or is_relative_to(output, source_dir):
            raise FinalBatchError(f"Output directory is not allowed: {output_dir}")
    validate_output_dir(output_dir, Path("__not_the_input_dir__"))
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FinalBatchError(f"Output directory must be absent or empty: {output_dir}")
    validate_apply_rows(rows, output_dir)
    version = "v2" if plan_csv.name.endswith("_v2.csv") else ""
    suffix = "_v2" if version == "v2" else ""
    quarantine_path = plan_csv.parent / f"quarantine_manifest{suffix}.csv"
    quarantine_rows = load_csv(quarantine_path) if quarantine_path.exists() else []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    staging = output_dir.parent / f".{output_dir.name}_staging_{timestamp}"
    if staging.exists():
        raise FinalBatchError(f"Temporary staging directory already exists: {staging}")
    staging.mkdir(parents=True)
    manifest_rows: list[dict[str, str]] = []
    try:
        for row in rows:
            source = Path(row["source_path"])
            target = staging / row["final_output_filename"]
            shutil.copy2(source, target)
            out_sha = sha256_file(target)
            if out_sha != row["source_sha256"]:
                raise FinalBatchError(f"Copied SHA-256 mismatch: {source}")
            manifest_rows.append(
                {
                    "final_pair_sequence": row["final_pair_sequence"],
                    "final_target_id": row["final_target_id"],
                    "final_role": row["final_role"],
                    "final_marker_color": row["final_marker_color"],
                    "source_filename": row["source_filename"],
                    "source_sha256": row["source_sha256"],
                    "output_filename": row["final_output_filename"],
                    "output_sha256": out_sha,
                    "original_pair_sequence": row["original_pair_sequence"],
                    "original_target_id": row["original_target_id"],
                    "resolution_source": row["resolution_source"],
                    "operation_mode": "copy",
                    "timestamp": timestamp,
                }
            )
        write_csv(staging / f"final_training_manifest{suffix}.csv", MANIFEST_FIELDS, manifest_rows)
        write_csv(staging / f"quarantine_manifest{suffix}.csv", QUARANTINE_FIELDS, quarantine_rows)
        ids = sorted({int(row["final_target_id"]) for row in rows})
        summary = {
            "final_training_pair_count": len(ids),
            "final_training_file_count": len(rows),
            "final_id_start": min(ids),
            "final_id_end": max(ids),
            "operation_mode": "copy",
            "timestamp": timestamp,
        }
        (staging / f"final_training_summary{suffix}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if output_dir.exists():
            output_dir.rmdir()
        finalize_staging_dir(staging, output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return output_dir


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize final trainable red-marker batch from frozen pair plan.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--plan-csv", required=True, type=Path)
    preflight.add_argument("--input-dir", required=True, type=Path)
    preflight.add_argument("--resolution-csv", required=True, type=Path)
    preflight.add_argument("--output-dir", required=True, type=Path)
    preflight.add_argument("--start-id", required=True, type=int)
    preflight.add_argument("--expected-source-pairs", type=int)
    preflight.add_argument("--expected-quarantined-pairs", type=int)
    preflight.add_argument("--expected-final-pairs", type=int)
    preflight.add_argument("--expected-final-files", type=int)
    preflight.add_argument("--v1-final-plan-csv", type=Path)
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--plan-csv", required=True, type=Path)
    apply_parser.add_argument("--output-dir", required=True, type=Path)
    apply_parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "preflight":
            final_rows, quarantine_rows, summary = build_preflight(
                args.plan_csv,
                args.input_dir,
                args.resolution_csv,
                args.output_dir,
                args.start_id,
                args.expected_source_pairs,
                args.expected_quarantined_pairs,
                args.expected_final_pairs,
                args.expected_final_files,
                args.v1_final_plan_csv,
            )
            out = write_preflight(final_rows, quarantine_rows, summary, "v2" if is_v2_resolution(args.resolution_csv) else "")
            print(f"Final training preflight written: {out}")
        elif args.command == "apply":
            out = apply_plan(args.plan_csv, args.output_dir, args.apply)
            print(f"Final training batch written: {out}")
        return 0
    except FinalBatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
