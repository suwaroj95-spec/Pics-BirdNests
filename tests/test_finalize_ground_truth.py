from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.finalize_ground_truth import (
    FinalizationError,
    clamp_preview_radius,
    finalize_ground_truth,
)


MANIFEST_COLUMNS = [
    "image_id",
    "source_image",
    "marked_image",
    "spot_id",
    "x_center",
    "y_center",
    "radius",
    "component_area",
    "enclosing_circle_radius",
    "quality_score",
    "pass_fail_status",
    "manually_verified_alignment",
    "alignment_note",
    "marker_source",
    "label_confidence",
    "review_status",
    "notes",
]

IMAGE_COLUMNS = [
    "image_id",
    "source_image",
    "marked_image",
    "dirty_spot_count",
    "quality_score",
    "pass_fail_status",
    "manually_verified_alignment",
    "alignment_note",
    "preview_path",
    "review_status",
    "notes",
]

REVIEW_COLUMNS = [
    "image_id",
    "reason",
    "priority",
    "recommended_action",
    "manual_review_required",
    "source_image",
    "preview_path",
    "notes",
]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def base_manifest_rows() -> list[dict[str, object]]:
    return [
        {
            "image_id": "synthetic",
            "source_image": "synthetic.jpg",
            "marked_image": "syntheticm.jpg",
            "spot_id": "synthetic_spot_001",
            "x_center": 10,
            "y_center": 20,
            "radius": 16,
            "component_area": 30,
            "enclosing_circle_radius": 8,
            "quality_score": 95,
            "pass_fail_status": "PASS",
            "manually_verified_alignment": "true",
            "alignment_note": "visually verified marker-to-defect correspondence",
            "marker_source": "blue_marker",
            "label_confidence": "preliminary_verified",
            "review_status": "pending_preview_confirmation",
            "notes": "test",
        },
        {
            "image_id": "synthetic",
            "source_image": "synthetic.jpg",
            "marked_image": "syntheticm.jpg",
            "spot_id": "synthetic_spot_002",
            "x_center": 30,
            "y_center": 40,
            "radius": 30,
            "component_area": 40,
            "enclosing_circle_radius": 30,
            "quality_score": 95,
            "pass_fail_status": "PASS",
            "manually_verified_alignment": "true",
            "alignment_note": "visually verified marker-to-defect correspondence",
            "marker_source": "blue_marker",
            "label_confidence": "preliminary_verified",
            "review_status": "pending_preview_confirmation",
            "notes": "test",
        },
        {
            "image_id": "synthetic",
            "source_image": "synthetic.jpg",
            "marked_image": "syntheticm.jpg",
            "spot_id": "synthetic_spot_003",
            "x_center": 50,
            "y_center": 60,
            "radius": 50,
            "component_area": 50,
            "enclosing_circle_radius": 80,
            "quality_score": 95,
            "pass_fail_status": "PASS",
            "manually_verified_alignment": "true",
            "alignment_note": "visually verified marker-to-defect correspondence",
            "marker_source": "blue_marker",
            "label_confidence": "preliminary_verified",
            "review_status": "pending_preview_confirmation",
            "notes": "test",
        },
    ]


def write_fixture(input_dir: Path, manifest_rows: list[dict[str, object]] | None = None) -> None:
    manifest_rows = manifest_rows or base_manifest_rows()
    write_csv(input_dir / "ground_truth_manifest.csv", MANIFEST_COLUMNS, manifest_rows)
    write_csv(
        input_dir / "image_quality_summary.csv",
        IMAGE_COLUMNS,
        [
            {
                "image_id": "synthetic",
                "source_image": "synthetic.jpg",
                "marked_image": "syntheticm.jpg",
                "dirty_spot_count": len(manifest_rows),
                "quality_score": 95,
                "pass_fail_status": "PASS",
                "manually_verified_alignment": "true",
                "alignment_note": "visually verified marker-to-defect correspondence",
                "preview_path": "previews/synthetic.jpg",
                "review_status": "pending_preview_confirmation",
                "notes": "test",
            }
        ],
    )
    write_csv(input_dir / "review_queue.csv", REVIEW_COLUMNS, [])
    (input_dir / "generation_summary.json").write_text(
        '{"total_dirty_spots": %d, "automatic_merge_enabled": false}' % len(manifest_rows),
        encoding="utf-8",
    )


class FinalizeGroundTruthTests(unittest.TestCase):
    def test_raw_radius_preservation_and_preview_clamp(self) -> None:
        self.assertEqual(clamp_preview_radius(8), 16)
        self.assertEqual(clamp_preview_radius(30), 30)
        self.assertEqual(clamp_preview_radius(80), 50)

    def test_finalization_migrates_radius_and_statuses(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            temp_path = Path(temp_root)
            input_dir = temp_path / "input"
            output_dir = temp_path / "out"
            input_dir.mkdir()
            write_fixture(input_dir)

            summary = finalize_ground_truth(input_dir, output_dir, True, run_id="test_run")

            self.assertEqual(summary["final_manifest_rows"], 3)
            with (output_dir / "final_ground_truth_manifest.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["preliminary_preview_radius"], "16")
            self.assertEqual(float(rows[0]["radius"]), 8)
            self.assertEqual(float(rows[0]["preview_radius"]), 16)
            self.assertEqual(float(rows[1]["radius"]), 30)
            self.assertEqual(float(rows[1]["preview_radius"]), 30)
            self.assertEqual(float(rows[2]["radius"]), 80)
            self.assertEqual(float(rows[2]["preview_radius"]), 50)
            for row in rows:
                self.assertEqual(row["label_confidence"], "human_verified_ground_truth")
                self.assertEqual(row["review_status"], "final_confirmed")
                self.assertEqual(row["ground_truth_stage"], "final")
                self.assertEqual(float(row["radius"]), float(row["enclosing_circle_radius"]))
                self.assertEqual(row["quality_score"], "95")
                self.assertEqual(row["pass_fail_status"], "PASS")

    def test_duplicate_label_key_fails_safely(self) -> None:
        rows = base_manifest_rows()
        rows[1]["spot_id"] = rows[0]["spot_id"]
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            temp_path = Path(temp_root)
            input_dir = temp_path / "input"
            output_dir = temp_path / "out"
            input_dir.mkdir()
            write_fixture(input_dir, rows)

            with self.assertRaises(FinalizationError):
                finalize_ground_truth(input_dir, output_dir, True)
            self.assertFalse((output_dir / "final_ground_truth_manifest.csv").exists())

    def test_invalid_raw_radius_fails_without_partial_output(self) -> None:
        rows = base_manifest_rows()
        rows[0]["enclosing_circle_radius"] = "bad"
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            temp_path = Path(temp_root)
            input_dir = temp_path / "input"
            output_dir = temp_path / "out"
            input_dir.mkdir()
            write_fixture(input_dir, rows)

            with self.assertRaises(FinalizationError):
                finalize_ground_truth(input_dir, output_dir, True)
            self.assertFalse((output_dir / "final_ground_truth_manifest.csv").exists())

    def test_input_files_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            temp_path = Path(temp_root)
            input_dir = temp_path / "input"
            output_dir = temp_path / "out"
            input_dir.mkdir()
            write_fixture(input_dir)
            before = (input_dir / "ground_truth_manifest.csv").read_text(encoding="utf-8")

            finalize_ground_truth(input_dir, output_dir, True)

            after = (input_dir / "ground_truth_manifest.csv").read_text(encoding="utf-8")
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
