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

from tools.run_crop_baseline_experiment import (
    FEATURE_NAMES,
    ExperimentError,
    extract_features,
    run_experiment,
    select_threshold,
)


LINEAGE_COLUMNS = [
    "output_file",
    "label",
    "resolved_image_id",
    "resolved_source_image",
    "dataset_split",
]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_image(path: Path, value: int, tint: tuple[int, int, int] = (0, 0, 0)) -> None:
    image = np.full((24, 24, 3), value, dtype=np.uint8)
    if tint != (0, 0, 0):
        image[:, :] = np.clip(image.astype(np.int16) + np.array(tint, dtype=np.int16), 0, 255).astype(np.uint8)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"Could not write image: {path}")


def make_fixture(root: Path, marker_decision: str = "SAFE_TO_TRAIN", marker_like_count: int = 0) -> tuple[Path, Path, Path]:
    crops_dir = root / "Crops"
    marker_dir = root / "marker"
    crops_dir.mkdir()
    marker_dir.mkdir()
    for subdir in ["dirty_positive", "clean_negative"]:
        (crops_dir / subdir).mkdir()

    rows = [
        ("dirty_positive/train_dp_1.jpg", "dirty_positive", "1", "train", 45, (25, 0, 0)),
        ("dirty_positive/train_dp_2.jpg", "dirty_positive", "1", "train", 55, (25, 0, 0)),
        ("clean_negative/train_cn_1.jpg", "clean_negative", "2", "train", 210, (0, 0, 0)),
        ("clean_negative/train_cn_2.jpg", "clean_negative", "2", "train", 220, (0, 0, 0)),
        ("dirty_positive/val_dp.jpg", "dirty_positive", "3", "validation", 60, (25, 0, 0)),
        ("clean_negative/val_cn.jpg", "clean_negative", "3", "validation", 205, (0, 0, 0)),
        ("dirty_positive/test_dp.jpg", "dirty_positive", "4", "test", 65, (25, 0, 0)),
        ("clean_negative/test_cn.jpg", "clean_negative", "4", "test", 200, (0, 0, 0)),
    ]
    lineage_rows = []
    marker_rows = []
    for crop_path, label, image_id, split, value, tint in rows:
        write_image(crops_dir / crop_path, value, tint)
        lineage_rows.append(
            {
                "output_file": crop_path,
                "label": label,
                "resolved_image_id": image_id,
                "resolved_source_image": f"{image_id}.jpg",
                "dataset_split": split,
            }
        )
        marker_rows.append({"output_file": crop_path, "marker_contamination_status": "none"})
    write_csv(crops_dir / "metadata.csv", ["output_file", "label"], lineage_rows)
    lineage_path = root / "crop_lineage_manifest.csv"
    write_csv(lineage_path, LINEAGE_COLUMNS, lineage_rows)
    (marker_dir / "marker_leakage_summary.json").write_text(
        json.dumps({"decision": marker_decision, "marker_like_count": marker_like_count}),
        encoding="utf-8",
    )
    write_csv(marker_dir / "crop_marker_leakage_manifest.csv", ["output_file", "marker_contamination_status"], marker_rows)
    return crops_dir, lineage_path, marker_dir


class CropBaselineExperimentTests(unittest.TestCase):
    def test_feature_vector_contains_only_numeric_image_derived_values(self) -> None:
        image = np.full((32, 32, 3), 128, dtype=np.uint8)
        features = extract_features(image)
        self.assertEqual(len(features), len(FEATURE_NAMES))
        self.assertTrue(np.issubdtype(features.dtype, np.number))
        self.assertTrue(np.isfinite(features).all())

    def test_feature_schema_is_deterministic_across_repeated_extraction(self) -> None:
        image = np.zeros((32, 32, 3), dtype=np.uint8)
        first = extract_features(image)
        second = extract_features(image)
        self.assertEqual(FEATURE_NAMES, list(FEATURE_NAMES))
        np.testing.assert_allclose(first, second)

    def test_crop_outside_crops_directory_fails_safely(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, lineage, marker_dir = make_fixture(root)
            rows = list(csv.DictReader(lineage.open(newline="", encoding="utf-8")))
            rows[0]["output_file"] = "../outside.jpg"
            write_csv(lineage, LINEAGE_COLUMNS, rows)
            out = root / "out"
            with self.assertRaises(ExperimentError):
                run_experiment(crops_dir, lineage, marker_dir, out, seed=1, enforce_empty_output=False)
            self.assertFalse(out.exists())

    def test_missing_crop_file_fails_before_partial_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, lineage, marker_dir = make_fixture(root)
            (crops_dir / "dirty_positive" / "train_dp_1.jpg").unlink()
            out = root / "out"
            with self.assertRaises(ExperimentError):
                run_experiment(crops_dir, lineage, marker_dir, out, seed=1, enforce_empty_output=False)
            self.assertFalse(out.exists())

    def test_marker_audit_decision_blocks_experiment(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, lineage, marker_dir = make_fixture(root, marker_decision="MANUAL_REVIEW_REQUIRED")
            with self.assertRaises(ExperimentError):
                run_experiment(crops_dir, lineage, marker_dir, root / "out", seed=1, enforce_empty_output=False)

    def test_nonzero_marker_like_count_blocks_experiment(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, lineage, marker_dir = make_fixture(root, marker_like_count=1)
            with self.assertRaises(ExperimentError):
                run_experiment(crops_dir, lineage, marker_dir, root / "out", seed=1, enforce_empty_output=False)

    def test_same_seed_produces_identical_threshold_selection_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, lineage, marker_dir = make_fixture(root)
            run_experiment(crops_dir, lineage, marker_dir, root / "out1", seed=20260624, enforce_empty_output=False)
            run_experiment(crops_dir, lineage, marker_dir, root / "out2", seed=20260624, enforce_empty_output=False)
            self.assertEqual(
                (root / "out1" / "threshold_selection.csv").read_text(encoding="utf-8"),
                (root / "out2" / "threshold_selection.csv").read_text(encoding="utf-8"),
            )

    def test_test_labels_are_not_passed_into_threshold_selection_logic(self) -> None:
        y_validation = np.array([1, 1, 0, 0], dtype=np.int32)
        probabilities = np.array([0.9, 0.7, 0.2, 0.1], dtype=np.float64)
        first = select_threshold(y_validation, probabilities)
        poisoned_test_labels = np.array([0, 0, 0, 0], dtype=np.int32)
        self.assertIsNotNone(poisoned_test_labels)
        second = select_threshold(y_validation, probabilities)
        self.assertEqual(first, second)

    def test_split_assignments_in_output_equal_lineage_manifest(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, lineage, marker_dir = make_fixture(root)
            run_experiment(crops_dir, lineage, marker_dir, root / "out", seed=1, enforce_empty_output=False)
            lineage_splits = {
                row["output_file"]: row["dataset_split"]
                for row in csv.DictReader(lineage.open(newline="", encoding="utf-8"))
            }
            output_splits = {
                row["crop_path"]: row["dataset_split"]
                for row in csv.DictReader((root / "out" / "split_predictions.csv").open(newline="", encoding="utf-8"))
            }
            self.assertEqual(output_splits, lineage_splits)

    def test_input_manifest_content_remains_unchanged_after_experiment(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, lineage, marker_dir = make_fixture(root)
            before = lineage.read_text(encoding="utf-8")
            run_experiment(crops_dir, lineage, marker_dir, root / "out", seed=1, enforce_empty_output=False)
            self.assertEqual(lineage.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
