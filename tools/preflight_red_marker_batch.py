from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
EXPECTED_START_ID = 16
EXPECTED_END_ID = 189
CSV_FIELDS = [
    "id",
    "raw_filename",
    "marker_filename",
    "raw_sha256",
    "marker_sha256",
    "raw_width",
    "raw_height",
    "marker_width",
    "marker_height",
    "red_pixel_count",
    "red_pixel_ratio",
    "red_component_count",
    "eligible_component_count",
    "total_eligible_red_area",
    "largest_eligible_red_area",
    "estimated_dirty_spot_count",
    "red_evidence_score",
    "raw_red_pixel_count",
    "raw_largest_eligible_red_area",
    "raw_source_filename",
    "original_pair_sequence",
    "validation_status",
]
REVIEW_FIELDS = [
    "raw_source_sha256",
    "source_filename",
    "previous_v1_target_id",
    "final_v2_target_id",
    "original_pair_sequence",
    "decision",
    "reason",
    "review_status",
]


class RedMarkerPreflightError(RuntimeError):
    pass


@dataclass(frozen=True)
class RedConfig:
    min_component_area: int = 20
    saturation_min: int = 80
    value_min: int = 50


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_image(path: Path) -> np.ndarray | None:
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


def red_mask(image: np.ndarray, config: RedConfig) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_red = cv2.inRange(
        hsv,
        np.array((0, config.saturation_min, config.value_min), dtype=np.uint8),
        np.array((10, 255, 255), dtype=np.uint8),
    )
    upper_red = cv2.inRange(
        hsv,
        np.array((170, config.saturation_min, config.value_min), dtype=np.uint8),
        np.array((179, 255, 255), dtype=np.uint8),
    )
    return cv2.bitwise_or(lower_red, upper_red)


def analyze_red(image: np.ndarray, config: RedConfig) -> dict[str, object]:
    mask = red_mask(image, config)
    red_pixel_count = int(cv2.countNonZero(mask))
    component_count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, 8)
    all_areas: list[int] = []
    eligible_areas: list[int] = []
    for label in range(1, component_count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        all_areas.append(area)
        if area >= config.min_component_area:
            eligible_areas.append(area)
    total_area = int(sum(eligible_areas))
    largest_area = int(max(eligible_areas) if eligible_areas else 0)
    total_pixels = int(image.shape[0] * image.shape[1])
    return {
        "red_pixel_count": red_pixel_count,
        "red_pixel_ratio": red_pixel_count / total_pixels if total_pixels else 0.0,
        "red_component_count": len(all_areas),
        "eligible_component_count": len(eligible_areas),
        "total_eligible_red_area": total_area,
        "largest_eligible_red_area": largest_area,
        "estimated_dirty_spot_count": len(eligible_areas),
        "red_evidence_score": total_area,
    }


def parse_batch_files(input_dir: Path) -> tuple[dict[int, Path], dict[int, Path], list[str]]:
    raw: dict[int, Path] = {}
    marker: dict[int, Path] = {}
    unsupported: list[str] = []
    pattern = re.compile(r"^(\d+)(m)?(\.[^.]+)$", re.IGNORECASE)
    for path in input_dir.iterdir():
        if not path.is_file() or path.name in {
            "final_training_manifest.csv",
            "final_training_summary.json",
            "quarantine_manifest.csv",
            "final_training_manifest_v2.csv",
            "final_training_summary_v2.json",
            "quarantine_manifest_v2.csv",
        }:
            continue
        match = pattern.match(path.name)
        if not match or path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
            unsupported.append(path.name)
            continue
        image_id = int(match.group(1))
        target = marker if match.group(2) else raw
        if image_id in target:
            unsupported.append(path.name)
            continue
        target[image_id] = path
    return raw, marker, unsupported


def load_manifest_provenance(input_dir: Path) -> dict[str, dict[str, str]]:
    for name in ["final_training_manifest_v2.csv", "final_training_manifest.csv"]:
        manifest = input_dir / name
        if manifest.is_file():
            with manifest.open("r", newline="", encoding="utf-8") as handle:
                return {row["output_filename"]: row for row in csv.DictReader(handle)}
    return {}


def load_review_resolution(path: Path | None) -> set[tuple[str, str, str]]:
    if path is None:
        return set()
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in REVIEW_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise RedMarkerPreflightError("Review resolution CSV missing columns: " + ", ".join(missing))
        approved: set[tuple[str, str, str]] = set()
        blocked_v1_ids = {"96", "101", "103"}
        for row in reader:
            if row["decision"] != "APPROVED_RAW_RED_CONTENT" or row["review_status"] != "APPROVED":
                raise RedMarkerPreflightError("Review resolution rows must be approved raw-red-content decisions.")
            if row["previous_v1_target_id"] in blocked_v1_ids:
                raise RedMarkerPreflightError(f"Removed V1 target ID appears in review resolution: {row['previous_v1_target_id']}")
            key = (row["raw_source_sha256"], row["source_filename"], row["original_pair_sequence"])
            if key in approved:
                raise RedMarkerPreflightError("Duplicate review resolution composite key.")
            approved.add(key)
    return approved


def classify_pair(
    raw_path: Path | None,
    marker_path: Path | None,
    config: RedConfig,
) -> tuple[dict[str, str], dict[str, object] | None, dict[str, object] | None, np.ndarray | None, np.ndarray | None]:
    if raw_path is None or marker_path is None:
        return ({"validation_status": "PAIR_STRUCTURE_ERROR"}, None, None, None, None)
    raw_image = read_image(raw_path)
    marker_image = read_image(marker_path)
    raw_sha = sha256_file(raw_path)
    marker_sha = sha256_file(marker_path)
    if raw_image is None or marker_image is None:
        return ({"validation_status": "IMAGE_READ_ERROR", "raw_sha256": raw_sha, "marker_sha256": marker_sha}, None, None, raw_image, marker_image)
    raw_height, raw_width = raw_image.shape[:2]
    marker_height, marker_width = marker_image.shape[:2]
    raw_analysis = analyze_red(raw_image, config)
    marker_analysis = analyze_red(marker_image, config)
    status = "SAFE_MARKER_PAIR"
    if (raw_width, raw_height) != (marker_width, marker_height):
        status = "DIMENSION_MISMATCH"
    elif raw_sha == marker_sha:
        status = "PAIR_STRUCTURE_ERROR"
    elif int(marker_analysis["eligible_component_count"]) == 0:
        status = "NO_RED_MARKER" if int(marker_analysis["red_component_count"]) == 0 else "WEAK_RED_MARKER"
    elif int(raw_analysis["eligible_component_count"]) > 0:
        status = "RAW_RED_ANOMALY"
    base = {
        "validation_status": status,
        "raw_sha256": raw_sha,
        "marker_sha256": marker_sha,
        "raw_width": str(raw_width),
        "raw_height": str(raw_height),
        "marker_width": str(marker_width),
        "marker_height": str(marker_height),
    }
    return base, raw_analysis, marker_analysis, raw_image, marker_image


def make_review_image(row: dict[str, str], raw_image: np.ndarray | None, marker_image: np.ndarray | None, output_path: Path) -> None:
    panels = []
    for label, image in [("RAW", raw_image), ("MARKER", marker_image)]:
        if image is None:
            image = np.full((260, 360, 3), 245, dtype=np.uint8)
        image = cv2.resize(image, (360, 260), interpolation=cv2.INTER_AREA)
        lines = [
            f"ID {row['id']} {label}",
            f"raw {row['raw_filename']}",
            f"marker {row['marker_filename']}",
            f"sha {row['raw_sha256'][:10]} / {row['marker_sha256'][:10]}",
            f"components {row['eligible_component_count']} area {row['total_eligible_red_area']}",
            f"largest {row['largest_eligible_red_area']} status {row['validation_status']}",
        ]
        y = 20
        for line in lines:
            cv2.putText(image, line, (7, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(image, line, (7, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
            y += 22
        panels.append(image)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), np.hstack(panels))


def run_preflight(
    input_dir: Path,
    output_dir: Path | None = None,
    config: RedConfig = RedConfig(),
    review_resolution_csv: Path | None = None,
) -> Path:
    if not input_dir.is_dir():
        raise RedMarkerPreflightError(f"Input directory does not exist: {input_dir}")
    raw_files, marker_files, unsupported = parse_batch_files(input_dir)
    provenance = load_manifest_provenance(input_dir)
    approved_review_keys = load_review_resolution(review_resolution_csv)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    is_v2 = (input_dir / "final_training_manifest_v2.csv").is_file()
    root_name = "red_marker_preflight_v2" if is_v2 else "red_marker_preflight"
    suffix = "_v2" if is_v2 else ""
    out = output_dir or repo_root() / "tmp" / root_name / f"run_{timestamp}"
    counter = 1
    while out.exists():
        out = repo_root() / "tmp" / root_name / f"run_{timestamp}_{counter}"
        counter += 1
    review_dir = out / "review_pairs"
    review_dir.mkdir(parents=True)
    rows: list[dict[str, str]] = []
    status_counts: dict[str, int] = {}
    total_dirty_spots = 0
    expected_ids = sorted(set(raw_files) | set(marker_files))
    if not expected_ids:
        raise RedMarkerPreflightError(f"No supported numeric image pairs found in {input_dir}")
    if expected_ids != list(range(min(expected_ids), max(expected_ids) + 1)):
        unsupported.append("non_contiguous_numeric_ids")
    for image_id in expected_ids:
        raw_path = raw_files.get(image_id)
        marker_path = marker_files.get(image_id)
        base, raw_analysis, marker_analysis, raw_image, marker_image = classify_pair(raw_path, marker_path, config)
        marker_analysis = marker_analysis or {
            "red_pixel_count": 0,
            "red_pixel_ratio": 0.0,
            "red_component_count": 0,
            "eligible_component_count": 0,
            "total_eligible_red_area": 0,
            "largest_eligible_red_area": 0,
            "estimated_dirty_spot_count": 0,
            "red_evidence_score": 0,
        }
        raw_analysis = raw_analysis or {"red_pixel_count": 0, "largest_eligible_red_area": 0}
        raw_provenance = provenance.get(raw_path.name if raw_path else "", {})
        if base["validation_status"] == "RAW_RED_ANOMALY":
            review_key = (
                base.get("raw_sha256", ""),
                raw_provenance.get("source_filename", ""),
                raw_provenance.get("original_pair_sequence", ""),
            )
            if review_key in approved_review_keys:
                base["validation_status"] = "APPROVED_RAW_RED_CONTENT"
        row = {
            "id": str(image_id),
            "raw_filename": raw_path.name if raw_path else "",
            "marker_filename": marker_path.name if marker_path else "",
            "raw_sha256": base.get("raw_sha256", ""),
            "marker_sha256": base.get("marker_sha256", ""),
            "raw_width": base.get("raw_width", "0"),
            "raw_height": base.get("raw_height", "0"),
            "marker_width": base.get("marker_width", "0"),
            "marker_height": base.get("marker_height", "0"),
            "red_pixel_count": str(marker_analysis["red_pixel_count"]),
            "red_pixel_ratio": f"{float(marker_analysis['red_pixel_ratio']):.10f}",
            "red_component_count": str(marker_analysis["red_component_count"]),
            "eligible_component_count": str(marker_analysis["eligible_component_count"]),
            "total_eligible_red_area": str(marker_analysis["total_eligible_red_area"]),
            "largest_eligible_red_area": str(marker_analysis["largest_eligible_red_area"]),
            "estimated_dirty_spot_count": str(marker_analysis["estimated_dirty_spot_count"]),
            "red_evidence_score": str(marker_analysis["red_evidence_score"]),
            "raw_red_pixel_count": str(raw_analysis["red_pixel_count"]),
            "raw_largest_eligible_red_area": str(raw_analysis["largest_eligible_red_area"]),
            "raw_source_filename": raw_provenance.get("source_filename", ""),
            "original_pair_sequence": raw_provenance.get("original_pair_sequence", ""),
            "validation_status": base["validation_status"],
        }
        rows.append(row)
        status_counts[row["validation_status"]] = status_counts.get(row["validation_status"], 0) + 1
        total_dirty_spots += int(row["estimated_dirty_spot_count"])
        if row["validation_status"] not in {"SAFE_MARKER_PAIR", "APPROVED_RAW_RED_CONTENT"}:
            make_review_image(row, raw_image, marker_image, review_dir / f"id_{image_id:04d}_{row['validation_status']}.jpg")
    extra_ids = sorted((set(raw_files) | set(marker_files)) - set(expected_ids))
    if unsupported or extra_ids:
        status_counts["PAIR_STRUCTURE_ERROR"] = status_counts.get("PAIR_STRUCTURE_ERROR", 0) + len(unsupported) + len(extra_ids)
    with (out / f"red_marker_preflight{suffix}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    safe_count = status_counts.get("SAFE_MARKER_PAIR", 0)
    approved_raw_count = status_counts.get("APPROVED_RAW_RED_CONTENT", 0)
    exception_count = len(expected_ids) - safe_count - approved_raw_count + len(unsupported) + len(extra_ids)
    summary = {
        "input_dir": str(input_dir),
        "total_pair_count": len(expected_ids),
        "total_image_file_count": len(raw_files) + len(marker_files),
        "expected_id_start": min(expected_ids),
        "expected_id_end": max(expected_ids),
        "safe_pair_count": safe_count,
        "exception_count": exception_count,
        "status_counts": status_counts,
        "estimated_dirty_spot_count": total_dirty_spots,
        "unsupported_names": unsupported,
        "extra_numeric_ids": extra_ids,
        "ground_truth_created": False,
        "safe_to_proceed_to_red_ground_truth": exception_count == 0,
    }
    (out / f"red_marker_preflight_summary{suffix}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = [
        "# Red Marker Batch Preflight",
        "",
        f"- Total pairs checked: {summary['total_pair_count']}",
        f"- Image files discovered: {summary['total_image_file_count']}",
        f"- ID range: {min(expected_ids)}-{max(expected_ids)}",
        f"- Safe pairs: {safe_count}",
        f"- Exceptions: {exception_count}",
        f"- Estimated dirty spots: {total_dirty_spots}",
        f"- Safe to proceed to red Ground Truth generation: {'yes' if exception_count == 0 else 'no'}",
        "",
        "## Status Counts",
        "",
    ]
    report.extend(f"- {status}: {count}" for status, count in sorted(status_counts.items()))
    (out / f"red_marker_preflight_report{suffix}.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return out


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only preflight for finalized red-marker training batch.")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--min-component-area", type=int, default=RedConfig.min_component_area)
    parser.add_argument("--saturation-min", type=int, default=RedConfig.saturation_min)
    parser.add_argument("--value-min", type=int, default=RedConfig.value_min)
    parser.add_argument("--review-resolution-csv", type=Path)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    config = RedConfig(args.min_component_area, args.saturation_min, args.value_min)
    try:
        output = run_preflight(args.input_dir, args.output_dir, config, args.review_resolution_csv)
        print(f"Red marker preflight written: {output}")
        return 0
    except RedMarkerPreflightError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
