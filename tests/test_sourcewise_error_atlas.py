from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_sourcewise_error_atlas import (
    AtlasError,
    build_atlas,
    build_profiles,
    error_type,
    threshold_margin,
)


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_image(path: Path, value: int) -> None:
    image = np.full((24, 24, 3), value, dtype=np.uint8)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(path)


def make_fixture(root: Path, marker_decision: str = "SAFE_TO_TRAIN", marker_like_count: int = 0) -> tuple[Path, Path, Path, Path]:
    crops = root / "Crops"
    robustness = root / "robustness"
    marker = root / "marker"
    crops.mkdir()
    robustness.mkdir()
    marker.mkdir()
    (crops / "dirty_positive").mkdir()
    (crops / "clean_negative").mkdir()

    pred_rows = []
    lineage_rows = []
    metric_rows = []
    assign_rows = []
    for image_id in ["1", "2", "3"]:
        assign_rows.append({"fold_id": image_id, "outer_test_image_id": image_id, "inner_validation_image_id": "x", "inner_training_image_ids": "y", "train_source_count": 1, "validation_source_count": 1, "test_source_count": 1, "train_crop_count": 1, "validation_crop_count": 1, "test_crop_count": 4})
        examples = [
            ("dirty_positive", "dirty_positive", "tp", 0.9),
            ("dirty_positive", "clean_negative", "fn", 0.2),
            ("clean_negative", "clean_negative", "tn", 0.1),
            ("clean_negative", "dirty_positive", "fp", 0.8),
        ]
        for idx, (label, pred, suffix, prob) in enumerate(examples):
            rel = f"{label}/s{image_id}_{suffix}.jpg"
            write_image(crops / rel, 40 + idx * 40)
            pred_rows.append({"fold_id": image_id, "outer_test_image_id": image_id, "crop_path": rel, "crop_label": label, "y_true": 1 if label == "dirty_positive" else 0, "probability_dirty_positive": prob, "prediction": pred, "selected_threshold": "0.50"})
            lineage_rows.append({"output_file": rel, "label": label, "resolved_image_id": image_id, "resolved_source_image": f"{image_id}.jpg", "dataset_split": "train"})
        metric_rows.append({"fold_id": image_id, "outer_test_image_id": image_id, "selected_threshold": "0.50", "test_crop_count": 4, "test_dirty_positive_count": 2, "test_clean_negative_count": 2, "accuracy": "0.50000000", "precision_dirty_positive": "0.50000000", "recall_dirty_positive": "0.50000000", "f1_dirty_positive": "0.50000000", "false_negative_dirty_count": 1, "false_positive_dirty_count": 1, "roc_auc": "0.50000000", "average_precision": "0.50000000", "metric_status": "available", "notes": ""})

    write_csv(robustness / "sourcewise_predictions.csv", ["fold_id", "outer_test_image_id", "crop_path", "crop_label", "y_true", "probability_dirty_positive", "prediction", "selected_threshold"], pred_rows)
    write_csv(robustness / "sourcewise_metrics.csv", ["fold_id", "outer_test_image_id", "selected_threshold", "test_crop_count", "test_dirty_positive_count", "test_clean_negative_count", "accuracy", "precision_dirty_positive", "recall_dirty_positive", "f1_dirty_positive", "false_negative_dirty_count", "false_positive_dirty_count", "roc_auc", "average_precision", "metric_status", "notes"], metric_rows)
    write_csv(robustness / "fold_assignments.csv", ["fold_id", "outer_test_image_id", "inner_validation_image_id", "inner_training_image_ids", "train_source_count", "validation_source_count", "test_source_count", "train_crop_count", "validation_crop_count", "test_crop_count"], assign_rows)
    write_csv(robustness / "fold_threshold_selection.csv", ["fold_id", "threshold"], [])
    (robustness / "sourcewise_summary.json").write_text(json.dumps({"final_decision": "BASELINE_UNSTABLE"}), encoding="utf-8")
    lineage = root / "lineage.csv"
    write_csv(lineage, ["output_file", "label", "resolved_image_id", "resolved_source_image", "dataset_split"], lineage_rows)
    (marker / "marker_leakage_summary.json").write_text(json.dumps({"decision": marker_decision, "marker_like_count": marker_like_count}), encoding="utf-8")
    write_csv(marker / "crop_marker_leakage_manifest.csv", ["output_file"], [])
    return crops, robustness, lineage, marker


class SourcewiseErrorAtlasTests(unittest.TestCase):
    def test_error_categorization(self) -> None:
        self.assertEqual(error_type("dirty_positive", "dirty_positive"), "true_positive")
        self.assertEqual(error_type("clean_negative", "clean_negative"), "true_negative")
        self.assertEqual(error_type("clean_negative", "dirty_positive"), "false_positive")
        self.assertEqual(error_type("dirty_positive", "clean_negative"), "false_negative")

    def test_threshold_margin_for_fp_and_fn(self) -> None:
        self.assertAlmostEqual(threshold_margin("false_positive", 0.8, 0.5), 0.3)
        self.assertAlmostEqual(threshold_margin("false_negative", 0.2, 0.5), 0.3)

    def test_rankings_and_business_risk_formula(self) -> None:
        rows = [
            {"image_id": "1", "crop_label": "dirty_positive", "error_type": "false_negative"},
            {"image_id": "1", "crop_label": "clean_negative", "error_type": "true_negative"},
            {"image_id": "2", "crop_label": "dirty_positive", "error_type": "true_positive"},
            {"image_id": "2", "crop_label": "clean_negative", "error_type": "false_positive"},
        ]
        metrics = {
            "1": {"selected_threshold": "0.5", "accuracy": "0", "precision_dirty_positive": "0", "recall_dirty_positive": "0", "f1_dirty_positive": "0.25"},
            "2": {"selected_threshold": "0.5", "accuracy": "0", "precision_dirty_positive": "0", "recall_dirty_positive": "0", "f1_dirty_positive": "0.50"},
        }
        profiles, under, over, overall = build_profiles(rows, metrics)
        self.assertEqual(under[0], "1")
        self.assertEqual(over[0], "2")
        risk_1 = next(row for row in profiles if row["image_id"] == "1")["business_risk_score"]
        self.assertEqual(risk_1, "0.68750000")
        self.assertEqual(overall[0], "1")

    def test_crop_outside_crops_fails_safely(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            root = Path(temp)
            crops, robustness, lineage, marker = make_fixture(root)
            rows = list(csv.DictReader((robustness / "sourcewise_predictions.csv").open(newline="", encoding="utf-8")))
            rows[0]["crop_path"] = "../escape.jpg"
            write_csv(robustness / "sourcewise_predictions.csv", rows[0].keys(), rows)
            with self.assertRaises(AtlasError):
                build_atlas(crops, robustness, lineage, marker, root / "out", 1, enforce_empty_output=False)
            self.assertFalse((root / "out").exists())

    def test_missing_crop_fails_before_partial_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            root = Path(temp)
            crops, robustness, lineage, marker = make_fixture(root)
            (crops / "dirty_positive" / "s1_tp.jpg").unlink()
            with self.assertRaises(AtlasError):
                build_atlas(crops, robustness, lineage, marker, root / "out", 1, enforce_empty_output=False)
            self.assertFalse((root / "out").exists())

    def test_marker_blocks(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            root = Path(temp)
            crops, robustness, lineage, marker = make_fixture(root, marker_decision="MANUAL_REVIEW_REQUIRED")
            with self.assertRaises(AtlasError):
                build_atlas(crops, robustness, lineage, marker, root / "out", 1, enforce_empty_output=False)
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            root = Path(temp)
            crops, robustness, lineage, marker = make_fixture(root, marker_like_count=1)
            with self.assertRaises(AtlasError):
                build_atlas(crops, robustness, lineage, marker, root / "out", 1, enforce_empty_output=False)

    def test_contact_sheet_limit_and_summary_hash_scope(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            root = Path(temp)
            crops, robustness, lineage, marker = make_fixture(root)
            build_atlas(crops, robustness, lineage, marker, root / "out", 1, enforce_empty_output=False)
            selected = list(csv.DictReader((root / "out" / "selected_error_examples.csv").open(newline="", encoding="utf-8")))
            counts = {}
            for row in selected:
                key = (row["image_id"], row["error_type"])
                counts[key] = counts.get(key, 0) + 1
            self.assertTrue(all(count <= 1 for count in counts.values()))
            summary = json.loads((root / "out" / "error_atlas_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["output_hash_scope"], "primary_csv_artifacts_only")
            self.assertNotIn("error_atlas_summary.json", summary["output_file_hashes"])

    def test_input_files_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp:
            root = Path(temp)
            crops, robustness, lineage, marker = make_fixture(root)
            before = lineage.read_text(encoding="utf-8")
            build_atlas(crops, robustness, lineage, marker, root / "out", 1, enforce_empty_output=False)
            self.assertEqual(lineage.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
