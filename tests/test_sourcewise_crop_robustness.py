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

from tools.run_sourcewise_crop_robustness import RobustnessError, run_robustness, select_threshold


LINEAGE_COLUMNS = ["output_file", "label", "resolved_image_id", "resolved_source_image", "dataset_split"]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_image(path: Path, value: int) -> None:
    image = np.full((20, 20, 3), value, dtype=np.uint8)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"Could not write {path}")


def make_fixture(root: Path, decision: str = "SAFE_TO_TRAIN", marker_like_count: int = 0) -> tuple[Path, Path, Path]:
    crops_dir = root / "Crops"
    marker_dir = root / "marker"
    crops_dir.mkdir()
    marker_dir.mkdir()
    (crops_dir / "dirty_positive").mkdir()
    (crops_dir / "clean_negative").mkdir()
    rows = []
    splits = ["train", "validation", "test"]
    for source_id in range(1, 16):
        split = splits[(source_id - 1) % len(splits)]
        dirty = f"dirty_positive/s{source_id}_dirty.jpg"
        clean = f"clean_negative/s{source_id}_clean.jpg"
        write_image(crops_dir / dirty, 40 + source_id)
        write_image(crops_dir / clean, 200 - source_id)
        rows.extend(
            [
                {"output_file": dirty, "label": "dirty_positive", "resolved_image_id": str(source_id), "resolved_source_image": f"{source_id}.jpg", "dataset_split": split},
                {"output_file": clean, "label": "clean_negative", "resolved_image_id": str(source_id), "resolved_source_image": f"{source_id}.jpg", "dataset_split": split},
            ]
        )
    lineage = root / "crop_lineage_manifest.csv"
    write_csv(lineage, LINEAGE_COLUMNS, rows)
    write_csv(crops_dir / "metadata.csv", ["output_file", "label"], rows)
    (marker_dir / "marker_leakage_summary.json").write_text(
        json.dumps({"decision": decision, "marker_like_count": marker_like_count}),
        encoding="utf-8",
    )
    write_csv(marker_dir / "crop_marker_leakage_manifest.csv", ["output_file", "marker_contamination_status"], [{"output_file": row["output_file"], "marker_contamination_status": "none"} for row in rows])
    return crops_dir, lineage, marker_dir


class SourcewiseCropRobustnessTests(unittest.TestCase):
    def test_each_source_appears_once_as_outer_test(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops, lineage, marker = make_fixture(root)
            run_robustness(crops, lineage, marker, root / "out", seed=20260624, enforce_empty_output=False)
            with (root / "out" / "fold_assignments.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(sorted((row["outer_test_image_id"] for row in rows), key=int), [str(i) for i in range(1, 16)])

    def test_inner_validation_image_is_never_outer_test(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops, lineage, marker = make_fixture(root)
            run_robustness(crops, lineage, marker, root / "out", seed=20260624, enforce_empty_output=False)
            with (root / "out" / "fold_assignments.csv").open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    self.assertNotEqual(row["outer_test_image_id"], row["inner_validation_image_id"])

    def test_every_crop_from_one_source_stays_in_same_fold_role(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops, lineage, marker = make_fixture(root)
            run_robustness(crops, lineage, marker, root / "out", seed=20260624, enforce_empty_output=False)
            with (root / "out" / "sourcewise_predictions.csv").open(newline="", encoding="utf-8") as handle:
                predictions = list(csv.DictReader(handle))
            for source_id in range(1, 16):
                source_rows = [row for row in predictions if row["outer_test_image_id"] == str(source_id)]
                self.assertEqual(len(source_rows), 2)
                self.assertTrue(all(f"s{source_id}_" in row["crop_path"] for row in source_rows))

    def test_threshold_selection_uses_validation_labels_only(self) -> None:
        y_validation = np.array([1, 1, 0, 0], dtype=np.int32)
        probabilities = np.array([0.9, 0.8, 0.3, 0.2], dtype=np.float64)
        first = select_threshold(y_validation, probabilities)
        outer_test_labels = np.array([0, 0, 0, 0], dtype=np.int32)
        self.assertIsNotNone(outer_test_labels)
        second = select_threshold(y_validation, probabilities)
        self.assertEqual(first, second)

    def test_same_seed_inputs_produce_identical_assignments_and_thresholds(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops, lineage, marker = make_fixture(root)
            run_robustness(crops, lineage, marker, root / "out1", seed=20260624, enforce_empty_output=False)
            run_robustness(crops, lineage, marker, root / "out2", seed=20260624, enforce_empty_output=False)
            self.assertEqual((root / "out1" / "fold_assignments.csv").read_text(), (root / "out2" / "fold_assignments.csv").read_text())
            self.assertEqual((root / "out1" / "fold_threshold_selection.csv").read_text(), (root / "out2" / "fold_threshold_selection.csv").read_text())

    def test_missing_crop_file_fails_before_partial_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops, lineage, marker = make_fixture(root)
            (crops / "dirty_positive" / "s1_dirty.jpg").unlink()
            out = root / "out"
            with self.assertRaises(RobustnessError):
                run_robustness(crops, lineage, marker, out, seed=20260624, enforce_empty_output=False)
            self.assertFalse(out.exists())

    def test_marker_decision_not_safe_blocks_execution(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops, lineage, marker = make_fixture(root, decision="MANUAL_REVIEW_REQUIRED")
            with self.assertRaises(RobustnessError):
                run_robustness(crops, lineage, marker, root / "out", seed=20260624, enforce_empty_output=False)

    def test_nonzero_marker_like_count_blocks_execution(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops, lineage, marker = make_fixture(root, marker_like_count=1)
            with self.assertRaises(RobustnessError):
                run_robustness(crops, lineage, marker, root / "out", seed=20260624, enforce_empty_output=False)

    def test_input_lineage_manifest_remains_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops, lineage, marker = make_fixture(root)
            before = lineage.read_text(encoding="utf-8")
            run_robustness(crops, lineage, marker, root / "out", seed=20260624, enforce_empty_output=False)
            self.assertEqual(lineage.read_text(encoding="utf-8"), before)

    def test_summary_json_does_not_contain_own_hash(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops, lineage, marker = make_fixture(root)
            run_robustness(crops, lineage, marker, root / "out", seed=20260624, enforce_empty_output=False)
            summary = json.loads((root / "out" / "sourcewise_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["output_hash_scope"], "primary_csv_artifacts_only")
            self.assertNotIn("sourcewise_summary.json", summary["output_file_hashes"])


if __name__ == "__main__":
    unittest.main()
