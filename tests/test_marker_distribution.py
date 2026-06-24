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

from tools.analyze_blue_marker_distribution import (
    IMAGE_SUMMARY_COLUMNS,
    MARKER_COLUMNS,
    detect_marker_instances,
    quality_grade,
    write_csv,
)


class MarkerDistributionTests(unittest.TestCase):
    def test_grade_boundaries(self) -> None:
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

    def test_synthetic_blue_marker_produces_one_instance(self) -> None:
        image = np.zeros((96, 96, 3), dtype=np.uint8)
        cv2.circle(image, (40, 48), 8, (255, 0, 0), thickness=-1)

        markers = detect_marker_instances(image, "synthetic", "syntheticm.jpg")

        self.assertEqual(len(markers), 1)
        marker = markers[0]
        self.assertEqual(marker.image_id, "synthetic")
        self.assertAlmostEqual(marker.x_center, 40, delta=1)
        self.assertAlmostEqual(marker.y_center, 48, delta=1)
        self.assertGreaterEqual(marker.component_area, 20)

    def test_output_schema_headers_are_written(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_dir:
            temp_path = Path(temp_dir)
            marker_path = temp_path / "marker_instances.csv"
            image_path = temp_path / "image_summary.csv"

            write_csv(marker_path, MARKER_COLUMNS, [])
            write_csv(image_path, IMAGE_SUMMARY_COLUMNS, [])

            with marker_path.open(newline="", encoding="utf-8") as handle:
                marker_header = next(csv.reader(handle))
            with image_path.open(newline="", encoding="utf-8") as handle:
                image_header = next(csv.reader(handle))

            self.assertEqual(marker_header, MARKER_COLUMNS)
            self.assertEqual(image_header, IMAGE_SUMMARY_COLUMNS)


if __name__ == "__main__":
    unittest.main()
