from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import sklearn
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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.run_crop_baseline_experiment import (
    FEATURE_NAMES,
    NEGATIVE_CLASS,
    POSITIVE_CLASS,
    THRESHOLD_CANDIDATES,
    extract_features,
    select_threshold,
)


VALID_LABELS = {POSITIVE_CLASS, NEGATIVE_CLASS}
SEED_DEFAULT = 20260624
PRIMARY_CSV_OUTPUTS = [
    "fold_assignments.csv",
    "fold_threshold_selection.csv",
    "sourcewise_metrics.csv",
    "sourcewise_predictions.csv",
]


class RobustnessError(RuntimeError):
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
        raise RobustnessError(f"Output directory already contains files: {output_dir}")


def numeric_source_sort(source_id: str) -> tuple[int, str]:
    return (int(source_id), source_id) if source_id.isdigit() else (10**9, source_id)


def safe_crop_path(crops_dir: Path, crop_path_text: str) -> Path:
    crops_root = crops_dir.resolve()
    candidate = (crops_root / crop_path_text).resolve()
    try:
        candidate.relative_to(crops_root)
    except ValueError as exc:
        raise RobustnessError(f"Crop path is outside Crops directory: {crop_path_text}") from exc
    return candidate


def validate_marker_audit(marker_audit_dir: Path) -> dict[str, Any]:
    summary_path = marker_audit_dir / "marker_leakage_summary.json"
    manifest_path = marker_audit_dir / "crop_marker_leakage_manifest.csv"
    if not summary_path.exists() or not manifest_path.exists():
        raise RobustnessError("Marker leakage audit files are missing")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("decision") != "SAFE_TO_TRAIN":
        raise RobustnessError("Marker leakage decision is not SAFE_TO_TRAIN")
    if int(summary.get("marker_like_count", -1)) != 0:
        raise RobustnessError("marker_like_count is not zero")
    return summary


def load_dataset(crops_dir: Path, lineage_manifest: Path, marker_audit_dir: Path) -> dict[str, Any]:
    marker_summary = validate_marker_audit(marker_audit_dir)
    columns, rows = read_csv(lineage_manifest)
    required = ["output_file", "label", "resolved_image_id", "dataset_split"]
    missing = [column for column in required if column not in columns]
    if missing:
        raise RobustnessError(f"Lineage manifest missing columns: {', '.join(missing)}")

    records: list[dict[str, Any]] = []
    features: list[np.ndarray] = []
    labels: list[int] = []
    source_to_splits: dict[str, set[str]] = defaultdict(set)
    label_counts = Counter()

    for row_index, row in enumerate(rows, start=2):
        if row["label"] not in VALID_LABELS:
            raise RobustnessError(f"Invalid label at row {row_index}: {row['label']}")
        if not row["resolved_image_id"]:
            raise RobustnessError(f"Missing resolved_image_id at row {row_index}")
        crop_path = safe_crop_path(crops_dir, row["output_file"])
        if not crop_path.exists():
            raise RobustnessError(f"Missing crop file at row {row_index}: {row['output_file']}")
        image = cv2.imread(str(crop_path), cv2.IMREAD_COLOR)
        if image is None:
            raise RobustnessError(f"Unreadable crop image at row {row_index}: {row['output_file']}")

        source_id = row["resolved_image_id"]
        source_to_splits[source_id].add(row["dataset_split"])
        label_counts[row["label"]] += 1
        features.append(extract_features(image))
        labels.append(1 if row["label"] == POSITIVE_CLASS else 0)
        records.append(
            {
                "source_id": source_id,
                "crop_path": row["output_file"],
                "crop_label": row["label"],
                "y_true": 1 if row["label"] == POSITIVE_CLASS else 0,
            }
        )

    if len(source_to_splits) != 15:
        raise RobustnessError(f"Expected exactly 15 independent source images, found {len(source_to_splits)}")
    bad_sources = {source: splits for source, splits in source_to_splits.items() if len(splits) != 1}
    if bad_sources:
        raise RobustnessError(f"At least one source image maps to multiple finalized splits: {bad_sources}")
    if not label_counts[POSITIVE_CLASS] or not label_counts[NEGATIVE_CLASS]:
        raise RobustnessError("Both crop classes must exist overall")

    return {
        "records": records,
        "X": np.vstack(features).astype(np.float64),
        "y": np.array(labels, dtype=np.int32),
        "source_ids": sorted(source_to_splits, key=numeric_source_sort),
        "marker_summary": marker_summary,
        "input_hashes": {
            "crop_lineage_manifest": file_sha256(lineage_manifest),
            "marker_leakage_summary": file_sha256(marker_audit_dir / "marker_leakage_summary.json"),
            "crop_marker_leakage_manifest": file_sha256(marker_audit_dir / "crop_marker_leakage_manifest.csv"),
            "baseline_feature_source": file_sha256(Path("tools/run_crop_baseline_experiment.py")),
        },
    }


def rows_for_sources(dataset: dict[str, Any], source_ids: set[str]) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    indices = [index for index, record in enumerate(dataset["records"]) if record["source_id"] in source_ids]
    return dataset["X"][indices], dataset["y"][indices], [dataset["records"][index] for index in indices]


def positive_probabilities(model: Any, X: np.ndarray) -> np.ndarray:
    probabilities = model.predict_proba(X)
    return probabilities[:, list(model.classes_).index(1)]


def y_to_label(value: int) -> str:
    return POSITIVE_CLASS if int(value) == 1 else NEGATIVE_CLASS


def evaluate(y_true: np.ndarray, predictions: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    if len(set(int(value) for value in y_true)) < 2:
        return {"metric_status": "unavailable", "notes": "outer source lacks both crop classes"}
    matrix = confusion_matrix(y_true, predictions, labels=[0, 1])
    return {
        "metric_status": "available",
        "notes": "",
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision_dirty_positive": float(precision_score(y_true, predictions, pos_label=1, zero_division=0)),
        "recall_dirty_positive": float(recall_score(y_true, predictions, pos_label=1, zero_division=0)),
        "f1_dirty_positive": float(f1_score(y_true, predictions, pos_label=1, zero_division=0)),
        "false_negative_dirty_count": int(matrix[1, 0]),
        "false_positive_dirty_count": int(matrix[0, 1]),
        "confusion_matrix": matrix.tolist(),
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "average_precision": float(average_precision_score(y_true, probabilities)),
    }


def distribution(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"median": None, "mean": None, "minimum": None, "maximum": None, "p25": None, "p75": None}
    arr = np.array(values, dtype=np.float64)
    return {
        "median": float(np.median(arr)),
        "mean": float(np.mean(arr)),
        "minimum": float(np.min(arr)),
        "maximum": float(np.max(arr)),
        "p25": float(np.percentile(arr, 25)),
        "p75": float(np.percentile(arr, 75)),
    }


def decision_from(metrics_rows: list[dict[str, Any]]) -> str:
    available = [row for row in metrics_rows if row["metric_status"] == "available"]
    if len(available) < len(metrics_rows):
        return "BASELINE_INSUFFICIENT_FOR_DECISION"
    recalls = [float(row["recall_dirty_positive"]) for row in available]
    precisions = [float(row["precision_dirty_positive"]) for row in available]
    low_recall_fraction = sum(1 for value in recalls if value < 0.60) / len(recalls)
    if np.median(recalls) >= 0.80 and np.median(precisions) >= 0.80 and low_recall_fraction <= 0.20:
        return "BASELINE_SIGNAL_PRESENT"
    return "BASELINE_UNSTABLE"


def run_robustness(crops_dir: Path, lineage_manifest: Path, marker_audit_dir: Path, output_dir: Path, seed: int, enforce_empty_output: bool = True) -> dict[str, Any]:
    if enforce_empty_output:
        ensure_output_empty(output_dir)
    dataset = load_dataset(crops_dir, lineage_manifest, marker_audit_dir)
    source_ids = dataset["source_ids"]

    assignment_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    metrics_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    fallback_folds: list[str] = []
    selected_thresholds: list[float] = []

    for fold_index, outer_source in enumerate(source_ids, start=1):
        outer_idx = source_ids.index(outer_source)
        validation_source = source_ids[(outer_idx + 1) % len(source_ids)]
        training_sources = [source for source in source_ids if source not in {outer_source, validation_source}]

        X_train, y_train, train_records = rows_for_sources(dataset, set(training_sources))
        X_val, y_val, val_records = rows_for_sources(dataset, {validation_source})
        X_test, y_test, test_records = rows_for_sources(dataset, {outer_source})
        if len(set(y_train.tolist())) < 2:
            raise RobustnessError(f"Fold {fold_index} training sources lack both classes")

        model = Pipeline(
            [
                ("standard_scaler", StandardScaler()),
                ("logistic_regression", LogisticRegression(class_weight="balanced", random_state=seed, max_iter=2000)),
            ]
        )
        model.fit(X_train, y_train)
        val_prob = positive_probabilities(model, X_val)
        selected_threshold, selection_reason, fold_threshold_rows = select_threshold(y_val, val_prob)
        selected_thresholds.append(selected_threshold)
        if selection_reason.startswith("fallback"):
            fallback_folds.append(str(fold_index))

        for threshold_row in fold_threshold_rows:
            threshold_rows.append(
                {
                    "fold_id": fold_index,
                    "outer_test_image_id": outer_source,
                    "inner_validation_image_id": validation_source,
                    **{key: threshold_row[key] for key in ["threshold", "validation_precision_dirty_positive", "validation_recall_dirty_positive", "validation_f1_dirty_positive", "eligible_by_precision_rule", "selected", "selection_reason"]},
                }
            )

        test_prob = positive_probabilities(model, X_test)
        test_pred = (test_prob >= selected_threshold).astype(np.int32)
        metrics = evaluate(y_test, test_pred, test_prob)
        class_counts = Counter(record["crop_label"] for record in test_records)
        metrics_rows.append(
            {
                "fold_id": fold_index,
                "outer_test_image_id": outer_source,
                "selected_threshold": f"{selected_threshold:.2f}",
                "test_crop_count": len(test_records),
                "test_dirty_positive_count": class_counts[POSITIVE_CLASS],
                "test_clean_negative_count": class_counts[NEGATIVE_CLASS],
                "accuracy": "" if metrics["metric_status"] != "available" else f"{metrics['accuracy']:.8f}",
                "precision_dirty_positive": "" if metrics["metric_status"] != "available" else f"{metrics['precision_dirty_positive']:.8f}",
                "recall_dirty_positive": "" if metrics["metric_status"] != "available" else f"{metrics['recall_dirty_positive']:.8f}",
                "f1_dirty_positive": "" if metrics["metric_status"] != "available" else f"{metrics['f1_dirty_positive']:.8f}",
                "false_negative_dirty_count": "" if metrics["metric_status"] != "available" else metrics["false_negative_dirty_count"],
                "false_positive_dirty_count": "" if metrics["metric_status"] != "available" else metrics["false_positive_dirty_count"],
                "roc_auc": "" if metrics["metric_status"] != "available" else f"{metrics['roc_auc']:.8f}",
                "average_precision": "" if metrics["metric_status"] != "available" else f"{metrics['average_precision']:.8f}",
                "metric_status": metrics["metric_status"],
                "notes": metrics["notes"],
                "_confusion_matrix": metrics.get("confusion_matrix"),
            }
        )

        for record, probability, prediction in zip(test_records, test_prob, test_pred):
            prediction_rows.append(
                {
                    "fold_id": fold_index,
                    "outer_test_image_id": outer_source,
                    "crop_path": record["crop_path"],
                    "crop_label": record["crop_label"],
                    "y_true": record["y_true"],
                    "probability_dirty_positive": f"{float(probability):.8f}",
                    "prediction": y_to_label(int(prediction)),
                    "selected_threshold": f"{selected_threshold:.2f}",
                }
            )

        assignment_rows.append(
            {
                "fold_id": fold_index,
                "outer_test_image_id": outer_source,
                "inner_validation_image_id": validation_source,
                "inner_training_image_ids": ";".join(training_sources),
                "train_source_count": len(training_sources),
                "validation_source_count": 1,
                "test_source_count": 1,
                "train_crop_count": len(train_records),
                "validation_crop_count": len(val_records),
                "test_crop_count": len(test_records),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=False)
    assignment_path = output_dir / "fold_assignments.csv"
    threshold_path = output_dir / "fold_threshold_selection.csv"
    metrics_path = output_dir / "sourcewise_metrics.csv"
    predictions_path = output_dir / "sourcewise_predictions.csv"
    write_csv(assignment_path, ["fold_id", "outer_test_image_id", "inner_validation_image_id", "inner_training_image_ids", "train_source_count", "validation_source_count", "test_source_count", "train_crop_count", "validation_crop_count", "test_crop_count"], assignment_rows)
    write_csv(threshold_path, ["fold_id", "outer_test_image_id", "inner_validation_image_id", "threshold", "validation_precision_dirty_positive", "validation_recall_dirty_positive", "validation_f1_dirty_positive", "eligible_by_precision_rule", "selected", "selection_reason"], threshold_rows)
    write_csv(metrics_path, ["fold_id", "outer_test_image_id", "selected_threshold", "test_crop_count", "test_dirty_positive_count", "test_clean_negative_count", "accuracy", "precision_dirty_positive", "recall_dirty_positive", "f1_dirty_positive", "false_negative_dirty_count", "false_positive_dirty_count", "roc_auc", "average_precision", "metric_status", "notes"], metrics_rows)
    write_csv(predictions_path, ["fold_id", "outer_test_image_id", "crop_path", "crop_label", "y_true", "probability_dirty_positive", "prediction", "selected_threshold"], prediction_rows)

    metric_distribution = {}
    for metric_name in ["accuracy", "precision_dirty_positive", "recall_dirty_positive", "f1_dirty_positive", "false_negative_dirty_count", "false_positive_dirty_count"]:
        values = [float(row[metric_name]) for row in metrics_rows if row["metric_status"] == "available" and row[metric_name] != ""]
        metric_distribution[metric_name] = distribution(values)
    final_decision = decision_from(metrics_rows)
    summary = {
        "seed": seed,
        "source_image_count": len(source_ids),
        "fold_count": len(metrics_rows),
        "feature_schema_match_status": f"imported from tools/run_crop_baseline_experiment.py; feature_count={len(FEATURE_NAMES)}",
        "marker_leakage_decision": dataset["marker_summary"]["decision"],
        "marker_like_count": dataset["marker_summary"]["marker_like_count"],
        "threshold_selection_policy": "inner validation source only; precision>=0.80 then max recall, tie closest to 0.50; fallback max F1",
        "sourcewise_metric_distribution": metric_distribution,
        "folds_with_precision_rule_fallback": fallback_folds,
        "mean_selected_threshold": float(np.mean(selected_thresholds)),
        "median_selected_threshold": float(np.median(selected_thresholds)),
        "min_selected_threshold": float(np.min(selected_thresholds)),
        "max_selected_threshold": float(np.max(selected_thresholds)),
        "final_decision": final_decision,
        "dependency_versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "input_file_hashes": dataset["input_hashes"],
        "output_hash_scope": "primary_csv_artifacts_only",
        "output_file_hashes": {
            "fold_assignments.csv": file_sha256(assignment_path),
            "fold_threshold_selection.csv": file_sha256(threshold_path),
            "sourcewise_metrics.csv": file_sha256(metrics_path),
            "sourcewise_predictions.csv": file_sha256(predictions_path),
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (output_dir / "sourcewise_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "sourcewise_report.md").write_text(report_text(summary, metrics_rows), encoding="utf-8")
    return summary


def report_text(summary: dict[str, Any], metrics_rows: list[dict[str, Any]]) -> str:
    available = [row for row in metrics_rows if row["metric_status"] == "available"]
    best = max(available, key=lambda row: float(row["f1_dirty_positive"])) if available else None
    worst = min(available, key=lambda row: float(row["f1_dirty_positive"])) if available else None
    table = "\n".join(
        f"| {row['outer_test_image_id']} | {row['selected_threshold']} | {row['precision_dirty_positive']} | {row['recall_dirty_positive']} | {row['f1_dirty_positive']} | {row['false_negative_dirty_count']} | {row['false_positive_dirty_count']} |"
        for row in metrics_rows
    )
    dist = summary["sourcewise_metric_distribution"]
    dist_lines = "\n".join(
        f"- {name}: median={values['median']}, mean={values['mean']}, min={values['minimum']}, max={values['maximum']}, p25={values['p25']}, p75={values['p75']}"
        for name, values in dist.items()
    )
    return f"""# Sourcewise Crop Robustness Evaluation

## วัตถุประสงค์และขอบเขต
ประเมินความผันผวนแบบ leave-one-source-out ของ crop-level classifier สำหรับ dirty_positive vs clean_negative เท่านั้น ไม่ใช่ quality scoring ทั้งภาพ และไม่ใช่ production model

## ความต่างจาก baseline เดิม
baseline เดิมใช้ train/validation/test split ที่ finalize แล้วหนึ่งครั้ง ส่วน evaluation นี้วน 15 folds โดย hold out source image ทีละภาพ เลือก threshold จาก inner validation source ของ fold นั้นเท่านั้น แล้วประเมิน outer source หนึ่งครั้ง

## Leakage Safeguards
ใช้ feature extraction จาก crop pixels เท่านั้น และ import feature schema จาก baseline script เดิม ไม่ใช้ source ID, crop path, PASS/FAIL, quality score, Blue Marker หรือ annotation metadata เป็น feature

## Nested Threshold Selection
แต่ละ fold ใช้ source ถัดไปในลำดับเป็น validation source และ source ที่เหลือเป็น training source; outer test data ไม่ถูกใช้เลือก threshold

## Per-Source Metrics
| source | threshold | precision | recall | f1 | FN dirty | FP dirty |
|---|---:|---:|---:|---:|---:|---:|
{table}

## Distribution
{dist_lines}

## Best / Worst
- Best source by F1: {best['outer_test_image_id'] if best else 'unavailable'}
- Worst source by F1: {worst['outer_test_image_id'] if worst else 'unavailable'}

## Interpretation
ผลหลักคือ distribution ระดับ source ไม่ใช่ pooled crop accuracy เพราะ crop ใน source เดียวกัน correlated กัน และ source-to-source variation เป็น risk หลักของ pilot นี้

## Limitations
- 15 independent source images remain too few for deployment claims
- each fold uses only one validation source
- results are for pilot robustness assessment only

## Final Decision
{summary['final_decision']}

No source image, crop, label, Ground Truth, or split manifest was modified.
No Blue Marker or annotation metadata was used as a model feature.
Outer test data was never used to select its fold threshold.
This evaluation does not produce bird-nest PASS/FAIL decisions.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run nested sourcewise crop robustness evaluation.")
    parser.add_argument("--crops-dir", type=Path, required=True)
    parser.add_argument("--lineage-manifest", type=Path, required=True)
    parser.add_argument("--marker-audit-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=SEED_DEFAULT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        summary = run_robustness(args.crops_dir, args.lineage_manifest, args.marker_audit_dir, args.output_dir, args.seed)
    except RobustnessError as exc:
        raise SystemExit(f"BLOCKED_INPUT_VALIDATION: {exc}") from exc
    print(f"Sourcewise robustness evaluation complete: {args.output_dir.resolve()}")
    print(f"Folds: {summary['fold_count']}")
    print(f"Decision: {summary['final_decision']}")
    print(f"Threshold range: {summary['min_selected_threshold']:.2f} - {summary['max_selected_threshold']:.2f}")


if __name__ == "__main__":
    main()
