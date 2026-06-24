from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


CLEAN_LABEL = "clean_negative"
DIRTY_LABEL = "dirty_positive"
DEFAULT_CLEAN_TARGET = 300
DEFAULT_DIRTY_PAIR_TARGET = 200
PATCH_SIZE = 256
MIN_MATERIAL_RATIO = 0.80
MIN_MATERIAL_CENTER_RATIO = 0.62
MIN_EDGE_DENSITY = 0.055
MAX_FLAT_RATIO = 0.48
MAX_LARGEST_FLAT_BACKGROUND_RATIO = 0.20
MAX_ESTIMATED_BACKGROUND_RATIO = 0.20


@dataclass
class Candidate:
    row: dict[str, str]
    label: str
    image_path: Path
    relative_output: str
    mask_path: Path | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)

    @property
    def source_id(self) -> str:
        return self.row.get("source_id", "")


SYSTEMS = [
    {
        "key": "system_1_opencv_content_contour",
        "name": "System 1 - OpenCV HSV/Contour content filter",
        "description": (
            "Uses color/texture foreground masks and connected components to prefer "
            "crops filled by bird nest material with little background."
        ),
    },
    {
        "key": "system_2_edge_texture_sharpness",
        "name": "System 2 - Edge/texture sharpness filter",
        "description": (
            "Uses Canny edges, Laplacian variance, Tenengrad, and entropy to prefer "
            "clear crops with visible nest fiber detail."
        ),
    },
    {
        "key": "system_3_numpy_frequency_balance",
        "name": "System 3 - NumPy frequency/variance balance",
        "description": (
            "Uses FFT high-frequency energy, local variance, contrast, and exposure "
            "balance to prefer sharp detailed regions without large flat background."
        ),
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Back test three bird-nest crop selection systems."
    )
    parser.add_argument("--crops-dir", default="Crops", help="Directory containing crop folders.")
    parser.add_argument(
        "--output-dir",
        default="BacktestSelection",
        help="Root directory where timestamped run outputs will be written.",
    )
    parser.add_argument("--clean-target", type=int, default=DEFAULT_CLEAN_TARGET)
    parser.add_argument(
        "--dirty-pair-target",
        type=int,
        default=DEFAULT_DIRTY_PAIR_TARGET,
        help="Number of dirty image/mask pairs to select. 200 pairs = 400 dirty files.",
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Only write logs/manifests; do not copy selected images.",
    )
    parser.add_argument(
        "--no-diversity",
        action="store_true",
        help="Disable source_id diversity balancing and choose strictly by score.",
    )
    return parser.parse_args()


def safe_float(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def read_image(path: Path) -> np.ndarray | None:
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


def detect_blue_annotation(image: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower = np.array((90, 50, 50), dtype=np.uint8)
    upper = np.array((140, 255, 255), dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    return cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    )


def normalized_hist_entropy(gray: np.ndarray) -> float:
    hist = cv2.calcHist([gray], [0], None, [64], [0, 256]).ravel()
    total = float(hist.sum())
    if total <= 0:
        return 0.0
    probs = hist / total
    probs = probs[probs > 0]
    entropy = -float(np.sum(probs * np.log2(probs)))
    return entropy / 6.0


def local_std_mean(gray: np.ndarray) -> tuple[float, float]:
    std = local_std_image(gray)
    return float(std.mean()), float(np.mean(std < 4.0))


def local_std_image(gray: np.ndarray, kernel_size: int = 9) -> np.ndarray:
    gray_f = gray.astype(np.float32)
    mean = cv2.blur(gray_f, (kernel_size, kernel_size))
    sq_mean = cv2.blur(gray_f * gray_f, (kernel_size, kernel_size))
    variance = np.maximum(sq_mean - mean * mean, 0.0)
    return np.sqrt(variance)


def foreground_mask(image: np.ndarray, gray: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]

    sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(sobel_x, sobel_y)

    grad_threshold = max(8.0, float(np.percentile(grad, 55)))
    texture = grad > grad_threshold
    visible = (val > 30) & (val < 250)
    color_detail = (sat > 8) & (val > 35)
    mask = ((texture | color_detail) & visible).astype(np.uint8) * 255

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.dilate(mask, kernel, iterations=1)
    return mask


def material_texture_mask(image: np.ndarray, gray: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    local_std = local_std_image(gray)

    sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(sobel_x, sobel_y)

    fibers = (local_std > 5.5) | (grad > 14.0)
    highlights = (gray > np.percentile(gray, 62)) & (local_std > 4.5)
    organic_tone = (sat > 16) & (local_std > 3.5)
    visible = (val > 28) & (val < 252)
    blue_marks = detect_blue_annotation(image) > 0

    mask = ((fibers | highlights | organic_tone) & visible & ~blue_marks).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def largest_flat_background_ratio(image: np.ndarray, gray: np.ndarray) -> float:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    local_std = local_std_image(gray)
    flat_background = (
        (local_std < 4.0)
        & (sat < 32)
        & (val > 24)
        & (val < 246)
    ).astype(np.uint8) * 255
    largest_ratio, _ = connected_component_ratio(flat_background)
    return largest_ratio


def connected_component_ratio(mask: np.ndarray) -> tuple[float, int]:
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        return 0.0, 0
    areas = stats[1:, cv2.CC_STAT_AREA]
    largest = int(areas.max())
    total = int(mask.size)
    return largest / total, largest


def border_ratio(mask: np.ndarray, border: int = 20) -> float:
    top = mask[:border, :]
    bottom = mask[-border:, :]
    left = mask[:, :border]
    right = mask[:, -border:]
    pixels = np.concatenate([top.ravel(), bottom.ravel(), left.ravel(), right.ravel()])
    return float(np.mean(pixels > 0))


def center_ratio(mask: np.ndarray) -> float:
    h, w = mask.shape[:2]
    y0, y1 = h // 4, h - (h // 4)
    x0, x1 = w // 4, w - (w // 4)
    center = mask[y0:y1, x0:x1]
    return float(np.mean(center > 0))


def high_frequency_energy(gray: np.ndarray) -> float:
    small = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA).astype(np.float32)
    small -= float(small.mean())
    spectrum = np.fft.fftshift(np.fft.fft2(small))
    power = np.abs(spectrum) ** 2
    h, w = power.shape
    yy, xx = np.ogrid[:h, :w]
    cy, cx = h // 2, w // 2
    radius = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    high = power[radius > 18].sum()
    total = power.sum()
    if total <= 0:
        return 0.0
    return float(high / total)


def mask_metrics(mask_path: Path | None) -> dict[str, float]:
    defaults = {
        "dirty_mark_ratio": 0.0,
        "dirty_mark_center_score": 0.0,
        "dirty_mark_margin_score": 0.0,
        "dirty_mark_found": 0.0,
    }
    if mask_path is None or not mask_path.exists():
        return defaults

    mask_image = read_image(mask_path)
    if mask_image is None:
        return defaults

    blue = detect_blue_annotation(mask_image)
    coords = np.column_stack(np.where(blue > 0))
    if coords.size == 0:
        return defaults

    h, w = blue.shape[:2]
    y_min, x_min = coords.min(axis=0)
    y_max, x_max = coords.max(axis=0)
    cy, cx = coords.mean(axis=0)
    distance = math.sqrt((cx - (w / 2.0)) ** 2 + (cy - (h / 2.0)) ** 2)
    max_distance = math.sqrt((w / 2.0) ** 2 + (h / 2.0) ** 2)
    margin = min(x_min, y_min, w - 1 - x_max, h - 1 - y_max)

    return {
        "dirty_mark_ratio": float(np.mean(blue > 0)),
        "dirty_mark_center_score": 1.0 - min(distance / max_distance, 1.0),
        "dirty_mark_margin_score": max(0.0, min(float(margin) / 64.0, 1.0)),
        "dirty_mark_found": 1.0,
    }


def analyze_image(path: Path, mask_path: Path | None) -> dict[str, float]:
    image = read_image(path)
    if image is None:
        return {"read_ok": 0.0}

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    fg_mask = foreground_mask(image, gray)
    material_mask = material_texture_mask(image, gray)
    largest_component, largest_area = connected_component_ratio(fg_mask)
    material_largest_component, material_largest_area = connected_component_ratio(material_mask)
    edges = cv2.Canny(gray, 60, 150)
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    tenengrad = float(np.mean(sobel_x * sobel_x + sobel_y * sobel_y))
    local_std, flat_ratio = local_std_mean(gray)
    contrast = float(gray.std())
    mean_brightness = float(gray.mean())
    exposure_penalty = float(np.mean((gray < 12) | (gray > 245)))
    exposure_score = 1.0 - min(exposure_penalty * 2.5, 1.0)
    blue_ratio = float(np.mean(detect_blue_annotation(image) > 0))

    metrics = {
        "read_ok": 1.0,
        "foreground_ratio": float(np.mean(fg_mask > 0)),
        "largest_component_ratio": largest_component,
        "largest_component_area": float(largest_area),
        "border_foreground_ratio": border_ratio(fg_mask),
        "center_foreground_ratio": center_ratio(fg_mask),
        "material_ratio": float(np.mean(material_mask > 0)),
        "material_largest_component_ratio": material_largest_component,
        "material_largest_component_area": float(material_largest_area),
        "material_border_ratio": border_ratio(material_mask),
        "material_center_ratio": center_ratio(material_mask),
        "largest_flat_background_ratio": largest_flat_background_ratio(image, gray),
        "edge_density": float(np.mean(edges > 0)),
        "laplacian_variance": lap_var,
        "tenengrad": tenengrad,
        "entropy": normalized_hist_entropy(gray),
        "local_std_mean": local_std,
        "flat_ratio": flat_ratio,
        "contrast": contrast,
        "mean_brightness": mean_brightness,
        "exposure_score": exposure_score,
        "blue_marker_ratio": blue_ratio,
        "high_frequency_energy": high_frequency_energy(gray),
    }
    metrics["estimated_background_ratio"] = max(
        1.0 - metrics["material_ratio"],
        metrics["largest_flat_background_ratio"],
    )
    metrics["quality_gate_pass"] = float(
        metrics["material_ratio"] >= MIN_MATERIAL_RATIO
        and metrics["material_center_ratio"] >= MIN_MATERIAL_CENTER_RATIO
        and metrics["edge_density"] >= MIN_EDGE_DENSITY
        and metrics["flat_ratio"] <= MAX_FLAT_RATIO
        and metrics["largest_flat_background_ratio"] <= MAX_LARGEST_FLAT_BACKGROUND_RATIO
        and metrics["estimated_background_ratio"] <= MAX_ESTIMATED_BACKGROUND_RATIO
    )
    metrics.update(mask_metrics(mask_path))
    return metrics


def load_candidates(crops_dir: Path) -> tuple[list[Candidate], list[str]]:
    metadata_path = crops_dir / "metadata.csv"
    warnings: list[str] = []
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.csv not found: {metadata_path}")

    candidates: list[Candidate] = []
    with metadata_path.open("r", newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            label = row.get("label", "")
            if label not in {CLEAN_LABEL, DIRTY_LABEL}:
                continue
            relative_output = row.get("output_file", "")
            image_path = crops_dir / relative_output
            if not image_path.exists():
                warnings.append(f"Missing image: {relative_output}")
                continue

            mask_path = None
            if label == DIRTY_LABEL:
                mask_path = image_path.with_name(f"{image_path.stem}_mask{image_path.suffix}")
                if not mask_path.exists():
                    warnings.append(f"Missing dirty mask: {mask_path.relative_to(crops_dir)}")

            candidates.append(
                Candidate(
                    row=row,
                    label=label,
                    image_path=image_path,
                    relative_output=relative_output,
                    mask_path=mask_path,
                )
            )

    return candidates, warnings


def percentile_normalize(values: list[float]) -> list[float]:
    arr = np.array(values, dtype=np.float64)
    if arr.size == 0:
        return []
    lo = float(np.percentile(arr, 5))
    hi = float(np.percentile(arr, 95))
    if hi <= lo:
        return [0.5 for _ in values]
    normalized = np.clip((arr - lo) / (hi - lo), 0.0, 1.0)
    return [float(v) for v in normalized]


def add_normalized_scores(candidates: list[Candidate]) -> None:
    fields = [
        "foreground_ratio",
        "largest_component_ratio",
        "border_foreground_ratio",
        "center_foreground_ratio",
        "material_ratio",
        "material_largest_component_ratio",
        "material_border_ratio",
        "material_center_ratio",
        "largest_flat_background_ratio",
        "estimated_background_ratio",
        "edge_density",
        "laplacian_variance",
        "tenengrad",
        "entropy",
        "local_std_mean",
        "flat_ratio",
        "contrast",
        "exposure_score",
        "high_frequency_energy",
        "dirty_mark_ratio",
        "dirty_mark_center_score",
        "dirty_mark_margin_score",
    ]

    for label in (CLEAN_LABEL, DIRTY_LABEL):
        label_candidates = [c for c in candidates if c.label == label and c.metrics.get("read_ok") == 1.0]
        for field_name in fields:
            values = [c.metrics.get(field_name, 0.0) for c in label_candidates]
            normalized = percentile_normalize(values)
            for candidate, norm_value in zip(label_candidates, normalized):
                candidate.metrics[f"norm_{field_name}"] = norm_value


def dirty_mask_bonus(candidate: Candidate) -> float:
    if candidate.label != DIRTY_LABEL:
        return 0.0
    found = candidate.metrics.get("dirty_mark_found", 0.0)
    center = candidate.metrics.get("dirty_mark_center_score", 0.0)
    margin = candidate.metrics.get("dirty_mark_margin_score", 0.0)
    area = candidate.metrics.get("norm_dirty_mark_ratio", 0.0)
    return 0.12 * found + 0.05 * center + 0.03 * margin + 0.03 * area


def compute_system_scores(candidates: list[Candidate]) -> None:
    for candidate in candidates:
        if candidate.metrics.get("read_ok") != 1.0:
            for system in SYSTEMS:
                candidate.scores[system["key"]] = -1.0
            continue

        blue_penalty = min(candidate.metrics.get("blue_marker_ratio", 0.0) * 8.0, 0.25)
        gate_penalty = 0.0 if candidate.metrics.get("quality_gate_pass", 0.0) >= 1.0 else 1.0
        flat_good = 1.0 - candidate.metrics.get("norm_flat_ratio", 0.0)
        material = candidate.metrics.get("norm_material_ratio", 0.0)
        largest = candidate.metrics.get("norm_material_largest_component_ratio", 0.0)
        center = candidate.metrics.get("norm_material_center_ratio", 0.0)
        border = candidate.metrics.get("norm_material_border_ratio", 0.0)
        exposure = candidate.metrics.get("norm_exposure_score", 0.0)
        background_penalty = (
            0.35 * candidate.metrics.get("flat_ratio", 0.0)
            + 0.35 * candidate.metrics.get("largest_flat_background_ratio", 0.0)
            + 0.60 * candidate.metrics.get("estimated_background_ratio", 0.0)
            + gate_penalty
        )
        mask_bonus = dirty_mask_bonus(candidate)

        candidate.scores["system_1_opencv_content_contour"] = (
            0.36 * material
            + 0.24 * largest
            + 0.16 * center
            + 0.12 * border
            + 0.08 * exposure
            + 0.04 * flat_good
            + mask_bonus
            - blue_penalty
            - background_penalty
        )

        candidate.scores["system_2_edge_texture_sharpness"] = (
            0.30 * candidate.metrics.get("norm_laplacian_variance", 0.0)
            + 0.22 * candidate.metrics.get("norm_tenengrad", 0.0)
            + 0.18 * candidate.metrics.get("norm_edge_density", 0.0)
            + 0.12 * candidate.metrics.get("norm_entropy", 0.0)
            + 0.10 * flat_good
            + 0.08 * exposure
            + mask_bonus
            - blue_penalty
            - background_penalty
        )

        candidate.scores["system_3_numpy_frequency_balance"] = (
            0.30 * candidate.metrics.get("norm_high_frequency_energy", 0.0)
            + 0.20 * candidate.metrics.get("norm_local_std_mean", 0.0)
            + 0.16 * candidate.metrics.get("norm_contrast", 0.0)
            + 0.14 * material
            + 0.10 * exposure
            + 0.10 * flat_good
            + mask_bonus
            - blue_penalty
            - background_penalty
        )


def sorted_candidates(candidates: list[Candidate], system_key: str, label: str) -> list[Candidate]:
    return sorted(
        [
            c
            for c in candidates
            if c.label == label
            and c.metrics.get("quality_gate_pass", 0.0) >= 1.0
            and c.scores.get(system_key, -1.0) >= 0.0
        ],
        key=lambda c: (
            c.scores.get(system_key, -1.0),
            c.metrics.get("material_ratio", 0.0),
            c.metrics.get("laplacian_variance", 0.0),
            -safe_float(c.row.get("source_id")),
            c.relative_output,
        ),
        reverse=True,
    )


def select_with_source_diversity(
    candidates: list[Candidate],
    system_key: str,
    label: str,
    target: int,
    use_diversity: bool,
) -> list[Candidate]:
    ranked = sorted_candidates(candidates, system_key, label)
    if not use_diversity or target <= 0:
        return ranked[:target]

    source_ids = sorted({c.source_id for c in ranked})
    if not source_ids:
        return []

    selected: list[Candidate] = []
    selected_ids: set[str] = set()
    per_source_cap = max(1, math.ceil(target / len(source_ids)))

    while len(selected) < target and len(selected) < len(ranked):
        added_this_round = False
        source_counts: dict[str, int] = {}
        for candidate in selected:
            source_counts[candidate.source_id] = source_counts.get(candidate.source_id, 0) + 1

        for candidate in ranked:
            if candidate.relative_output in selected_ids:
                continue
            if source_counts.get(candidate.source_id, 0) >= per_source_cap:
                continue
            selected.append(candidate)
            selected_ids.add(candidate.relative_output)
            source_counts[candidate.source_id] = source_counts.get(candidate.source_id, 0) + 1
            added_this_round = True
            if len(selected) >= target:
                break

        if not added_this_round:
            per_source_cap += 1

    return selected[:target]


def ensure_label_dirs(system_dir: Path) -> tuple[Path, Path]:
    clean_dir = system_dir / CLEAN_LABEL
    dirty_dir = system_dir / DIRTY_LABEL
    clean_dir.mkdir(parents=True, exist_ok=True)
    dirty_dir.mkdir(parents=True, exist_ok=True)
    return clean_dir, dirty_dir


def copy_selected(selected: list[Candidate], system_dir: Path) -> None:
    clean_dir, dirty_dir = ensure_label_dirs(system_dir)
    for candidate in selected:
        if candidate.label == CLEAN_LABEL:
            destination = clean_dir / candidate.image_path.name
            shutil.copy2(candidate.image_path, destination)
        else:
            destination = dirty_dir / candidate.image_path.name
            shutil.copy2(candidate.image_path, destination)
            if candidate.mask_path is not None and candidate.mask_path.exists():
                shutil.copy2(candidate.mask_path, dirty_dir / candidate.mask_path.name)


def numeric_summary(selected: list[Candidate], system_key: str) -> dict[str, float]:
    fields = [
        "foreground_ratio",
        "material_ratio",
        "material_center_ratio",
        "largest_flat_background_ratio",
        "estimated_background_ratio",
        "border_foreground_ratio",
        "center_foreground_ratio",
        "laplacian_variance",
        "edge_density",
        "entropy",
        "high_frequency_energy",
        "flat_ratio",
        "exposure_score",
    ]
    summary: dict[str, float] = {
        "count": float(len(selected)),
        "mean_score": mean([c.scores.get(system_key, 0.0) for c in selected]),
    }
    for field_name in fields:
        summary[f"mean_{field_name}"] = mean([c.metrics.get(field_name, 0.0) for c in selected])
    return summary


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def write_manifest(path: Path, selected: list[Candidate], system_key: str) -> None:
    metric_fields = sorted({key for c in selected for key in c.metrics.keys() if not key.startswith("norm_")})
    fieldnames = [
        "rank",
        "system",
        "score",
        "label",
        "output_file",
        "paired_mask_file",
        "source_id",
        "source_image",
        "x",
        "y",
        "generation_method",
    ] + metric_fields

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for rank, candidate in enumerate(selected, start=1):
            row = {
                "rank": rank,
                "system": system_key,
                "score": f"{candidate.scores.get(system_key, 0.0):.8f}",
                "label": candidate.label,
                "output_file": candidate.relative_output,
                "paired_mask_file": (
                    str(candidate.mask_path.relative_to(candidate.image_path.parents[1]))
                    if candidate.mask_path is not None and candidate.mask_path.exists()
                    else ""
                ),
                "source_id": candidate.source_id,
                "source_image": candidate.row.get("source_image", ""),
                "x": candidate.row.get("x", ""),
                "y": candidate.row.get("y", ""),
                "generation_method": candidate.row.get("generation_method", ""),
            }
            for field_name in metric_fields:
                value = candidate.metrics.get(field_name, "")
                row[field_name] = f"{value:.8f}" if isinstance(value, float) else value
            writer.writerow(row)


def write_all_scores(path: Path, candidates: list[Candidate]) -> None:
    metric_fields = [
        "foreground_ratio",
        "largest_component_ratio",
        "border_foreground_ratio",
        "center_foreground_ratio",
        "edge_density",
        "laplacian_variance",
        "tenengrad",
        "entropy",
        "local_std_mean",
        "flat_ratio",
        "contrast",
        "exposure_score",
        "high_frequency_energy",
        "quality_gate_pass",
        "dirty_mark_found",
        "dirty_mark_ratio",
        "dirty_mark_center_score",
        "dirty_mark_margin_score",
    ]
    fieldnames = [
        "label",
        "output_file",
        "source_id",
        "system_1_score",
        "system_2_score",
        "system_3_score",
    ] + metric_fields
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for candidate in candidates:
            row = {
                "label": candidate.label,
                "output_file": candidate.relative_output,
                "source_id": candidate.source_id,
                "system_1_score": f"{candidate.scores.get(SYSTEMS[0]['key'], 0.0):.8f}",
                "system_2_score": f"{candidate.scores.get(SYSTEMS[1]['key'], 0.0):.8f}",
                "system_3_score": f"{candidate.scores.get(SYSTEMS[2]['key'], 0.0):.8f}",
            }
            for field_name in metric_fields:
                row[field_name] = f"{candidate.metrics.get(field_name, 0.0):.8f}"
            writer.writerow(row)


def source_distribution(selected: list[Candidate]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for candidate in selected:
        distribution[candidate.source_id] = distribution.get(candidate.source_id, 0) + 1
    return dict(sorted(distribution.items(), key=lambda item: safe_float(item[0])))


def write_summary_text(path: Path, summary: dict) -> None:
    lines = [
        summary["system_name"],
        "",
        f"Elapsed seconds: {summary['elapsed_seconds']:.3f}",
        f"Selected clean images: {summary['selected_clean']} / {summary['target_clean']}",
        (
            "Selected dirty pairs: "
            f"{summary['selected_dirty_pairs']} / {summary['target_dirty_pairs']} "
            f"({summary['selected_dirty_files']} files including masks)"
        ),
        "",
        "Clean selected averages:",
    ]
    for key, value in summary["clean_summary"].items():
        lines.append(f"  {key}: {value:.6f}")
    lines.append("")
    lines.append("Dirty selected averages:")
    for key, value in summary["dirty_summary"].items():
        lines.append(f"  {key}: {value:.6f}")
    lines.append("")
    lines.append("Clean source distribution:")
    lines.append(json.dumps(summary["clean_source_distribution"], ensure_ascii=False))
    lines.append("")
    lines.append("Dirty source distribution:")
    lines.append(json.dumps(summary["dirty_source_distribution"], ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_system(
    system: dict[str, str],
    candidates: list[Candidate],
    run_dir: Path,
    clean_target: int,
    dirty_pair_target: int,
    copy_files: bool,
    use_diversity: bool,
) -> dict:
    started = time.perf_counter()
    system_key = system["key"]
    system_dir = run_dir / system_key
    system_dir.mkdir(parents=True, exist_ok=True)

    selected_clean = select_with_source_diversity(
        candidates, system_key, CLEAN_LABEL, clean_target, use_diversity
    )
    selected_dirty = select_with_source_diversity(
        candidates, system_key, DIRTY_LABEL, dirty_pair_target, use_diversity
    )
    selected = selected_clean + selected_dirty

    if copy_files:
        copy_selected(selected, system_dir)

    write_manifest(system_dir / "selected_manifest.csv", selected, system_key)
    elapsed = time.perf_counter() - started

    summary = {
        "system_key": system_key,
        "system_name": system["name"],
        "description": system["description"],
        "elapsed_seconds": elapsed,
        "target_clean": clean_target,
        "target_dirty_pairs": dirty_pair_target,
        "selected_clean": len(selected_clean),
        "selected_dirty_pairs": len(selected_dirty),
        "selected_dirty_files": len(selected_dirty) * 2,
        "clean_summary": numeric_summary(selected_clean, system_key),
        "dirty_summary": numeric_summary(selected_dirty, system_key),
        "clean_source_distribution": source_distribution(selected_clean),
        "dirty_source_distribution": source_distribution(selected_dirty),
        "outputs": {
            "system_dir": str(system_dir),
            "manifest": str(system_dir / "selected_manifest.csv"),
            "summary_text": str(system_dir / "summary.txt"),
            "analysis_log": str(system_dir / "analysis_log.json"),
        },
    }

    (system_dir / "analysis_log.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_summary_text(system_dir / "summary.txt", summary)
    return summary


def compare_systems(run_dir: Path, summaries: list[dict], candidates: list[Candidate]) -> None:
    comparison_csv = run_dir / "comparison_summary.csv"
    fieldnames = [
        "system_key",
        "elapsed_seconds",
        "selected_clean",
        "selected_dirty_pairs",
        "selected_dirty_files",
        "clean_mean_score",
        "dirty_mean_score",
        "clean_mean_foreground_ratio",
        "dirty_mean_foreground_ratio",
        "clean_mean_laplacian_variance",
        "dirty_mean_laplacian_variance",
        "clean_mean_flat_ratio",
        "dirty_mean_flat_ratio",
    ]
    with comparison_csv.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for summary in summaries:
            writer.writerow(
                {
                    "system_key": summary["system_key"],
                    "elapsed_seconds": f"{summary['elapsed_seconds']:.6f}",
                    "selected_clean": summary["selected_clean"],
                    "selected_dirty_pairs": summary["selected_dirty_pairs"],
                    "selected_dirty_files": summary["selected_dirty_files"],
                    "clean_mean_score": f"{summary['clean_summary']['mean_score']:.8f}",
                    "dirty_mean_score": f"{summary['dirty_summary']['mean_score']:.8f}",
                    "clean_mean_foreground_ratio": (
                        f"{summary['clean_summary']['mean_foreground_ratio']:.8f}"
                    ),
                    "dirty_mean_foreground_ratio": (
                        f"{summary['dirty_summary']['mean_foreground_ratio']:.8f}"
                    ),
                    "clean_mean_laplacian_variance": (
                        f"{summary['clean_summary']['mean_laplacian_variance']:.8f}"
                    ),
                    "dirty_mean_laplacian_variance": (
                        f"{summary['dirty_summary']['mean_laplacian_variance']:.8f}"
                    ),
                    "clean_mean_flat_ratio": f"{summary['clean_summary']['mean_flat_ratio']:.8f}",
                    "dirty_mean_flat_ratio": f"{summary['dirty_summary']['mean_flat_ratio']:.8f}",
                }
            )

    comparison = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "systems": summaries,
        "all_scores_csv": str(run_dir / "all_candidate_scores.csv"),
        "comparison_csv": str(comparison_csv),
        "candidate_counts": {
            CLEAN_LABEL: sum(1 for c in candidates if c.label == CLEAN_LABEL),
            DIRTY_LABEL: sum(1 for c in candidates if c.label == DIRTY_LABEL),
        },
    }
    (run_dir / "comparison_summary.json").write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    total_started = time.perf_counter()
    crops_dir = Path(args.crops_dir)
    output_root = Path(args.output_dir)
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    load_started = time.perf_counter()
    candidates, warnings = load_candidates(crops_dir)
    load_seconds = time.perf_counter() - load_started

    analyze_started = time.perf_counter()
    for index, candidate in enumerate(candidates, start=1):
        candidate.metrics = analyze_image(candidate.image_path, candidate.mask_path)
        if index % 500 == 0:
            print(f"Analyzed {index}/{len(candidates)} candidates...")
    add_normalized_scores(candidates)
    compute_system_scores(candidates)
    analyze_seconds = time.perf_counter() - analyze_started

    write_all_scores(run_dir / "all_candidate_scores.csv", candidates)

    summaries = []
    for system in SYSTEMS:
        print(f"Running {system['name']}...")
        summaries.append(
            run_system(
                system=system,
                candidates=candidates,
                run_dir=run_dir,
                clean_target=args.clean_target,
                dirty_pair_target=args.dirty_pair_target,
                copy_files=not args.no_copy,
                use_diversity=not args.no_diversity,
            )
        )

    compare_systems(run_dir, summaries, candidates)
    total_seconds = time.perf_counter() - total_started

    run_log = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "crops_dir": str(crops_dir),
        "run_dir": str(run_dir),
        "targets": {
            CLEAN_LABEL: args.clean_target,
            "dirty_pairs": args.dirty_pair_target,
            "dirty_files_including_masks": args.dirty_pair_target * 2,
        },
        "candidate_counts": {
            CLEAN_LABEL: sum(1 for c in candidates if c.label == CLEAN_LABEL),
            DIRTY_LABEL: sum(1 for c in candidates if c.label == DIRTY_LABEL),
        },
        "timing_seconds": {
            "load_metadata": load_seconds,
            "analyze_candidates": analyze_seconds,
            "total": total_seconds,
        },
        "warnings": warnings[:200],
        "warning_count": len(warnings),
        "systems": [summary["system_key"] for summary in summaries],
    }
    (run_dir / "run_log.json").write_text(
        json.dumps(run_log, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nBack test complete.")
    print(f"Run directory: {run_dir}")
    print(f"Analyzed candidates: {len(candidates)}")
    print(f"Load seconds: {load_seconds:.3f}")
    print(f"Analyze seconds: {analyze_seconds:.3f}")
    print(f"Total seconds: {total_seconds:.3f}")
    print(f"Comparison: {run_dir / 'comparison_summary.csv'}")


if __name__ == "__main__":
    main()
