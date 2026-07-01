from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


REQUIRED_COLUMNS = [
    "sorted_position",
    "pair_sequence",
    "source_filename",
    "source_path",
    "source_sha256",
    "width",
    "height",
    "role_proposed",
    "marker_evidence_score",
    "validation_status",
    "target_id",
]
CSV_FIELDS = [
    "pair_sequence",
    "target_id",
    "sorted_position",
    "source_filename",
    "source_sha256",
    "paired_source_filename",
    "paired_source_sha256",
    "same_sha256_within_pair",
    "width",
    "height",
    "paired_width",
    "paired_height",
    "red_marker_score",
    "paired_red_marker_score",
    "role_proposed",
    "paired_role_proposed",
    "validation_status",
    "integrity_classification",
    "rename_eligible",
    "recommended_next_action",
    "human_review_required",
]
CLASSIFICATIONS = [
    "EXACT_DUPLICATE_WITHIN_PAIR",
    "DISTINCT_IMAGES_ROLE_UNCERTAIN",
    "DISTINCT_IMAGES_DIMENSION_MISMATCH",
    "IMAGE_READ_ERROR",
    "PLAN_STRUCTURE_ERROR",
]


class PairIntegrityAuditError(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_plan(plan_csv: Path) -> list[dict[str, str]]:
    with plan_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise PairIntegrityAuditError("Plan is missing required columns: " + ", ".join(missing))
        return list(reader)


def selected_pairs(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    pairs: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if row["validation_status"].strip().casefold() == "both_marker_like":
            pairs.setdefault(row["pair_sequence"], []).append(row)
    return dict(sorted(pairs.items(), key=lambda item: int(item[0])))


def read_image_info(path: Path) -> tuple[bool, int, int, int]:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        return False, 0, 0, 0
    height, width = image.shape[:2]
    channels = 1 if image.ndim == 2 else int(image.shape[2])
    return True, int(width), int(height), channels


def classify_pair(pair_rows: list[dict[str, str]]) -> tuple[str, bool, str, bool, list[dict[str, object]]]:
    if len(pair_rows) != 2:
        return (
            "PLAN_STRUCTURE_ERROR",
            False,
            "Fix plan structure so this unresolved pair has exactly two rows.",
            False,
            [],
        )

    ordered = sorted(pair_rows, key=lambda row: int(row["sorted_position"]))
    infos: list[dict[str, object]] = []
    for row in ordered:
        source = Path(row["source_path"])
        exists = source.is_file()
        actual_sha = sha256_file(source) if exists else ""
        sha_matches = exists and actual_sha == row["source_sha256"]
        readable, width, height, channels = read_image_info(source) if exists else (False, 0, 0, 0)
        infos.append(
            {
                "row": row,
                "exists": exists,
                "sha_matches": sha_matches,
                "readable": readable,
                "width": width,
                "height": height,
                "channels": channels,
                "extension": source.suffix.casefold(),
            }
        )

    if any(not info["exists"] or not info["sha_matches"] for info in infos):
        return ("IMAGE_READ_ERROR", False, "Recover or replace the missing/changed source image before rename.", False, infos)
    if any(not info["readable"] for info in infos):
        return ("IMAGE_READ_ERROR", False, "Recover or replace the unreadable source image before rename.", False, infos)

    same_sha = ordered[0]["source_sha256"] == ordered[1]["source_sha256"]
    if same_sha:
        return (
            "EXACT_DUPLICATE_WITHIN_PAIR",
            False,
            "Request the missing raw/marker counterpart again; do not assign raw/marker labels to duplicate bytes.",
            False,
            infos,
        )

    same_dimensions = (
        infos[0]["width"] == infos[1]["width"]
        and infos[0]["height"] == infos[1]["height"]
        and infos[0]["channels"] == infos[1]["channels"]
    )
    if not same_dimensions:
        return (
            "DISTINCT_IMAGES_DIMENSION_MISMATCH",
            False,
            "Inspect source files and recover the mismatched counterpart before rename.",
            False,
            infos,
        )

    return (
        "DISTINCT_IMAGES_ROLE_UNCERTAIN",
        True,
        "Human should choose which image is raw and which is red marker; do not change source files.",
        True,
        infos,
    )


def make_review_image(pair_rows: list[dict[str, str]], output_path: Path, label: str) -> None:
    panels = []
    for row in sorted(pair_rows, key=lambda item: int(item["sorted_position"])):
        image = cv2.imread(row["source_path"], cv2.IMREAD_COLOR)
        if image is None:
            image = np.full((260, 360, 3), 245, dtype=np.uint8)
        image = cv2.resize(image, (360, 260), interpolation=cv2.INTER_AREA)
        lines = [
            label,
            f"pair {row['pair_sequence']} target {row['target_id']} pos {row['sorted_position']}",
            row["source_filename"][:44],
            f"sha {row['source_sha256'][:12]} score {row['marker_evidence_score']}",
            f"proposed role {row['role_proposed']}",
        ]
        y = 20
        for line in lines:
            cv2.putText(image, line, (7, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(image, line, (7, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
            y += 22
        panels.append(image)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), np.hstack(panels))


def audit_pairs(plan_csv: Path, input_dir: Path, output_dir: Path | None = None) -> Path:
    if not input_dir.is_dir():
        raise PairIntegrityAuditError(f"Input directory does not exist: {input_dir}")
    rows = load_plan(plan_csv)
    pairs = selected_pairs(rows)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_dir = output_dir or repo_root() / "tmp" / "line_sorted_import" / f"unresolved_pair_integrity_{timestamp}"
    counter = 1
    while audit_dir.exists():
        audit_dir = repo_root() / "tmp" / "line_sorted_import" / f"unresolved_pair_integrity_{timestamp}_{counter}"
        counter += 1
    duplicate_dir = audit_dir / "duplicate_pair_review"
    marker_dir = audit_dir / "marker_role_review"
    duplicate_dir.mkdir(parents=True)
    marker_dir.mkdir(parents=True)

    csv_rows: list[dict[str, str]] = []
    pair_classes: dict[str, str] = {}
    blocked_pairs: list[int] = []
    request_again: list[str] = []
    for pair_sequence, pair_rows in pairs.items():
        classification, rename_eligible, action, human_review, infos = classify_pair(pair_rows)
        pair_classes[pair_sequence] = classification
        if not rename_eligible:
            blocked_pairs.append(int(pair_sequence))
        ordered = sorted(pair_rows, key=lambda row: int(row["sorted_position"]))
        if classification == "EXACT_DUPLICATE_WITHIN_PAIR":
            request_again.extend(row["source_filename"] for row in ordered)
            make_review_image(
                ordered,
                duplicate_dir / f"pair_{int(pair_sequence):04d}.jpg",
                "DUPLICATE PAIR - DO NOT ASSIGN RAW/MARKER YET",
            )
        elif classification == "DISTINCT_IMAGES_ROLE_UNCERTAIN":
            make_review_image(
                ordered,
                marker_dir / f"pair_{int(pair_sequence):04d}.jpg",
                "MARKER ROLE REVIEW",
            )

        info_by_name = {str(info["row"]["source_filename"]): info for info in infos}
        for index, row in enumerate(ordered):
            paired = ordered[1 - index] if len(ordered) == 2 else {}
            info = info_by_name.get(row["source_filename"], {})
            paired_info = info_by_name.get(paired.get("source_filename", ""), {})
            csv_rows.append(
                {
                    "pair_sequence": row["pair_sequence"],
                    "target_id": row.get("target_id", ""),
                    "sorted_position": row["sorted_position"],
                    "source_filename": row["source_filename"],
                    "source_sha256": row.get("source_sha256", ""),
                    "paired_source_filename": paired.get("source_filename", ""),
                    "paired_source_sha256": paired.get("source_sha256", ""),
                    "same_sha256_within_pair": "true" if paired and row.get("source_sha256") == paired.get("source_sha256") else "false",
                    "width": str(info.get("width", row.get("width", "0"))),
                    "height": str(info.get("height", row.get("height", "0"))),
                    "paired_width": str(paired_info.get("width", paired.get("width", "0"))),
                    "paired_height": str(paired_info.get("height", paired.get("height", "0"))),
                    "red_marker_score": row.get("marker_evidence_score", ""),
                    "paired_red_marker_score": paired.get("marker_evidence_score", ""),
                    "role_proposed": row.get("role_proposed", ""),
                    "paired_role_proposed": paired.get("role_proposed", ""),
                    "validation_status": row.get("validation_status", ""),
                    "integrity_classification": classification,
                    "rename_eligible": "true" if rename_eligible else "false",
                    "recommended_next_action": action,
                    "human_review_required": "true" if human_review else "false",
                }
            )

    counts = {classification: list(pair_classes.values()).count(classification) for classification in CLASSIFICATIONS}
    rename_eligible_count = counts["DISTINCT_IMAGES_ROLE_UNCERTAIN"]
    total_pairs = 184
    safe_pair_count_if_quarantined = total_pairs - len(blocked_pairs)
    summary = {
        "total_unresolved_pair_count": len(pairs),
        "exact_duplicate_within_pair_count": counts["EXACT_DUPLICATE_WITHIN_PAIR"],
        "distinct_images_role_uncertain_count": counts["DISTINCT_IMAGES_ROLE_UNCERTAIN"],
        "dimension_mismatch_count": counts["DISTINCT_IMAGES_DIMENSION_MISMATCH"],
        "image_read_error_count": counts["IMAGE_READ_ERROR"],
        "plan_structure_error_count": counts["PLAN_STRUCTURE_ERROR"],
        "rename_eligible_pair_count": rename_eligible_count,
        "rename_blocked_pair_count": len(blocked_pairs),
        "blocked_pair_sequences": sorted(blocked_pairs),
    }
    with (audit_dir / "unresolved_pair_integrity.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(csv_rows)
    (audit_dir / "unresolved_pair_integrity_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = [
        "# Unresolved Pair Integrity Audit",
        "",
        f"- Total unresolved BOTH_MARKER_LIKE pairs: {len(pairs)}",
        f"- Exact duplicate pairs: {counts['EXACT_DUPLICATE_WITHIN_PAIR']}",
        f"- Distinct-image marker-role review pairs: {counts['DISTINCT_IMAGES_ROLE_UNCERTAIN']}",
        f"- Dimension mismatch pairs: {counts['DISTINCT_IMAGES_DIMENSION_MISMATCH']}",
        f"- Image read error pairs: {counts['IMAGE_READ_ERROR']}",
        f"- Plan structure error pairs: {counts['PLAN_STRUCTURE_ERROR']}",
        f"- Pairs that cannot be renamed safely now: {sorted(blocked_pairs)}",
        f"- Maximum safe pair count if blocked pairs are temporarily quarantined: {safe_pair_count_if_quarantined}",
        f"- Original 184 pairs / IDs 16-199 assumption remains valid: {'yes' if not blocked_pairs else 'no, not until blocked pairs are resolved'}",
        "",
        "## Files To Request Again",
        "",
    ]
    if request_again:
        report.extend(f"- {name}" for name in sorted(set(request_again)))
    else:
        report.append("- None identified from exact duplicate unresolved pairs.")
    (audit_dir / "unresolved_pair_integrity_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return audit_dir


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit unresolved LINE pair integrity without modifying dataset files.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit")
    audit.add_argument("--plan-csv", required=True, type=Path)
    audit.add_argument("--input-dir", required=True, type=Path)
    audit.add_argument("--output-dir", type=Path)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "audit":
            output = audit_pairs(args.plan_csv, args.input_dir, args.output_dir)
            print(f"Unresolved pair integrity audit written: {output}")
        return 0
    except PairIntegrityAuditError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
