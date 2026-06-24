from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable

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
OUTPUT_ROOT = PROJECT_ROOT / "tmp" / "marker_analysis"

ALIGNMENT_COLUMNS = [
    "image_id",
    "source_image",
    "marked_image",
    "original_width",
    "original_height",
    "marked_width",
    "marked_height",
    "estimated_x_offset",
    "estimated_y_offset",
    "alignment_confidence",
    "alignment_status",
    "notes",
]

MARKER_COLUMNS = [
    "image_id",
    "spot_id",
    "x_center",
    "y_center",
    "bbox_x",
    "bbox_y",
    "bbox_width",
    "bbox_height",
    "component_area",
    "equivalent_circle_radius",
    "enclosing_circle_radius",
    "nearest_neighbor_distance",
    "source_marked_image",
]

IMAGE_SUMMARY_COLUMNS = [
    "image_id",
    "source_image",
    "marked_image",
    "dirty_spot_count",
    "cleanliness_score",
    "pass_fail_status",
    "alignment_status",
    "alignment_confidence",
    "estimated_x_offset",
    "estimated_y_offset",
    "min_marker_area",
    "median_marker_area",
    "max_marker_area",
    "min_equivalent_radius",
    "median_equivalent_radius",
    "max_equivalent_radius",
    "min_nearest_neighbor_distance",
    "median_nearest_neighbor_distance",
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
    duplicates: list[str]
    unsupported_extensions: list[str]


@dataclass(frozen=True)
class MarkerInstance:
    image_id: str
    spot_id: str
    x_center: float
    y_center: float
    bbox_x: int
    bbox_y: int
    bbox_width: int
    bbox_height: int
    component_area: int
    equivalent_circle_radius: float
    enclosing_circle_radius: float
    nearest_neighbor_distance: float | None
    source_marked_image: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Blue Marker Analysis for RawPics image pairs. "
            "This tool does not train a model and does not modify source images."
        )
    )
    parser.add_argument("--raw-dir", required=True, help="Directory containing original/marked pairs.")
    parser.add_argument("--output-dir", required=True, help="Output directory under tmp/marker_analysis.")
    return parser.parse_args()


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        resolved = path.resolve()
    else:
        resolved = (PROJECT_ROOT / path).resolve()
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
        raise ValueError("Output directory must stay under tmp/marker_analysis") from exc
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

    names_seen: dict[str, Path] = {}
    duplicates: list[str] = []
    for path in image_files:
        key = path.name.lower()
        if key in names_seen:
            duplicates.append(f"{names_seen[key].name} / {path.name}")
        else:
            names_seen[key] = path

    marked_files = sorted(
        [path for path in image_files if path.stem.endswith("m")],
        key=natural_image_key,
    )
    original_files = [path for path in image_files if not path.stem.endswith("m")]
    original_lookup = {path.with_suffix(path.suffix.lower()).name.lower(): path for path in original_files}

    pairs: list[ImagePair] = []
    missing_originals: list[str] = []
    paired_originals: set[Path] = set()
    for marked_path in marked_files:
        try:
            original_path = original_for_marked(marked_path)
        except ValueError:
            missing_originals.append(marked_path.name)
            continue
        lookup_key = original_path.with_suffix(original_path.suffix.lower()).name.lower()
        actual_original = original_lookup.get(lookup_key)
        if actual_original is None:
            missing_originals.append(marked_path.name)
            continue
        paired_originals.add(actual_original)
        pairs.append(
            ImagePair(
                image_id=actual_original.stem,
                original_path=actual_original,
                marked_path=marked_path,
            )
        )

    missing_marked = sorted(
        original.name
        for original in original_files
        if original not in paired_originals
    )

    return PairDiscovery(
        pairs=pairs,
        missing_originals=missing_originals,
        missing_marked=missing_marked,
        duplicates=sorted(duplicates),
        unsupported_extensions=unsupported,
    )


def read_image(path: Path) -> np.ndarray | None:
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


def alignment_status(
    same_dimensions: bool,
    x_offset: float | None,
    y_offset: float | None,
    confidence: float | None,
) -> str:
    if not same_dimensions or x_offset is None or y_offset is None or confidence is None:
        return "FAIL"
    max_offset = max(abs(x_offset), abs(y_offset))
    if max_offset <= 2.0 and confidence >= 0.25:
        return "PASS"
    if max_offset <= 6.0 and confidence >= 0.10:
        return "WARNING"
    return "FAIL"


def estimate_alignment(original: np.ndarray | None, marked: np.ndarray | None) -> dict[str, object]:
    if original is None or marked is None:
        return {
            "original_width": "",
            "original_height": "",
            "marked_width": "",
            "marked_height": "",
            "estimated_x_offset": "",
            "estimated_y_offset": "",
            "alignment_confidence": "",
            "alignment_status": "FAIL",
            "notes": "could_not_read_image",
        }

    original_height, original_width = original.shape[:2]
    marked_height, marked_width = marked.shape[:2]
    same_dimensions = (original_width, original_height) == (marked_width, marked_height)
    if not same_dimensions:
        return {
            "original_width": original_width,
            "original_height": original_height,
            "marked_width": marked_width,
            "marked_height": marked_height,
            "estimated_x_offset": "",
            "estimated_y_offset": "",
            "alignment_confidence": "",
            "alignment_status": "FAIL",
            "notes": "dimension_mismatch",
        }

    original_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY).astype(np.float32)
    marked_gray = cv2.cvtColor(marked, cv2.COLOR_BGR2GRAY).astype(np.float32)
    window = cv2.createHanningWindow((original_width, original_height), cv2.CV_32F)
    (x_offset, y_offset), confidence = cv2.phaseCorrelate(original_gray, marked_gray, window)
    status = alignment_status(True, x_offset, y_offset, confidence)
    return {
        "original_width": original_width,
        "original_height": original_height,
        "marked_width": marked_width,
        "marked_height": marked_height,
        "estimated_x_offset": round(float(x_offset), 4),
        "estimated_y_offset": round(float(y_offset), 4),
        "alignment_confidence": round(float(confidence), 6),
        "alignment_status": status,
        "notes": "phase_correlation_original_to_marked",
    }


def quality_grade(spot_count: int) -> tuple[int, str]:
    if spot_count <= 9:
        return 95, "PASS"
    if spot_count <= 20:
        return 90, "PASS"
    if spot_count <= 30:
        return 80, "PASS"
    return 70, "FAIL"


def detect_marker_instances(marked_image: np.ndarray, image_id: str, source_marked_image: str) -> list[MarkerInstance]:
    blue_mask = detect_blue_mask(marked_image)
    component_count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        (blue_mask > 0).astype(np.uint8),
        connectivity=8,
    )

    instances: list[MarkerInstance] = []
    for label in range(1, component_count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < MIN_BLUE_COMPONENT_AREA:
            continue

        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        center_x = float(centroids[label][0])
        center_y = float(centroids[label][1])
        equivalent_radius = math.sqrt(area / math.pi)

        component_mask = (labels[y : y + height, x : x + width] == label).astype(np.uint8)
        contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            contour = max(contours, key=cv2.contourArea)
            (_, _), enclosing_radius = cv2.minEnclosingCircle(contour)
        else:
            enclosing_radius = max(width, height) / 2.0

        instances.append(
            MarkerInstance(
                image_id=image_id,
                spot_id=f"{image_id}_spot_{len(instances) + 1:03d}",
                x_center=round(center_x, 4),
                y_center=round(center_y, 4),
                bbox_x=x,
                bbox_y=y,
                bbox_width=width,
                bbox_height=height,
                component_area=area,
                equivalent_circle_radius=round(float(equivalent_radius), 4),
                enclosing_circle_radius=round(float(enclosing_radius), 4),
                nearest_neighbor_distance=None,
                source_marked_image=source_marked_image,
            )
        )

    return with_nearest_neighbor_distances(instances)


def with_nearest_neighbor_distances(instances: list[MarkerInstance]) -> list[MarkerInstance]:
    if len(instances) < 2:
        return instances
    updated: list[MarkerInstance] = []
    centers = np.array([[marker.x_center, marker.y_center] for marker in instances], dtype=np.float32)
    for index, marker in enumerate(instances):
        distances = np.linalg.norm(centers - centers[index], axis=1)
        distances[index] = np.inf
        nearest = round(float(np.min(distances)), 4)
        updated.append(
            MarkerInstance(
                image_id=marker.image_id,
                spot_id=marker.spot_id,
                x_center=marker.x_center,
                y_center=marker.y_center,
                bbox_x=marker.bbox_x,
                bbox_y=marker.bbox_y,
                bbox_width=marker.bbox_width,
                bbox_height=marker.bbox_height,
                component_area=marker.component_area,
                equivalent_circle_radius=marker.equivalent_circle_radius,
                enclosing_circle_radius=marker.enclosing_circle_radius,
                nearest_neighbor_distance=nearest,
                source_marked_image=marker.source_marked_image,
            )
        )
    return updated


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    return round(float(np.percentile(np.array(values, dtype=np.float64), pct)), 4)


def distribution(values: Iterable[float]) -> dict[str, float | int | None]:
    clean_values = [float(value) for value in values if value is not None and not math.isnan(float(value))]
    return {
        "count": len(clean_values),
        "min": percentile(clean_values, 0),
        "p05": percentile(clean_values, 5),
        "p25": percentile(clean_values, 25),
        "median": percentile(clean_values, 50),
        "p75": percentile(clean_values, 75),
        "p95": percentile(clean_values, 95),
        "max": percentile(clean_values, 100),
    }


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def marker_to_row(marker: MarkerInstance) -> dict[str, object]:
    return {
        "image_id": marker.image_id,
        "spot_id": marker.spot_id,
        "x_center": marker.x_center,
        "y_center": marker.y_center,
        "bbox_x": marker.bbox_x,
        "bbox_y": marker.bbox_y,
        "bbox_width": marker.bbox_width,
        "bbox_height": marker.bbox_height,
        "component_area": marker.component_area,
        "equivalent_circle_radius": marker.equivalent_circle_radius,
        "enclosing_circle_radius": marker.enclosing_circle_radius,
        "nearest_neighbor_distance": (
            "" if marker.nearest_neighbor_distance is None else marker.nearest_neighbor_distance
        ),
        "source_marked_image": marker.source_marked_image,
    }


def median_or_blank(values: list[float]) -> float | str:
    if not values:
        return ""
    return percentile(values, 50) or ""


def min_or_blank(values: list[float]) -> float | str:
    return round(min(values), 4) if values else ""


def max_or_blank(values: list[float]) -> float | str:
    return round(max(values), 4) if values else ""


def make_preview(
    marked_image: np.ndarray,
    markers: list[MarkerInstance],
    destination: Path,
    image_id: str,
    spot_count: int,
) -> None:
    preview = marked_image.copy()
    for marker in markers:
        radius = max(8, int(round(marker.enclosing_circle_radius + 4)))
        center = (int(round(marker.x_center)), int(round(marker.y_center)))
        cv2.circle(preview, center, radius, (0, 255, 255), 3)
        cv2.putText(
            preview,
            marker.spot_id.rsplit("_", 1)[-1],
            (center[0] + radius + 4, max(20, center[1])),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
    cv2.putText(
        preview,
        f"{image_id}: {spot_count} spots",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 255),
        3,
        cv2.LINE_AA,
    )
    cv2.imwrite(str(destination), preview)


def summarize_outliers(
    image_rows: list[dict[str, object]],
    marker_rows: list[dict[str, object]],
) -> dict[str, list[str]]:
    spot_counts = [float(row["dirty_spot_count"]) for row in image_rows]
    area_values = [float(row["component_area"]) for row in marker_rows]
    nn_values = [
        float(row["nearest_neighbor_distance"])
        for row in marker_rows
        if row["nearest_neighbor_distance"] != ""
    ]
    high_spot_threshold = percentile(spot_counts, 95) if spot_counts else None
    high_area_threshold = percentile(area_values, 95) if area_values else None
    low_nn_threshold = percentile(nn_values, 5) if nn_values else None

    return {
        "high_spot_count_images": [
            str(row["image_id"])
            for row in image_rows
            if high_spot_threshold is not None and float(row["dirty_spot_count"]) >= high_spot_threshold
        ],
        "large_marker_images": sorted(
            {
                str(row["image_id"])
                for row in marker_rows
                if high_area_threshold is not None and float(row["component_area"]) >= high_area_threshold
            }
        ),
        "close_marker_images": sorted(
            {
                str(row["image_id"])
                for row in marker_rows
                if row["nearest_neighbor_distance"] != ""
                and low_nn_threshold is not None
                and float(row["nearest_neighbor_distance"]) <= low_nn_threshold
            }
        ),
    }


def policy_proposal_text(summary: dict[str, object]) -> str:
    area = summary["marker_area"]
    equiv = summary["equivalent_radius"]
    enclosing = summary["enclosing_radius"]
    nearest = summary["nearest_neighbor_distance"]
    spots = summary["spot_count_per_image"]
    outliers = summary["outlier_images"]

    def fmt(section: dict[str, object], key: str) -> str:
        value = section.get(key)
        return "n/a" if value is None else str(value)

    min_size_options = [
        f"Conservative: keep current crop-pipeline minimum area {MIN_BLUE_COMPONENT_AREA} px.",
        f"Balanced: consider p05 marker area around {fmt(area, 'p05')} px after reviewer spot-check.",
        f"Strict: consider p25 marker area around {fmt(area, 'p25')} px if tiny components are often noise.",
    ]
    radius_options = [
        f"Use equivalent radius median around {fmt(equiv, 'median')} px for compact point circles.",
        f"Use enclosing radius median around {fmt(enclosing, 'median')} px for visible annotation circles.",
        f"Use p75 enclosing radius around {fmt(enclosing, 'p75')} px when previews must fully cover larger marks.",
    ]
    merge_options = [
        "No automatic merge in this phase; treat each connected component as one preliminary spot.",
        f"Review pairs below p05 nearest-neighbor distance around {fmt(nearest, 'p05')} px as possible accidental splits.",
        f"Use a candidate merge-distance near p25 nearest-neighbor distance around {fmt(nearest, 'p25')} px only after human validation.",
    ]

    lines = [
        "# Blue Marker Policy Proposal",
        "",
        "This report is evidence only. It does not finalize marker-size, radius, or merge-distance policy.",
        "",
        "## Observed Distributions",
        "",
        f"- Marker area: min {fmt(area, 'min')}, median {fmt(area, 'median')}, p95 {fmt(area, 'p95')}, max {fmt(area, 'max')} px.",
        f"- Equivalent radius: min {fmt(equiv, 'min')}, median {fmt(equiv, 'median')}, p95 {fmt(equiv, 'p95')}, max {fmt(equiv, 'max')} px.",
        f"- Enclosing radius: min {fmt(enclosing, 'min')}, median {fmt(enclosing, 'median')}, p95 {fmt(enclosing, 'p95')}, max {fmt(enclosing, 'max')} px.",
        f"- Nearest-neighbor distance: min {fmt(nearest, 'min')}, median {fmt(nearest, 'median')}, p95 {fmt(nearest, 'p95')}, max {fmt(nearest, 'max')} px.",
        f"- Spot count per image: min {fmt(spots, 'min')}, median {fmt(spots, 'median')}, p95 {fmt(spots, 'p95')}, max {fmt(spots, 'max')}.",
        "",
        "## Minimum-size Threshold Options",
        "",
    ]
    lines.extend(f"- {item}" for item in min_size_options)
    lines.extend(["", "## Circle-radius Rule Options", ""])
    lines.extend(f"- {item}" for item in radius_options)
    lines.extend(["", "## Merge-distance Evidence Options", ""])
    lines.extend(f"- {item}" for item in merge_options)
    lines.extend(
        [
            "",
            "## Outlier Images To Review",
            "",
            f"- High spot count images: {', '.join(outliers['high_spot_count_images']) or 'none'}",
            f"- Large marker images: {', '.join(outliers['large_marker_images']) or 'none'}",
            f"- Close marker images: {', '.join(outliers['close_marker_images']) or 'none'}",
            "",
            "## Business Risk Note",
            "",
            "False Accept is the highest business risk, so any future automatic merge or minimum-size threshold should be validated against missed dirty spots before use.",
        ]
    )
    return "\n".join(lines) + "\n"


def analyze(raw_dir: Path, output_dir: Path) -> dict[str, object]:
    discovery = discover_image_pairs(raw_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_dir = output_dir / "previews"
    preview_dir.mkdir(exist_ok=True)

    alignment_rows: list[dict[str, object]] = []
    marker_rows: list[dict[str, object]] = []
    image_rows: list[dict[str, object]] = []

    for pair in discovery.pairs:
        original = read_image(pair.original_path)
        marked = read_image(pair.marked_path)
        alignment = estimate_alignment(original, marked)
        alignment_row = {
            "image_id": pair.image_id,
            "source_image": pair.original_path.name,
            "marked_image": pair.marked_path.name,
            **alignment,
        }
        alignment_rows.append(alignment_row)

        markers = detect_marker_instances(marked, pair.image_id, pair.marked_path.name) if marked is not None else []
        marker_rows.extend(marker_to_row(marker) for marker in markers)
        score, status = quality_grade(len(markers))

        areas = [float(marker.component_area) for marker in markers]
        equivalent_radii = [float(marker.equivalent_circle_radius) for marker in markers]
        nearest_distances = [
            float(marker.nearest_neighbor_distance)
            for marker in markers
            if marker.nearest_neighbor_distance is not None
        ]
        image_rows.append(
            {
                "image_id": pair.image_id,
                "source_image": pair.original_path.name,
                "marked_image": pair.marked_path.name,
                "dirty_spot_count": len(markers),
                "cleanliness_score": score,
                "pass_fail_status": status,
                "alignment_status": alignment_row["alignment_status"],
                "alignment_confidence": alignment_row["alignment_confidence"],
                "estimated_x_offset": alignment_row["estimated_x_offset"],
                "estimated_y_offset": alignment_row["estimated_y_offset"],
                "min_marker_area": min_or_blank(areas),
                "median_marker_area": median_or_blank(areas),
                "max_marker_area": max_or_blank(areas),
                "min_equivalent_radius": min_or_blank(equivalent_radii),
                "median_equivalent_radius": median_or_blank(equivalent_radii),
                "max_equivalent_radius": max_or_blank(equivalent_radii),
                "min_nearest_neighbor_distance": min_or_blank(nearest_distances),
                "median_nearest_neighbor_distance": median_or_blank(nearest_distances),
                "notes": "blue_marker_preliminary_label",
            }
        )

        if marked is not None:
            make_preview(
                marked,
                markers,
                preview_dir / f"{pair.image_id}_marker_preview.jpg",
                pair.image_id,
                len(markers),
            )

    write_csv(output_dir / "alignment_report.csv", ALIGNMENT_COLUMNS, alignment_rows)
    write_csv(output_dir / "marker_instances.csv", MARKER_COLUMNS, marker_rows)
    write_csv(output_dir / "image_summary.csv", IMAGE_SUMMARY_COLUMNS, image_rows)

    marker_areas = [float(row["component_area"]) for row in marker_rows]
    equivalent_radii = [float(row["equivalent_circle_radius"]) for row in marker_rows]
    enclosing_radii = [float(row["enclosing_circle_radius"]) for row in marker_rows]
    nearest_distances = [
        float(row["nearest_neighbor_distance"])
        for row in marker_rows
        if row["nearest_neighbor_distance"] != ""
    ]
    spot_counts = [float(row["dirty_spot_count"]) for row in image_rows]
    alignment_status_counts = {
        status: sum(1 for row in alignment_rows if row["alignment_status"] == status)
        for status in ("PASS", "WARNING", "FAIL")
    }

    summary: dict[str, object] = {
        "pair_count": len(discovery.pairs),
        "missing_originals": discovery.missing_originals,
        "missing_marked": discovery.missing_marked,
        "duplicates": discovery.duplicates,
        "unsupported_extensions": discovery.unsupported_extensions,
        "marker_detection_constants": {
            "source": "crop_clean_patches.py",
            "hsv_lower": [90, 50, 50],
            "hsv_upper": [140, 255, 255],
            "morphology": "MORPH_CLOSE with 5x5 elliptical kernel via detect_blue_mask",
            "min_blue_component_area": MIN_BLUE_COMPONENT_AREA,
        },
        "alignment_status_counts": alignment_status_counts,
        "alignment_confidence_mean": round(
            mean(float(row["alignment_confidence"]) for row in alignment_rows if row["alignment_confidence"] != ""),
            6,
        )
        if alignment_rows
        else None,
        "marker_area": distribution(marker_areas),
        "equivalent_radius": distribution(equivalent_radii),
        "enclosing_radius": distribution(enclosing_radii),
        "nearest_neighbor_distance": distribution(nearest_distances),
        "spot_count_per_image": distribution(spot_counts),
        "pass_fail_counts": {
            status: sum(1 for row in image_rows if row["pass_fail_status"] == status)
            for status in ("PASS", "FAIL", "REVIEW")
        },
        "outlier_images": summarize_outliers(image_rows, marker_rows),
    }

    (output_dir / "distribution_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "marker_policy_proposal.md").write_text(
        policy_proposal_text(summary),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    args = parse_args()
    raw_dir = resolve_project_path(args.raw_dir)
    output_dir = resolve_output_dir(args.output_dir)
    summary = analyze(raw_dir, output_dir)
    print(f"Blue marker analysis complete: {output_dir}")
    print(f"Pairs analyzed: {summary['pair_count']}")
    print(f"Alignment status counts: {summary['alignment_status_counts']}")
    print(f"Pass/fail counts: {summary['pass_fail_counts']}")


if __name__ == "__main__":
    main()
