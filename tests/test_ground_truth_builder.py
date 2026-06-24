from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_ground_truth_from_markers import (
    GROUND_TRUTH_COLUMNS,
    IMAGE_SUMMARY_COLUMNS,
    RADIUS_MAX,
    RADIUS_MIN,
    detect_marker_labels,
    clamp_radius,
    make_preview,
    quality_grade,
    write_csv,
)


class GroundTruthBuilderTests(unittest.TestCase):
    def test_grade_mapping(self) -> None:
        cases = {
            0: (95, "PASS"),
            9: (95, "PASS"),
            10: (90, "PASS"),
            20: (90, "PASS"),
            21: (80, "PASS"),
            30: (80, "PASS"),
            31: (70, "FAIL"),
        }
        for spot_count, expected in cases.items():
            with self.subTest(spot_count=spot_count):
                self.assertEqual(quality_grade(spot_count), expected)

    def test_radius_clamp(self) -> None:
        self.assertEqual(clamp_radius(RADIUS_MIN - 2), RADIUS_MIN)
        self.assertEqual(clamp_radius(32.5), 32.5)
        self.assertEqual(clamp_radius(RADIUS_MAX + 10), RADIUS_MAX)

    def test_no_automatic_merge_for_close_separate_markers(self) -> None:
        image = np.zeros((128, 128, 3), dtype=np.uint8)
        cv2.circle(image, (50, 64), 8, (255, 0, 0), thickness=-1)
        cv2.circle(image, (75, 64), 8, (255, 0, 0), thickness=-1)

        labels = detect_marker_labels(image, "synthetic")

        self.assertEqual(len(labels), 2)
        self.assertEqual([label.spot_id for label in labels], ["synthetic_spot_001", "synthetic_spot_002"])

    def test_required_csv_header_schema_exists(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_dir:
            temp_path = Path(temp_dir)
            manifest_path = temp_path / "ground_truth_manifest.csv"
            summary_path = temp_path / "image_quality_summary.csv"

            write_csv(manifest_path, GROUND_TRUTH_COLUMNS, [])
            write_csv(summary_path, IMAGE_SUMMARY_COLUMNS, [])

            with manifest_path.open(newline="", encoding="utf-8") as handle:
                manifest_header = next(csv.reader(handle))
            with summary_path.open(newline="", encoding="utf-8") as handle:
                summary_header = next(csv.reader(handle))

            self.assertEqual(manifest_header, GROUND_TRUTH_COLUMNS)
            self.assertEqual(summary_header, IMAGE_SUMMARY_COLUMNS)

    def test_preview_generation_writes_to_temp_directory_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_dir:
            temp_path = Path(temp_dir)
            preview_path = temp_path / "preview.jpg"
            image = np.zeros((128, 128, 3), dtype=np.uint8)
            labels = detect_marker_labels(
                cv2.circle(image.copy(), (64, 64), 8, (255, 0, 0), thickness=-1),
                "synthetic",
            )

            make_preview(image, labels, preview_path, "synthetic", 95, "PASS")

            self.assertTrue(preview_path.exists())
            self.assertTrue(preview_path.resolve().is_relative_to(temp_path.resolve()))


if __name__ == "__main__":
    unittest.main()
