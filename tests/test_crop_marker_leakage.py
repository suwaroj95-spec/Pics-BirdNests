from __future__ import annotations

import csv
import hashlib
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

from tools.audit_crop_marker_leakage import AuditError, audit_crop_marker_leakage


LINEAGE_COLUMNS = [
    "source_id",
    "source_image",
    "marked_image",
    "output_file",
    "label",
    "resolved_image_id",
    "resolved_source_image",
    "dataset_split",
    "pass_fail_status",
    "lineage_status",
]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_image(path: Path, blue_rect: tuple[int, int, int, int] | None = None) -> None:
    image = np.full((32, 32, 3), 245, dtype=np.uint8)
    if blue_rect:
        x1, y1, x2, y2 = blue_rect
        image[y1:y2, x1:x2] = (255, 0, 0)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"Could not write synthetic image: {path}")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_fixture(root: Path, rows: list[dict[str, object]] | None = None) -> tuple[Path, Path]:
    crops_dir = root / "Crops"
    crops_dir.mkdir()
    (crops_dir / "dirty_positive").mkdir()
    (crops_dir / "clean_negative").mkdir()
    write_image(crops_dir / "dirty_positive" / "marker.jpg", (4, 4, 10, 10))
    write_image(crops_dir / "dirty_positive" / "tiny.jpg", (4, 4, 6, 6))
    write_image(crops_dir / "clean_negative" / "none.jpg")
    rows = rows or [
        {"source_id": "1", "source_image": "1.jpg", "marked_image": "1m.jpg", "output_file": "dirty_positive/marker.jpg", "label": "dirty_positive", "resolved_image_id": "1", "resolved_source_image": "1.jpg", "dataset_split": "train", "pass_fail_status": "PASS", "lineage_status": "resolved"},
        {"source_id": "1", "source_image": "1.jpg", "marked_image": "1m.jpg", "output_file": "dirty_positive/tiny.jpg", "label": "dirty_positive", "resolved_image_id": "1", "resolved_source_image": "1.jpg", "dataset_split": "train", "pass_fail_status": "PASS", "lineage_status": "resolved"},
        {"source_id": "2", "source_image": "2.jpg", "marked_image": "2m.jpg", "output_file": "clean_negative/none.jpg", "label": "clean_negative", "resolved_image_id": "2", "resolved_source_image": "2.jpg", "dataset_split": "test", "pass_fail_status": "FAIL", "lineage_status": "resolved"},
    ]
    write_csv(crops_dir / "metadata.csv", ["output_file", "label"], rows)
    lineage_path = root / "crop_lineage_manifest.csv"
    write_csv(lineage_path, LINEAGE_COLUMNS, rows)
    return crops_dir, lineage_path


class CropMarkerLeakageTests(unittest.TestCase):
    def test_marker_like_component_area_at_least_20_px(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, lineage = make_fixture(root)

            audit_crop_marker_leakage(crops_dir, lineage, root / "out", sample_limit_per_group=20, enforce_empty_output=False)

            with (root / "out" / "crop_marker_leakage_manifest.csv").open(newline="", encoding="utf-8") as handle:
                rows = {row["output_file"]: row for row in csv.DictReader(handle)}
            self.assertEqual(rows["dirty_positive/marker.jpg"]["marker_contamination_status"], "marker_like")

    def test_tiny_blue_speck_below_20_px_is_low_blue_signal(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, lineage = make_fixture(root)

            audit_crop_marker_leakage(crops_dir, lineage, root / "out", sample_limit_per_group=20, enforce_empty_output=False)

            with (root / "out" / "crop_marker_leakage_manifest.csv").open(newline="", encoding="utf-8") as handle:
                rows = {row["output_file"]: row for row in csv.DictReader(handle)}
            self.assertEqual(rows["dirty_positive/tiny.jpg"]["marker_contamination_status"], "low_blue_signal")

    def test_non_blue_crop_is_none(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, lineage = make_fixture(root)

            audit_crop_marker_leakage(crops_dir, lineage, root / "out", sample_limit_per_group=20, enforce_empty_output=False)

            with (root / "out" / "crop_marker_leakage_manifest.csv").open(newline="", encoding="utf-8") as handle:
                rows = {row["output_file"]: row for row in csv.DictReader(handle)}
            self.assertEqual(rows["clean_negative/none.jpg"]["marker_contamination_status"], "none")

    def test_crop_path_outside_crops_directory_fails_safely(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            rows = [{"source_id": "1", "source_image": "1.jpg", "marked_image": "1m.jpg", "output_file": "../outside.jpg", "label": "dirty_positive", "resolved_image_id": "1", "resolved_source_image": "1.jpg", "dataset_split": "train", "pass_fail_status": "PASS", "lineage_status": "resolved"}]
            crops_dir, lineage = make_fixture(root, rows)
            out = root / "out"

            with self.assertRaises(AuditError):
                audit_crop_marker_leakage(crops_dir, lineage, out, sample_limit_per_group=20, enforce_empty_output=False)
            self.assertFalse(out.exists())

    def test_missing_crop_fails_before_partial_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            rows = [{"source_id": "1", "source_image": "1.jpg", "marked_image": "1m.jpg", "output_file": "dirty_positive/missing.jpg", "label": "dirty_positive", "resolved_image_id": "1", "resolved_source_image": "1.jpg", "dataset_split": "train", "pass_fail_status": "PASS", "lineage_status": "resolved"}]
            crops_dir, lineage = make_fixture(root, rows)
            out = root / "out"

            with self.assertRaises(AuditError):
                audit_crop_marker_leakage(crops_dir, lineage, out, sample_limit_per_group=20, enforce_empty_output=False)
            self.assertFalse(out.exists())

    def test_aggregate_summary_counts_by_split_and_label(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, lineage = make_fixture(root)

            summary = audit_crop_marker_leakage(crops_dir, lineage, root / "out", sample_limit_per_group=20, enforce_empty_output=False)

            self.assertEqual(summary["train_crop_count"], 2)
            self.assertEqual(summary["test_crop_count"], 1)
            self.assertEqual(summary["dirty_positive_count"], 2)
            self.assertEqual(summary["clean_negative_count"], 1)
            self.assertEqual(summary["marker_like_dirty_positive_count"], 1)
            self.assertEqual(summary["marker_like_clean_negative_count"], 0)

    def test_input_csv_content_remains_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, lineage = make_fixture(root)
            before = lineage.read_text(encoding="utf-8")

            audit_crop_marker_leakage(crops_dir, lineage, root / "out", sample_limit_per_group=20, enforce_empty_output=False)

            self.assertEqual(lineage.read_text(encoding="utf-8"), before)

    def test_summary_json_does_not_contain_own_hash(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, lineage = make_fixture(root)
            out = root / "out"

            audit_crop_marker_leakage(crops_dir, lineage, out, sample_limit_per_group=20, enforce_empty_output=False)

            summary = json.loads((out / "marker_leakage_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["output_hash_scope"], "primary_csv_artifacts_only")
            self.assertNotIn("marker_leakage_summary.json", summary["output_file_hashes"])
            for filename, expected_hash in summary["output_file_hashes"].items():
                path = out / filename
                self.assertTrue(path.exists(), filename)
                self.assertEqual(file_sha256(path), expected_hash)


if __name__ == "__main__":
    unittest.main()
