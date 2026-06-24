from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_source_level_split import (
    SplitError,
    build_assignments,
    build_source_level_split,
    validate_final_ground_truth,
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
    "preliminary_preview_radius",
    "preview_radius",
    "ground_truth_stage",
    "finalization_run_id",
    "finalized_at",
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
    "ground_truth_status",
    "preview_confirmation",
    "finalization_run_id",
    "finalized_at",
]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def make_rows(statuses: dict[str, str] | None = None) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    statuses = statuses or {str(i): ("FAIL" if i in {2, 3, 11, 12} else "PASS") for i in range(1, 16)}
    counts = {"PASS": 2, "FAIL": 3, "REVIEW": 1}
    scores = {"PASS": 95, "FAIL": 70, "REVIEW": 95}
    manifest_rows: list[dict[str, object]] = []
    image_rows: list[dict[str, object]] = []
    for image_id in sorted(statuses, key=lambda value: int(value)):
        status = statuses[image_id]
        count = counts[status]
        score = scores[status]
        image_rows.append(
            {
                "image_id": image_id,
                "source_image": f"{image_id}.jpg",
                "marked_image": f"{image_id}m.jpg",
                "dirty_spot_count": count,
                "quality_score": score,
                "pass_fail_status": status,
                "manually_verified_alignment": "true",
                "alignment_note": "verified",
                "preview_path": "",
                "review_status": "final_confirmed",
                "notes": "",
                "ground_truth_status": "final_confirmed",
                "preview_confirmation": "true",
                "finalization_run_id": "test",
                "finalized_at": "2026-06-24T00:00:00",
            }
        )
        for index in range(count):
            manifest_rows.append(
                {
                    "image_id": image_id,
                    "source_image": f"{image_id}.jpg",
                    "marked_image": f"{image_id}m.jpg",
                    "spot_id": f"{image_id}_spot_{index + 1:03d}",
                    "x_center": 10 + index,
                    "y_center": 20 + index,
                    "radius": 12,
                    "component_area": 40,
                    "enclosing_circle_radius": 12,
                    "quality_score": score,
                    "pass_fail_status": status,
                    "manually_verified_alignment": "true",
                    "alignment_note": "verified",
                    "marker_source": "blue_marker",
                    "label_confidence": "human_verified_ground_truth",
                    "review_status": "final_confirmed",
                    "notes": "",
                    "preliminary_preview_radius": 16,
                    "preview_radius": 16,
                    "ground_truth_stage": "final",
                    "finalization_run_id": "test",
                    "finalized_at": "2026-06-24T00:00:00",
                }
            )
    return manifest_rows, image_rows


def write_fixture(root: Path, manifest_rows: list[dict[str, object]] | None = None, image_rows: list[dict[str, object]] | None = None) -> None:
    manifest_rows = manifest_rows if manifest_rows is not None else make_rows()[0]
    image_rows = image_rows if image_rows is not None else make_rows()[1]
    write_csv(root / "final_ground_truth_manifest.csv", MANIFEST_COLUMNS, manifest_rows)
    write_csv(root / "final_image_quality_summary.csv", IMAGE_COLUMNS, image_rows)
    (root / "finalization_summary.json").write_text(
        '{"total_dirty_spots": %d}' % len(manifest_rows),
        encoding="utf-8",
    )
    (root / "finalization_report.md").write_text("report", encoding="utf-8")


class SourceLevelSplitTests(unittest.TestCase):
    def test_expected_current_allocation(self) -> None:
        manifest_rows, image_rows = make_rows()
        records = validate_final_ground_truth(MANIFEST_COLUMNS, manifest_rows, image_rows, {"total_dirty_spots": len(manifest_rows)})
        assignments = build_assignments(records, 20260624)

        self.assertEqual(sum(1 for split in assignments.values() if split == "train"), 12)
        self.assertEqual(sum(1 for split in assignments.values() if split == "validation"), 1)
        self.assertEqual(sum(1 for split in assignments.values() if split == "test"), 2)
        by_id = {record.image_id: record for record in records}
        self.assertEqual(sum(1 for image_id, split in assignments.items() if split == "train" and by_id[image_id].pass_fail_status == "PASS"), 9)
        self.assertEqual(sum(1 for image_id, split in assignments.items() if split == "train" and by_id[image_id].pass_fail_status == "FAIL"), 3)
        self.assertEqual(sum(1 for image_id, split in assignments.items() if split == "validation" and by_id[image_id].pass_fail_status == "PASS"), 1)
        self.assertEqual(sum(1 for image_id, split in assignments.items() if split == "test" and by_id[image_id].pass_fail_status == "PASS"), 1)
        self.assertEqual(sum(1 for image_id, split in assignments.items() if split == "test" and by_id[image_id].pass_fail_status == "FAIL"), 1)

    def test_leakage_prevention_and_determinism(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            input_dir = root / "input"
            out_a = root / "out_a"
            out_b = root / "out_b"
            input_dir.mkdir()
            write_fixture(input_dir)

            first = build_source_level_split(input_dir, out_a, 20260624, enforce_empty_output=False)
            second = build_source_level_split(input_dir, out_b, 20260624, enforce_empty_output=False)

            self.assertEqual(first["train_source_count"], 12)
            self.assertEqual(first["validation_source_count"], 1)
            self.assertEqual(first["test_source_count"], 2)
            with (out_a / "final_ground_truth_with_split.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            split_by_image: dict[str, set[str]] = {}
            for row in rows:
                split_by_image.setdefault(row["image_id"], set()).add(row["dataset_split"])
            self.assertTrue(all(len(splits) == 1 for splits in split_by_image.values()))
            self.assertEqual(
                (out_a / "source_split_manifest.csv").read_text(encoding="utf-8"),
                (out_b / "source_split_manifest.csv").read_text(encoding="utf-8"),
            )
            self.assertEqual(second["source_image_count"], 15)

    def test_different_seed_preserves_counts(self) -> None:
        manifest_rows, image_rows = make_rows()
        records = validate_final_ground_truth(MANIFEST_COLUMNS, manifest_rows, image_rows, {"total_dirty_spots": len(manifest_rows)})
        assignments = build_assignments(records, 123)

        self.assertEqual(sum(1 for split in assignments.values() if split == "train"), 12)
        self.assertEqual(sum(1 for split in assignments.values() if split == "validation"), 1)
        self.assertEqual(sum(1 for split in assignments.values() if split == "test"), 2)

    def test_input_mismatch_fails_safely(self) -> None:
        statuses = {str(i): ("FAIL" if i in {2, 3, 11, 12} else "PASS") for i in range(1, 15)}
        manifest_rows, image_rows = make_rows(statuses)
        with self.assertRaises(SplitError):
            validate_final_ground_truth(MANIFEST_COLUMNS, manifest_rows, image_rows, {"total_dirty_spots": len(manifest_rows)})

        statuses = {str(i): ("FAIL" if i in {2, 3, 11} else "PASS") for i in range(1, 16)}
        manifest_rows, image_rows = make_rows(statuses)
        with self.assertRaises(SplitError):
            validate_final_ground_truth(MANIFEST_COLUMNS, manifest_rows, image_rows, {"total_dirty_spots": len(manifest_rows)})

        statuses = {str(i): ("REVIEW" if i == 1 else ("FAIL" if i in {2, 3, 11, 12} else "PASS")) for i in range(1, 16)}
        manifest_rows, image_rows = make_rows(statuses)
        with self.assertRaises(SplitError):
            validate_final_ground_truth(MANIFEST_COLUMNS, manifest_rows, image_rows, {"total_dirty_spots": len(manifest_rows)})

    def test_final_ground_truth_validation_failures(self) -> None:
        manifest_rows, image_rows = make_rows()
        manifest_rows[0]["review_status"] = "pending"
        with self.assertRaises(SplitError):
            validate_final_ground_truth(MANIFEST_COLUMNS, manifest_rows, image_rows, {"total_dirty_spots": len(manifest_rows)})

        manifest_rows, image_rows = make_rows()
        manifest_rows[0]["label_confidence"] = "preliminary"
        with self.assertRaises(SplitError):
            validate_final_ground_truth(MANIFEST_COLUMNS, manifest_rows, image_rows, {"total_dirty_spots": len(manifest_rows)})

        manifest_rows, image_rows = make_rows()
        manifest_rows[1]["spot_id"] = manifest_rows[0]["spot_id"]
        with self.assertRaises(SplitError):
            validate_final_ground_truth(MANIFEST_COLUMNS, manifest_rows, image_rows, {"total_dirty_spots": len(manifest_rows)})

    def test_input_immutability(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            input_dir = root / "input"
            output_dir = root / "out"
            input_dir.mkdir()
            write_fixture(input_dir)
            before = (input_dir / "final_ground_truth_manifest.csv").read_text(encoding="utf-8")

            build_source_level_split(input_dir, output_dir, 20260624, enforce_empty_output=False)

            after = (input_dir / "final_ground_truth_manifest.csv").read_text(encoding="utf-8")
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
