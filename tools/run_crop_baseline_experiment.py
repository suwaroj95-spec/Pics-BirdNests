from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pickle
import platform
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

try:
    import sklearn
    from sklearn.dummy import DummyClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        accuracy_score,
        average_precision_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
except ImportError as exc:  # pragma: no cover - exercised only on missing dependency hosts.
    raise SystemExit("BLOCKED_MISSING_DEPENDENCY: scikit-learn is required and was not installed") from exc


POSITIVE_CLASS = "dirty_positive"
NEGATIVE_CLASS = "clean_negative"
VALID_LABELS = {POSITIVE_CLASS, NEGATIVE_CLASS}
VALID_SPLITS = {"train", "validation", "test"}
RESIZE_WIDTH = 128
RESIZE_HEIGHT = 128
THRESHOLD_CANDIDATES = [round(value / 100, 2) for value in range(10, 91, 5)]
FEATURE_VERSION = "handcrafted_crop_pixels_v1"

REQUIRED_LINEAGE_COLUMNS = [
    "output_file",
    "label",
    "resolved_image_id",
    "resolved_source_image",
    "dataset_split",
]


class ExperimentError(RuntimeError):
    pass


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
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


def ensure_output_empty(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ExperimentError(f"Output directory already contains files: {output_dir}")


def require_columns(columns: list[str], required: list[str], source_name: str) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise ExperimentError(f"{source_name} missing required columns: {', '.join(missing)}")


def feature_names() -> list[str]:
    names = [
        "gray_mean",
        "gray_std",
        "gray_min",
        "gray_max",
        "gray_p05",
        "gray_p25",
        "gray_p50",
        "gray_p75",
        "gray_p95",
        "gray_dark_fraction",
        "gray_bright_fraction",
    ]
    names.extend([f"gray_hist_{index:02d}" for index in range(16)])
    names.extend(
        [
            "laplacian_variance",
            "sobel_magnitude_mean",
            "sobel_magnitude_std",
            "edge_pixel_fraction",
            "h_mean",
            "h_std",
            "s_mean",
            "s_std",
            "v_mean",
            "v_std",
        ]
    )
    names.extend([f"saturation_hist_{index:02d}" for index in range(8)])
    names.extend([f"value_hist_{index:02d}" for index in range(8)])
    return names


FEATURE_NAMES = feature_names()


def extract_features(image: np.ndarray) -> np.ndarray:
    resized = cv2.resize(image, (RESIZE_WIDTH, RESIZE_HEIGHT), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray_unit = gray / 255.0
    gray_hist = cv2.calcHist([gray.astype(np.uint8)], [0], None, [16], [0, 256]).flatten().astype(np.float64)
    gray_hist /= gray_hist.sum() if gray_hist.sum() else 1.0

    laplacian = cv2.Laplacian(gray, cv2.CV_32F)
    sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    sobel_mag = cv2.magnitude(sobel_x, sobel_y)

    hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV).astype(np.float32)
    h = hsv[:, :, 0] / 179.0
    s = hsv[:, :, 1] / 255.0
    v = hsv[:, :, 2] / 255.0
    sat_hist = cv2.calcHist([hsv[:, :, 1].astype(np.uint8)], [0], None, [8], [0, 256]).flatten().astype(np.float64)
    val_hist = cv2.calcHist([hsv[:, :, 2].astype(np.uint8)], [0], None, [8], [0, 256]).flatten().astype(np.float64)
    sat_hist /= sat_hist.sum() if sat_hist.sum() else 1.0
    val_hist /= val_hist.sum() if val_hist.sum() else 1.0

    values: list[float] = [
        float(gray_unit.mean()),
        float(gray_unit.std()),
        float(gray_unit.min()),
        float(gray_unit.max()),
        float(np.percentile(gray_unit, 5)),
        float(np.percentile(gray_unit, 25)),
        float(np.percentile(gray_unit, 50)),
        float(np.percentile(gray_unit, 75)),
        float(np.percentile(gray_unit, 95)),
        float(np.mean(gray_unit < 0.20)),
        float(np.mean(gray_unit > 0.80)),
    ]
    values.extend(float(value) for value in gray_hist)
    values.extend(
        [
            float(laplacian.var()),
            float(sobel_mag.mean()),
            float(sobel_mag.std()),
            float(np.mean(sobel_mag > 30.0)),
            float(h.mean()),
            float(h.std()),
            float(s.mean()),
            float(s.std()),
            float(v.mean()),
            float(v.std()),
        ]
    )
    values.extend(float(value) for value in sat_hist)
    values.extend(float(value) for value in val_hist)
    return np.array(values, dtype=np.float64)


def safe_crop_path(crops_dir: Path, crop_path_text: str) -> Path:
    crops_root = crops_dir.resolve()
    candidate = (crops_root / crop_path_text).resolve()
    try:
        candidate.relative_to(crops_root)
    except ValueError as exc:
        raise ExperimentError(f"Crop path is outside Crops directory: {crop_path_text}") from exc
    return candidate


def validate_marker_audit(marker_audit_dir: Path) -> tuple[dict[str, Any], int]:
    summary_path = marker_audit_dir / "marker_leakage_summary.json"
    manifest_path = marker_audit_dir / "crop_marker_leakage_manifest.csv"
    if not summary_path.exists() or not manifest_path.exists():
        raise ExperimentError("Marker leakage audit files are missing")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("decision") != "SAFE_TO_TRAIN":
        raise ExperimentError("Marker leakage decision is not SAFE_TO_TRAIN")
    if int(summary.get("marker_like_count", -1)) != 0:
        raise ExperimentError("Marker-like crop count is not zero")
    _, marker_rows = read_csv(manifest_path)
    low_blue_signal_count = sum(1 for row in marker_rows if row.get("marker_contamination_status") == "low_blue_signal")
    return summary, low_blue_signal_count


def load_and_validate_dataset(crops_dir: Path, lineage_manifest: Path, marker_audit_dir: Path) -> dict[str, Any]:
    marker_summary, low_blue_signal_count = validate_marker_audit(marker_audit_dir)
    columns, rows = read_csv(lineage_manifest)
    require_columns(columns, REQUIRED_LINEAGE_COLUMNS, lineage_manifest.name)

    source_to_splits: dict[str, set[str]] = defaultdict(set)
    records: list[dict[str, Any]] = []
    feature_rows: list[np.ndarray] = []
    labels: list[int] = []

    for index, row in enumerate(rows, start=2):
        crop_path = safe_crop_path(crops_dir, row["output_file"])
        if not crop_path.exists():
            raise ExperimentError(f"Missing crop file at row {index}: {row['output_file']}")
        if row["label"] not in VALID_LABELS:
            raise ExperimentError(f"Invalid crop label at row {index}: {row['label']}")
        if row["dataset_split"] not in VALID_SPLITS:
            raise ExperimentError(f"Invalid split at row {index}: {row['dataset_split']}")
        if not row["resolved_image_id"]:
            raise ExperimentError(f"Missing resolved_image_id at row {index}: {row['output_file']}")
        image = cv2.imread(str(crop_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ExperimentError(f"Unreadable crop image at row {index}: {row['output_file']}")

        source_to_splits[row["resolved_image_id"]].add(row["dataset_split"])
        feature_rows.append(extract_features(image))
        labels.append(1 if row["label"] == POSITIVE_CLASS else 0)
        records.append(
            {
                "crop_path": row["output_file"],
                "dataset_split": row["dataset_split"],
                "crop_label": row["label"],
                "y_true": 1 if row["label"] == POSITIVE_CLASS else 0,
            }
        )

    leaking_sources = {source: splits for source, splits in source_to_splits.items() if len(splits) != 1}
    if leaking_sources:
        raise ExperimentError(f"At least one source image maps to multiple splits: {leaking_sources}")

    split_label_counts: dict[str, Counter[str]] = {split: Counter() for split in VALID_SPLITS}
    for record in records:
        split_label_counts[str(record["dataset_split"])][str(record["crop_label"])] += 1
    if not split_label_counts["train"][POSITIVE_CLASS] or not split_label_counts["train"][NEGATIVE_CLASS]:
        raise ExperimentError("Training split must contain both crop labels")

    return {
        "records": records,
        "X": np.vstack(feature_rows).astype(np.float64),
        "y": np.array(labels, dtype=np.int32),
        "marker_summary": marker_summary,
        "low_blue_signal_count": low_blue_signal_count,
        "split_label_counts": split_label_counts,
    }


def split_arrays(dataset: dict[str, Any], split: str) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    indices = [index for index, record in enumerate(dataset["records"]) if record["dataset_split"] == split]
    return dataset["X"][indices], dataset["y"][indices], [dataset["records"][index] for index in indices]


def y_to_label(value: int) -> str:
    return POSITIVE_CLASS if int(value) == 1 else NEGATIVE_CLASS


def probability_for_positive(model: Any, X: np.ndarray) -> np.ndarray:
    probabilities = model.predict_proba(X)
    positive_index = list(model.classes_).index(1)
    return probabilities[:, positive_index]


def f1_from_precision_recall(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else (2 * precision * recall) / (precision + recall)


def select_threshold(y_validation: np.ndarray, probabilities: np.ndarray, candidates: list[float] = THRESHOLD_CANDIDATES) -> tuple[float, str, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    for threshold in candidates:
        predictions = (probabilities >= threshold).astype(np.int32)
        precision = precision_score(y_validation, predictions, pos_label=1, zero_division=0)
        recall = recall_score(y_validation, predictions, pos_label=1, zero_division=0)
        f1 = f1_from_precision_recall(float(precision), float(recall))
        rows.append(
            {
                "threshold": f"{threshold:.2f}",
                "validation_precision_dirty_positive": f"{precision:.8f}",
                "validation_recall_dirty_positive": f"{recall:.8f}",
                "validation_f1_dirty_positive": f"{f1:.8f}",
                "eligible_by_precision_rule": str(precision >= 0.80).lower(),
                "selection_rank": "",
                "selected": "false",
                "selection_reason": "",
                "_threshold": threshold,
                "_precision": float(precision),
                "_recall": float(recall),
                "_f1": float(f1),
            }
        )

    eligible = [row for row in rows if row["_precision"] >= 0.80]
    if eligible:
        selected = sorted(eligible, key=lambda row: (-row["_recall"], abs(row["_threshold"] - 0.50), row["_threshold"]))[0]
        reason = "precision>=0.80; selected highest recall, tie closest to 0.50"
    else:
        selected = sorted(rows, key=lambda row: (-row["_f1"], abs(row["_threshold"] - 0.50), row["_threshold"]))[0]
        reason = "fallback: no threshold met precision>=0.80; selected highest validation F1"
    selected["selection_rank"] = "1"
    selected["selected"] = "true"
    selected["selection_reason"] = reason

    public_rows = []
    for row in rows:
        public_rows.append({key: value for key, value in row.items() if not key.startswith("_")})
    return float(selected["_threshold"]), reason, public_rows


def evaluate_predictions(y_true: np.ndarray, predictions: np.ndarray, probabilities: np.ndarray | None = None) -> dict[str, Any]:
    if len(set(int(value) for value in y_true)) < 2:
        return {"available": False, "unavailable_reason": "split lacks both crop classes"}
    matrix = confusion_matrix(y_true, predictions, labels=[0, 1])
    result: dict[str, Any] = {
        "available": True,
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision_dirty_positive": float(precision_score(y_true, predictions, pos_label=1, zero_division=0)),
        "recall_dirty_positive": float(recall_score(y_true, predictions, pos_label=1, zero_division=0)),
        "f1_dirty_positive": float(f1_score(y_true, predictions, pos_label=1, zero_division=0)),
        "confusion_matrix": matrix.tolist(),
        "false_negative_dirty_count": int(matrix[1, 0]),
        "false_positive_dirty_count": int(matrix[0, 1]),
    }
    if probabilities is not None:
        result["roc_auc"] = float(roc_auc_score(y_true, probabilities))
        result["average_precision"] = float(average_precision_score(y_true, probabilities))
    return result


def json_ready(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    return value


def run_experiment(crops_dir: Path, lineage_manifest: Path, marker_audit_dir: Path, output_dir: Path, seed: int, enforce_empty_output: bool = True) -> dict[str, Any]:
    if enforce_empty_output:
        ensure_output_empty(output_dir)
    dataset = load_and_validate_dataset(crops_dir, lineage_manifest, marker_audit_dir)

    X_train, y_train, train_records = split_arrays(dataset, "train")
    X_val, y_val, val_records = split_arrays(dataset, "validation")
    X_test, y_test, test_records = split_arrays(dataset, "test")

    dummy = DummyClassifier(strategy="most_frequent")
    dummy.fit(X_train, y_train)
    logistic = Pipeline(
        [
            ("standard_scaler", StandardScaler()),
            (
                "logistic_regression",
                LogisticRegression(class_weight="balanced", random_state=seed, max_iter=2000),
            ),
        ]
    )
    logistic.fit(X_train, y_train)

    val_probabilities = probability_for_positive(logistic, X_val)
    selected_threshold, threshold_reason, threshold_rows = select_threshold(y_val, val_probabilities)

    split_payload = {
        "train": (X_train, y_train, train_records),
        "validation": (X_val, y_val, val_records),
        "test": (X_test, y_test, test_records),
    }
    metrics: dict[str, dict[str, Any]] = {"dummy_baseline": {}, "logistic_regression": {}}
    matrices: dict[str, dict[str, Any]] = {"dummy_baseline": {}, "logistic_regression": {}}
    prediction_rows: list[dict[str, Any]] = []

    for split, (X_split, y_split, records) in split_payload.items():
        dummy_predictions = dummy.predict(X_split)
        dummy_probabilities = probability_for_positive(dummy, X_split)
        logistic_probabilities = probability_for_positive(logistic, X_split)
        logistic_predictions = (logistic_probabilities >= selected_threshold).astype(np.int32)

        metrics["dummy_baseline"][split] = evaluate_predictions(y_split, dummy_predictions, dummy_probabilities)
        metrics["logistic_regression"][split] = evaluate_predictions(y_split, logistic_predictions, logistic_probabilities)
        for model_name in ["dummy_baseline", "logistic_regression"]:
            model_metrics = metrics[model_name][split]
            matrices[model_name][split] = {
                "labels": [NEGATIVE_CLASS, POSITIVE_CLASS],
                "available": bool(model_metrics.get("available")),
                "matrix": model_metrics.get("confusion_matrix"),
                "unavailable_reason": model_metrics.get("unavailable_reason", ""),
            }

        for index, record in enumerate(records):
            prediction_rows.append(
                {
                    "crop_path": record["crop_path"],
                    "dataset_split": split,
                    "crop_label": record["crop_label"],
                    "y_true": record["y_true"],
                    "dummy_prediction": y_to_label(int(dummy_predictions[index])),
                    "logistic_probability_dirty_positive": f"{float(logistic_probabilities[index]):.8f}",
                    "logistic_prediction": y_to_label(int(logistic_predictions[index])),
                    "selected_threshold": f"{selected_threshold:.2f}",
                }
            )

    output_dir.mkdir(parents=True, exist_ok=False)

    input_paths = {
        "crops_dir": str(crops_dir),
        "lineage_manifest": str(lineage_manifest),
        "marker_audit_dir": str(marker_audit_dir),
    }
    config = {
        "seed": seed,
        "input_paths": input_paths,
        "positive_class": POSITIVE_CLASS,
        "feature_resize": {"width": RESIZE_WIDTH, "height": RESIZE_HEIGHT},
        "model_definitions": {
            "dummy_baseline": 'DummyClassifier(strategy="most_frequent")',
            "logistic_regression": 'Pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", random_state=seed, max_iter=2000))',
        },
        "threshold_candidates": THRESHOLD_CANDIDATES,
        "threshold_selection_policy": "validation only; precision>=0.80 then max recall, tie closest to 0.50; fallback max F1",
        "test_set_locked_during_selection": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    feature_schema = {
        "feature_names": FEATURE_NAMES,
        "feature_count": len(FEATURE_NAMES),
        "feature_extraction_version": FEATURE_VERSION,
        "resize_width": RESIZE_WIDTH,
        "resize_height": RESIZE_HEIGHT,
    }
    versions = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "opencv": cv2.__version__,
        "scikit_learn": sklearn.__version__,
    }
    split_counts: dict[str, Counter[str]] = dataset["split_label_counts"]
    training_summary = {
        "train_crop_count": len(train_records),
        "validation_crop_count": len(val_records),
        "test_crop_count": len(test_records),
        "train_dirty_positive_count": split_counts["train"][POSITIVE_CLASS],
        "train_clean_negative_count": split_counts["train"][NEGATIVE_CLASS],
        "validation_dirty_positive_count": split_counts["validation"][POSITIVE_CLASS],
        "validation_clean_negative_count": split_counts["validation"][NEGATIVE_CLASS],
        "test_dirty_positive_count": split_counts["test"][POSITIVE_CLASS],
        "test_clean_negative_count": split_counts["test"][NEGATIVE_CLASS],
        "marker_leakage_decision": dataset["marker_summary"]["decision"],
        "marker_like_count": dataset["marker_summary"]["marker_like_count"],
        "low_blue_signal_count": dataset["low_blue_signal_count"],
        "selected_threshold": selected_threshold,
        "threshold_selection_result": threshold_reason,
    }

    coef = logistic.named_steps["logistic_regression"].coef_[0]
    coefficient_rows = sorted(
        [
            {
                "feature_name": name,
                "coefficient": f"{float(value):.12f}",
                "absolute_coefficient": f"{abs(float(value)):.12f}",
                "direction": "dirty_positive" if value > 0 else "clean_negative" if value < 0 else "neutral",
            }
            for name, value in zip(FEATURE_NAMES, coef)
        ],
        key=lambda row: float(row["absolute_coefficient"]),
        reverse=True,
    )

    (output_dir / "experiment_config.json").write_text(json.dumps(json_ready(config), indent=2), encoding="utf-8")
    (output_dir / "feature_schema.json").write_text(json.dumps(json_ready(feature_schema), indent=2), encoding="utf-8")
    (output_dir / "model_versions.json").write_text(json.dumps(json_ready(versions), indent=2), encoding="utf-8")
    (output_dir / "training_summary.json").write_text(json.dumps(json_ready(training_summary), indent=2), encoding="utf-8")
    (output_dir / "metrics_by_split.json").write_text(json.dumps(json_ready(metrics), indent=2), encoding="utf-8")
    write_csv(output_dir / "threshold_selection.csv", ["threshold", "validation_precision_dirty_positive", "validation_recall_dirty_positive", "validation_f1_dirty_positive", "eligible_by_precision_rule", "selection_rank", "selected", "selection_reason"], threshold_rows)
    write_csv(output_dir / "split_predictions.csv", ["crop_path", "dataset_split", "crop_label", "y_true", "dummy_prediction", "logistic_probability_dirty_positive", "logistic_prediction", "selected_threshold"], prediction_rows)
    (output_dir / "confusion_matrices.json").write_text(json.dumps(json_ready(matrices), indent=2), encoding="utf-8")
    write_csv(output_dir / "feature_coefficients.csv", ["feature_name", "coefficient", "absolute_coefficient", "direction"], coefficient_rows)
    with (output_dir / "baseline_model.pkl").open("wb") as handle:
        pickle.dump(logistic, handle)
    (output_dir / "baseline_report.md").write_text(report_text(training_summary, metrics, coefficient_rows), encoding="utf-8")

    return {"training_summary": training_summary, "metrics": metrics, "versions": versions, "top_coefficients": coefficient_rows[:10]}


def format_metric(metrics: dict[str, Any]) -> str:
    if not metrics.get("available"):
        return f"unavailable ({metrics.get('unavailable_reason')})"
    return (
        f"acc={metrics['accuracy']:.4f}, precision_dirty={metrics['precision_dirty_positive']:.4f}, "
        f"recall_dirty={metrics['recall_dirty_positive']:.4f}, f1_dirty={metrics['f1_dirty_positive']:.4f}, "
        f"FN_dirty={metrics['false_negative_dirty_count']}, FP_dirty={metrics['false_positive_dirty_count']}"
    )


def report_text(training_summary: dict[str, Any], metrics: dict[str, Any], coefficient_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Crop-Level Binary Baseline Experiment",
        "",
        "## วัตถุประสงค์และขอบเขต",
        "ทดลอง baseline แบบ crop-level เพื่อแยก dirty_positive กับ clean_negative เท่านั้น ไม่ใช่การให้คะแนนคุณภาพทั้งภาพ ไม่ใช่ PASS/FAIL ของรังนกทั้งใบ และไม่ใช่ production decision",
        "",
        "## Dataset และ Leakage Safeguards",
        "ใช้ split จาก crop_lineage_manifest run_002 เท่านั้น ไม่มีการ split ใหม่ และ feature มาจาก pixel ของ crop หลัง resize เพื่อ feature extraction เท่านั้น",
        f"Marker leakage preflight: {training_summary['marker_leakage_decision']}, marker_like_count={training_summary['marker_like_count']}, low_blue_signal_count={training_summary['low_blue_signal_count']}",
        "",
        "## Feature Categories",
        "grayscale intensity/statistics/histogram, Laplacian/Sobel edge texture, และ HSV color statistics/histograms",
        "",
        "## Models",
        "DummyClassifier(strategy='most_frequent') และ LogisticRegression pipeline with StandardScaler, class_weight='balanced'",
        "",
        "## Threshold Selection",
        f"เลือก threshold จาก validation เท่านั้น: {training_summary['selected_threshold']:.2f}; {training_summary['threshold_selection_result']}",
        "",
        "## Metrics",
    ]
    for model_name, by_split in metrics.items():
        lines.append(f"### {model_name}")
        for split in ["train", "validation", "test"]:
            lines.append(f"- {split}: {format_metric(by_split[split])}")
    lines.extend(
        [
            "",
            "## Top Feature Coefficients",
        ]
    )
    for row in coefficient_rows[:10]:
        lines.append(f"- {row['feature_name']}: {row['coefficient']} ({row['direction']})")
    lines.extend(
        [
            "",
            "## Pilot Limitations",
            "- มี independent source images เพียง 15 ภาพ",
            "- validation ใช้ crop จาก source image 1 ภาพ",
            "- test ใช้ crop จาก source images 2 ภาพ",
            "- crop จาก source เดียวกันมี correlation สูง",
            "- ผลนี้ยังไม่รองรับ deployment หรือคำกล่าวอ้างเรื่อง general performance",
            "",
            "No source image, crop, label, Ground Truth, or split manifest was modified.",
            "No Blue Marker or annotation metadata was used as a model feature.",
            "Test results were not used to select the threshold.",
            "This baseline does not produce bird-nest PASS/FAIL decisions.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run leakage-safe crop-level baseline experiment.")
    parser.add_argument("--crops-dir", type=Path, required=True)
    parser.add_argument("--lineage-manifest", type=Path, required=True)
    parser.add_argument("--marker-audit-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        result = run_experiment(args.crops_dir, args.lineage_manifest, args.marker_audit_dir, args.output_dir, args.seed)
    except ExperimentError as exc:
        raise SystemExit(f"BLOCKED_INPUT_VALIDATION: {exc}") from exc
    summary = result["training_summary"]
    print(f"Crop baseline experiment complete: {args.output_dir.resolve()}")
    print(
        f"Counts: train={summary['train_crop_count']} validation={summary['validation_crop_count']} test={summary['test_crop_count']}"
    )
    print(f"Selected threshold: {summary['selected_threshold']:.2f}")
    print(f"Threshold reason: {summary['threshold_selection_result']}")


if __name__ == "__main__":
    main()
