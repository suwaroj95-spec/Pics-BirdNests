from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


DEFAULT_METHODS = ("isolation_forest", "lof", "pca")
METHOD_LABELS = {
    "isolation_forest": "Isolation Forest",
    "lof": "Local Outlier Factor",
    "pca": "PCA Reconstruction Error",
}
IDENTIFIER_COLUMNS = {
    "rank",
    "system",
    "label",
    "output_file",
    "paired_mask_file",
    "source_id",
    "source_image",
    "x",
    "y",
    "generation_method",
}
EULER_GAMMA = 0.5772156649015329


@dataclass(frozen=True)
class AnomalyConfig:
    backtest_run: Path | None = None
    backtest_root: Path = Path("BacktestSelection")
    crops_dir: Path = Path("Crops")
    output_dir: Path = Path("AnomalyDetection")
    methods: tuple[str, ...] = DEFAULT_METHODS
    contamination: float = 0.08
    consensus_threshold: float = 0.85
    min_votes: int = 2
    isolation_trees: int = 96
    isolation_subsample: int = 256
    neighbor_k: int = 20
    pca_components: int = 6
    random_seed: int = 42
    top_n: int = 24
    make_previews: bool = True
    copy_anomalies: bool = False


@dataclass
class IsolationNode:
    size: int
    depth: int
    feature_index: int | None = None
    threshold: float | None = None
    left: "IsolationNode | None" = None
    right: "IsolationNode | None" = None


@dataclass
class FeatureMatrix:
    columns: list[str]
    raw: np.ndarray
    scaled: np.ndarray
    medians: np.ndarray
    scales: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run anomaly detection on selected BacktestSelection manifests using "
            "Isolation Forest, LOF, and PCA reconstruction scoring."
        )
    )
    parser.add_argument("--backtest-run", default="", help="BacktestSelection run directory.")
    parser.add_argument("--backtest-root", default="BacktestSelection")
    parser.add_argument("--crops-dir", default="Crops")
    parser.add_argument("--output-dir", default="AnomalyDetection")
    parser.add_argument(
        "--methods",
        default=",".join(DEFAULT_METHODS),
        help="Comma-separated methods: isolation_forest,lof,pca",
    )
    parser.add_argument("--contamination", type=float, default=0.08)
    parser.add_argument("--consensus-threshold", type=float, default=0.85)
    parser.add_argument("--min-votes", type=int, default=2)
    parser.add_argument("--isolation-trees", type=int, default=96)
    parser.add_argument("--isolation-subsample", type=int, default=256)
    parser.add_argument("--neighbor-k", type=int, default=20)
    parser.add_argument("--pca-components", type=int, default=6)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--top-n", type=int, default=24)
    parser.add_argument("--no-previews", action="store_true")
    parser.add_argument("--copy-anomalies", action="store_true")
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> AnomalyConfig:
    methods = tuple(
        method.strip()
        for method in args.methods.split(",")
        if method.strip()
    )
    unknown_methods = [method for method in methods if method not in METHOD_LABELS]
    if unknown_methods:
        raise ValueError(f"Unknown anomaly methods: {', '.join(unknown_methods)}")

    return AnomalyConfig(
        backtest_run=Path(args.backtest_run) if args.backtest_run else None,
        backtest_root=Path(args.backtest_root),
        crops_dir=Path(args.crops_dir),
        output_dir=Path(args.output_dir),
        methods=methods or DEFAULT_METHODS,
        contamination=max(0.0, min(args.contamination, 0.5)),
        consensus_threshold=max(0.0, min(args.consensus_threshold, 1.0)),
        min_votes=max(1, args.min_votes),
        isolation_trees=max(1, args.isolation_trees),
        isolation_subsample=max(2, args.isolation_subsample),
        neighbor_k=max(2, args.neighbor_k),
        pca_components=max(1, args.pca_components),
        random_seed=args.random_seed,
        top_n=max(1, args.top_n),
        make_previews=not args.no_previews,
        copy_anomalies=args.copy_anomalies,
    )


def latest_backtest_run(backtest_root: Path) -> Path:
    if not backtest_root.exists():
        raise FileNotFoundError(f"Backtest root not found: {backtest_root}")

    run_dirs = [
        path
        for path in backtest_root.iterdir()
        if path.is_dir() and (path / "comparison_summary.json").exists()
    ]
    if not run_dirs:
        raise FileNotFoundError(f"No BacktestSelection runs found in: {backtest_root}")
    return max(run_dirs, key=lambda path: (path.stat().st_mtime, path.name))


def resolve_backtest_run(config: AnomalyConfig) -> Path:
    if config.backtest_run is not None:
        run_dir = config.backtest_run
        if not run_dir.exists():
            run_dir = config.backtest_root / config.backtest_run
        if not run_dir.exists():
            raise FileNotFoundError(f"Backtest run not found: {config.backtest_run}")
        return run_dir
    return latest_backtest_run(config.backtest_root)


def manifest_paths_from_run(run_dir: Path) -> list[tuple[str, Path]]:
    comparison_path = run_dir / "comparison_summary.json"
    manifests: list[tuple[str, Path]] = []
    if comparison_path.exists():
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        for system in comparison.get("systems", []):
            system_key = str(system.get("system_key", ""))
            manifest_text = system.get("outputs", {}).get("manifest", "")
            manifest_path = resolve_manifest_path(manifest_text, run_dir)
            if manifest_path is not None:
                manifests.append((system_key, manifest_path))

    if manifests:
        return manifests

    for manifest_path in sorted(run_dir.glob("system_*/selected_manifest.csv")):
        manifests.append((manifest_path.parent.name, manifest_path))
    if not manifests:
        raise FileNotFoundError(f"No selected_manifest.csv files found in: {run_dir}")
    return manifests


def resolve_manifest_path(manifest_text: str, run_dir: Path) -> Path | None:
    if not manifest_text:
        return None

    manifest_path = Path(manifest_text)
    candidates = [manifest_path]
    if not manifest_path.is_absolute():
        candidates.extend(
            [
                run_dir / manifest_path,
                run_dir.parent / manifest_path,
                run_dir.parent.parent / manifest_path,
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def read_manifest(system_key: str, manifest_path: Path, crops_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with manifest_path.open("r", newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            row = dict(row)
            row["system_key"] = system_key or row.get("system", manifest_path.parent.name)
            row["manifest_path"] = str(manifest_path)
            row["image_path"] = str(resolve_image_path(row, manifest_path.parent, crops_dir))
            rows.append(row)
    return rows


def resolve_image_path(row: dict[str, str], system_dir: Path, crops_dir: Path) -> Path:
    output_file = row.get("output_file", "")
    selected_copy = system_dir / Path(output_file)
    if selected_copy.exists():
        return selected_copy

    original_crop = crops_dir / Path(output_file)
    if original_crop.exists():
        return original_crop

    return selected_copy


def safe_float(value: str | int | float | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def numeric_feature_columns(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return []

    columns = [
        column
        for column in rows[0].keys()
        if column not in IDENTIFIER_COLUMNS
        and column not in {"system_key", "manifest_path", "image_path"}
    ]
    numeric_columns: list[str] = []
    for column in columns:
        parsed = [safe_float(row.get(column)) for row in rows]
        valid_count = sum(value is not None for value in parsed)
        if valid_count >= max(3, int(len(rows) * 0.75)):
            numeric_columns.append(column)
    return numeric_columns


def build_feature_matrix(rows: list[dict[str, str]]) -> FeatureMatrix:
    columns = numeric_feature_columns(rows)
    if not columns:
        raise ValueError("No numeric feature columns found for anomaly detection.")

    raw = np.empty((len(rows), len(columns)), dtype=np.float64)
    raw.fill(np.nan)
    for row_index, row in enumerate(rows):
        for col_index, column in enumerate(columns):
            value = safe_float(row.get(column))
            if value is not None:
                raw[row_index, col_index] = value

    medians = np.nanmedian(raw, axis=0)
    medians = np.where(np.isfinite(medians), medians, 0.0)
    filled = np.where(np.isfinite(raw), raw, medians)

    q25 = np.percentile(filled, 25, axis=0)
    q75 = np.percentile(filled, 75, axis=0)
    scales = q75 - q25
    std = np.std(filled, axis=0)
    scales = np.where(scales > 1e-12, scales, std)
    scales = np.where(scales > 1e-12, scales, 1.0)
    scaled = np.clip((filled - medians) / scales, -8.0, 8.0)
    return FeatureMatrix(columns=columns, raw=filled, scaled=scaled, medians=medians, scales=scales)


def percentile_normalize(scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=np.float64)
    if scores.size == 0:
        return scores
    finite = scores[np.isfinite(scores)]
    if finite.size == 0:
        return np.zeros_like(scores)
    lo = float(np.percentile(finite, 5))
    hi = float(np.percentile(finite, 95))
    if hi <= lo:
        return np.full(scores.shape, 0.5, dtype=np.float64)
    return np.clip((scores - lo) / (hi - lo), 0.0, 1.0)


def average_path_length(sample_count: int) -> float:
    if sample_count <= 1:
        return 0.0
    if sample_count == 2:
        return 1.0
    return (
        2.0 * (math.log(sample_count - 1) + EULER_GAMMA)
        - (2.0 * (sample_count - 1) / sample_count)
    )


def build_isolation_tree(
    x_train: np.ndarray,
    rng: np.random.Generator,
    depth: int,
    max_depth: int,
) -> IsolationNode:
    node = IsolationNode(size=len(x_train), depth=depth)
    if depth >= max_depth or len(x_train) <= 1:
        return node

    mins = np.min(x_train, axis=0)
    maxs = np.max(x_train, axis=0)
    candidate_features = np.flatnonzero(maxs > mins)
    if candidate_features.size == 0:
        return node

    for _ in range(12):
        feature_index = int(rng.choice(candidate_features))
        threshold = float(rng.uniform(mins[feature_index], maxs[feature_index]))
        left_mask = x_train[:, feature_index] <= threshold
        left_count = int(left_mask.sum())
        if 0 < left_count < len(x_train):
            node.feature_index = feature_index
            node.threshold = threshold
            node.left = build_isolation_tree(x_train[left_mask], rng, depth + 1, max_depth)
            node.right = build_isolation_tree(x_train[~left_mask], rng, depth + 1, max_depth)
            return node
    return node


def path_length(row: np.ndarray, node: IsolationNode) -> float:
    if (
        node.feature_index is None
        or node.threshold is None
        or node.left is None
        or node.right is None
    ):
        return node.depth + average_path_length(node.size)
    if row[node.feature_index] <= node.threshold:
        return path_length(row, node.left)
    return path_length(row, node.right)


def isolation_forest_scores(
    x: np.ndarray,
    tree_count: int,
    subsample_size: int,
    seed: int,
) -> np.ndarray:
    sample_count = len(x)
    if sample_count < 3:
        return np.zeros(sample_count, dtype=np.float64)

    rng = np.random.default_rng(seed)
    effective_subsample = min(sample_count, max(2, subsample_size))
    max_depth = int(math.ceil(math.log2(effective_subsample)))
    path_sums = np.zeros(sample_count, dtype=np.float64)

    for _ in range(tree_count):
        if effective_subsample < sample_count:
            indices = rng.choice(sample_count, size=effective_subsample, replace=False)
            x_train = x[indices]
        else:
            x_train = x
        tree = build_isolation_tree(x_train, rng, depth=0, max_depth=max_depth)
        path_sums += np.array([path_length(row, tree) for row in x], dtype=np.float64)

    mean_paths = path_sums / tree_count
    normalizer = average_path_length(effective_subsample)
    if normalizer <= 0:
        return np.zeros(sample_count, dtype=np.float64)
    return np.power(2.0, -mean_paths / normalizer)


def lof_scores(x: np.ndarray, neighbor_k: int) -> np.ndarray:
    sample_count = len(x)
    if sample_count < 3:
        return np.zeros(sample_count, dtype=np.float64)

    k = min(max(2, neighbor_k), sample_count - 1)
    squared = np.sum(x * x, axis=1, keepdims=True)
    distances = squared + squared.T - (2.0 * x @ x.T)
    distances = np.sqrt(np.maximum(distances, 0.0))
    np.fill_diagonal(distances, np.inf)

    neighbors = np.argsort(distances, axis=1)[:, :k]
    neighbor_distances = np.take_along_axis(distances, neighbors, axis=1)
    sorted_distances = np.sort(distances, axis=1)
    k_distance = sorted_distances[:, k - 1]
    reachability = np.maximum(k_distance[neighbors], neighbor_distances)
    local_reachability_density = 1.0 / (np.mean(reachability, axis=1) + 1e-12)
    density_ratio = local_reachability_density[neighbors] / (
        local_reachability_density[:, None] + 1e-12
    )
    return np.mean(density_ratio, axis=1)


def pca_reconstruction_scores(x: np.ndarray, component_count: int) -> np.ndarray:
    sample_count, feature_count = x.shape
    if sample_count < 3 or feature_count < 2:
        return np.zeros(sample_count, dtype=np.float64)

    centered = x - np.mean(x, axis=0)
    max_components = max(1, min(sample_count - 1, feature_count - 1))
    components = min(max_components, component_count)
    _, singular_values, vt = np.linalg.svd(centered, full_matrices=False)
    basis = vt[:components]
    projected = centered @ basis.T
    reconstructed = projected @ basis
    residual = centered - reconstructed
    energy_scale = float(np.mean(singular_values[:components] ** 2)) if components else 1.0
    if energy_scale <= 1e-12:
        energy_scale = 1.0
    return np.mean(residual * residual, axis=1) / energy_scale


def top_fraction_flags(scores: np.ndarray, contamination: float) -> np.ndarray:
    flags = np.zeros(len(scores), dtype=bool)
    if len(scores) == 0 or contamination <= 0:
        return flags
    anomaly_count = max(1, int(math.ceil(len(scores) * contamination)))
    indices = np.argsort(scores)[::-1][:anomaly_count]
    flags[indices] = True
    return flags


def rank_descending(scores: np.ndarray) -> np.ndarray:
    order = np.argsort(scores)[::-1]
    ranks = np.empty(len(scores), dtype=np.int64)
    ranks[order] = np.arange(1, len(scores) + 1)
    return ranks


def detect_group_anomalies(
    rows: list[dict[str, str]],
    config: AnomalyConfig,
    group_seed: int,
) -> tuple[list[dict[str, str]], dict]:
    matrix = build_feature_matrix(rows)
    method_norms: list[np.ndarray] = []
    method_flags: list[np.ndarray] = []
    method_summary: dict[str, dict[str, float | int]] = {}

    for method_index, method in enumerate(config.methods):
        seed = group_seed + (method_index * 1009)
        if method == "isolation_forest":
            raw_scores = isolation_forest_scores(
                matrix.scaled,
                tree_count=config.isolation_trees,
                subsample_size=config.isolation_subsample,
                seed=seed,
            )
        elif method == "lof":
            raw_scores = lof_scores(matrix.scaled, neighbor_k=config.neighbor_k)
        elif method == "pca":
            raw_scores = pca_reconstruction_scores(
                matrix.scaled,
                component_count=config.pca_components,
            )
        else:
            continue

        normalized = percentile_normalize(raw_scores)
        flags = top_fraction_flags(normalized, config.contamination)
        ranks = rank_descending(normalized)
        method_norms.append(normalized)
        method_flags.append(flags)
        method_summary[method] = {
            "mean_score": float(np.mean(raw_scores)) if len(raw_scores) else 0.0,
            "max_score": float(np.max(raw_scores)) if len(raw_scores) else 0.0,
            "flagged": int(flags.sum()),
        }

        for row, raw_score, norm_score, rank, flag in zip(
            rows,
            raw_scores,
            normalized,
            ranks,
            flags,
            strict=True,
        ):
            row[f"{method}_score"] = f"{raw_score:.8f}"
            row[f"{method}_norm"] = f"{norm_score:.8f}"
            row[f"{method}_rank"] = str(int(rank))
            row[f"{method}_flag"] = "1" if bool(flag) else "0"

    if not method_norms:
        consensus = np.zeros(len(rows), dtype=np.float64)
        vote_counts = np.zeros(len(rows), dtype=np.int64)
    else:
        consensus = np.mean(np.vstack(method_norms), axis=0)
        vote_counts = np.sum(np.vstack(method_flags), axis=0)

    consensus_ranks = rank_descending(consensus)
    consensus_top_flags = top_fraction_flags(consensus, config.contamination)
    is_anomaly = (
        consensus_top_flags
        | (consensus >= config.consensus_threshold)
        | (vote_counts >= config.min_votes)
    )

    for row, score, rank, votes, flag in zip(
        rows,
        consensus,
        consensus_ranks,
        vote_counts,
        is_anomaly,
        strict=True,
    ):
        row["consensus_score"] = f"{score:.8f}"
        row["consensus_rank"] = str(int(rank))
        row["method_vote_count"] = str(int(votes))
        row["is_anomaly"] = "1" if bool(flag) else "0"
        row["feature_columns"] = ";".join(matrix.columns)

    summary = {
        "count": len(rows),
        "feature_count": len(matrix.columns),
        "feature_columns": matrix.columns,
        "anomaly_count": int(is_anomaly.sum()),
        "contamination_target": config.contamination,
        "consensus_threshold": config.consensus_threshold,
        "min_votes": config.min_votes,
        "methods": method_summary,
    }
    return rows, summary


def collect_fieldnames(rows: list[dict[str, str]]) -> list[str]:
    preferred = [
        "system_key",
        "label",
        "is_anomaly",
        "consensus_rank",
        "consensus_score",
        "method_vote_count",
        "output_file",
        "image_path",
        "rank",
        "score",
        "source_id",
        "source_image",
    ]
    fieldnames: list[str] = []
    for field in preferred:
        if any(field in row for row in rows):
            fieldnames.append(field)
    for row in rows:
        for field in row.keys():
            if field not in fieldnames:
                fieldnames.append(field)
    return fieldnames


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = collect_fieldnames(rows)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_summary_text(path: Path, summary: dict) -> None:
    lines = [
        "Anomaly Detection Summary",
        "",
        f"Created at: {summary['created_at']}",
        f"Backtest run: {summary['backtest_run']}",
        f"Output directory: {summary['output_dir']}",
        f"Total rows: {summary['total_rows']}",
        f"Total anomalies: {summary['total_anomalies']}",
        "",
    ]
    for group in summary["groups"]:
        lines.append(
            f"{group['system_key']} / {group['label']}: "
            f"{group['anomaly_count']} anomalies from {group['count']} rows"
        )
        lines.append(f"  Features: {group['feature_count']}")
        for method, method_summary in group["methods"].items():
            lines.append(
                "  "
                f"{METHOD_LABELS.get(method, method)}: "
                f"flagged={method_summary['flagged']}, "
                f"max={method_summary['max_score']:.6f}"
            )
        if group.get("preview"):
            lines.append(f"  Preview: {group['preview']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def short_text(text: str, limit: int = 34) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def create_contact_sheet(rows: list[dict[str, str]], output_path: Path, top_n: int) -> Path | None:
    rows = sorted(
        rows,
        key=lambda row: safe_float(row.get("consensus_score")) or 0.0,
        reverse=True,
    )[:top_n]
    if not rows:
        return None

    thumb_size = 148
    header_height = 46
    padding = 10
    cols = min(4, len(rows))
    sheet_rows = int(math.ceil(len(rows) / cols))
    width = (thumb_size * cols) + (padding * (cols + 1))
    height = ((thumb_size + header_height) * sheet_rows) + (padding * (sheet_rows + 1))
    sheet = np.full((height, width, 3), 246, dtype=np.uint8)

    for index, row in enumerate(rows):
        grid_y, grid_x = divmod(index, cols)
        x0 = padding + grid_x * (thumb_size + padding)
        y0 = padding + grid_y * (thumb_size + header_height + padding)
        image = cv2.imread(row.get("image_path", ""), cv2.IMREAD_COLOR)
        if image is None:
            tile = np.full((thumb_size, thumb_size, 3), 224, dtype=np.uint8)
            cv2.putText(tile, "missing", (22, 78), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (70, 70, 70), 1)
        else:
            tile = cv2.resize(image, (thumb_size, thumb_size), interpolation=cv2.INTER_AREA)

        sheet[y0 : y0 + thumb_size, x0 : x0 + thumb_size] = tile
        label_y = y0 + thumb_size + 18
        score_text = row.get("consensus_score", "0")
        cv2.putText(
            sheet,
            f"#{row.get('consensus_rank', '?')}  {score_text[:5]}",
            (x0, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (30, 48, 62),
            1,
            cv2.LINE_AA,
        )
        output_name = short_text(Path(row.get("output_file", "")).name, limit=22)
        cv2.putText(
            sheet,
            output_name,
            (x0, label_y + 19),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.36,
            (83, 97, 112),
            1,
            cv2.LINE_AA,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), sheet)
    return output_path


def copy_anomaly_files(rows: Iterable[dict[str, str]], output_dir: Path) -> None:
    for row in rows:
        source = Path(row.get("image_path", ""))
        if not source.exists():
            continue
        destination_dir = output_dir / row.get("system_key", "unknown") / row.get("label", "unknown")
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination_dir / source.name)

        paired_mask = row.get("paired_mask_file", "")
        if paired_mask:
            mask_path = source.parent / Path(paired_mask).name
            if mask_path.exists():
                shutil.copy2(mask_path, destination_dir / mask_path.name)


def run_anomaly_detection(config: AnomalyConfig) -> dict:
    started = time.perf_counter()
    backtest_run = resolve_backtest_run(config)
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    output_run_dir = config.output_dir / run_id
    output_run_dir.mkdir(parents=True, exist_ok=False)

    manifests = manifest_paths_from_run(backtest_run)
    all_rows: list[dict[str, str]] = []
    group_summaries: list[dict] = []

    for manifest_index, (system_key, manifest_path) in enumerate(manifests):
        manifest_rows = read_manifest(system_key, manifest_path, config.crops_dir)
        labels = sorted({row.get("label", "") for row in manifest_rows})
        for label_index, label in enumerate(labels):
            group_rows = [row for row in manifest_rows if row.get("label", "") == label]
            if not group_rows:
                continue
            seed = config.random_seed + (manifest_index * 10000) + (label_index * 137)
            detected_rows, group_summary = detect_group_anomalies(group_rows, config, seed)
            group_summary["system_key"] = system_key
            group_summary["label"] = label
            preview_path: Path | None = None
            if config.make_previews:
                flagged = [row for row in detected_rows if row.get("is_anomaly") == "1"]
                preview_path = create_contact_sheet(
                    flagged,
                    output_run_dir / "previews" / f"{system_key}_{label}_top_anomalies.jpg",
                    config.top_n,
                )
                if preview_path is not None:
                    group_summary["preview"] = str(preview_path)
            all_rows.extend(detected_rows)
            group_summaries.append(group_summary)

    all_rows = sorted(
        all_rows,
        key=lambda row: (
            row.get("system_key", ""),
            row.get("label", ""),
            int(row.get("consensus_rank", "999999") or "999999"),
        ),
    )
    anomaly_rows = [row for row in all_rows if row.get("is_anomaly") == "1"]
    kept_rows = [row for row in all_rows if row.get("is_anomaly") != "1"]
    fieldnames = collect_fieldnames(all_rows)

    write_csv(output_run_dir / "all_anomaly_scores.csv", all_rows, fieldnames)
    write_csv(output_run_dir / "anomaly_review.csv", anomaly_rows, fieldnames)
    write_csv(output_run_dir / "kept_manifest.csv", kept_rows, fieldnames)
    if config.copy_anomalies:
        copy_anomaly_files(anomaly_rows, output_run_dir / "anomaly_files")

    elapsed = time.perf_counter() - started
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "backtest_run": str(backtest_run),
        "output_dir": str(output_run_dir),
        "elapsed_seconds": elapsed,
        "methods": list(config.methods),
        "config": {
            "contamination": config.contamination,
            "consensus_threshold": config.consensus_threshold,
            "min_votes": config.min_votes,
            "isolation_trees": config.isolation_trees,
            "isolation_subsample": config.isolation_subsample,
            "neighbor_k": config.neighbor_k,
            "pca_components": config.pca_components,
            "random_seed": config.random_seed,
            "top_n": config.top_n,
            "make_previews": config.make_previews,
            "copy_anomalies": config.copy_anomalies,
        },
        "outputs": {
            "all_scores_csv": str(output_run_dir / "all_anomaly_scores.csv"),
            "anomaly_review_csv": str(output_run_dir / "anomaly_review.csv"),
            "kept_manifest_csv": str(output_run_dir / "kept_manifest.csv"),
            "summary_json": str(output_run_dir / "summary.json"),
            "summary_text": str(output_run_dir / "summary.txt"),
        },
        "total_rows": len(all_rows),
        "total_anomalies": len(anomaly_rows),
        "groups": group_summaries,
    }
    (output_run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_summary_text(output_run_dir / "summary.txt", summary)
    return summary


def main() -> None:
    config = config_from_args(parse_args())
    summary = run_anomaly_detection(config)
    print("\nAnomaly detection complete.")
    print(f"Backtest run: {summary['backtest_run']}")
    print(f"Output directory: {summary['output_dir']}")
    print(f"Rows scored: {summary['total_rows']}")
    print(f"Anomalies flagged: {summary['total_anomalies']}")
    print(f"Review CSV: {summary['outputs']['anomaly_review_csv']}")


if __name__ == "__main__":
    main()
