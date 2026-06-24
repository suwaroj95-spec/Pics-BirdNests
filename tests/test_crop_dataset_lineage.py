from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.audit_crop_dataset_lineage import audit_crop_lineage


CROP_COLUMNS = [
    "source_id",
    "source_image",
    "marked_image",
    "output_file",
    "label",
    "dirty_spot_id",
]

SPLIT_COLUMNS = [
    "image_id",
    "source_image",
    "marked_image",
    "dataset_split",
    "stratification_group",
    "dirty_spot_count",
    "quality_score",
    "pass_fail_status",
    "ground_truth_status",
    "split_seed",
    "split_policy_version",
    "notes",
]

FINAL_COLUMNS = [
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
    "ground_truth_stage",
    "dataset_split",
]

IMAGE_COLUMNS = [
    "image_id",
    "source_image",
    "marked_image",
    "dirty_spot_count",
    "quality_score",
    "pass_fail_status",
    "ground_truth_status",
]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
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


def write_fixture(root: Path, crops: list[dict[str, object]] | None = None) -> tuple[Path, Path, Path]:
    crops_dir = root / "Crops"
    split_dir = root / "split"
    final_dir = root / "final"
    crops_dir.mkdir()
    split_dir.mkdir()
    final_dir.mkdir()
    crops = crops or [
        {"source_id": "1", "source_image": "1.jpg", "marked_image": "1m.jpg", "output_file": "clean/c1.jpg", "label": "clean_negative", "dirty_spot_id": ""},
        {"source_id": "1", "source_image": "1.jpg", "marked_image": "1m.jpg", "output_file": "dirty/d1.jpg", "label": "dirty_positive", "dirty_spot_id": "1"},
        {"source_id": "2", "source_image": "2.jpg", "marked_image": "2m.jpg", "output_file": "dirty/d2.jpg", "label": "dirty_positive", "dirty_spot_id": "1"},
    ]
    write_csv(crops_dir / "metadata.csv", CROP_COLUMNS, crops)
    write_csv(
        split_dir / "source_split_manifest.csv",
        SPLIT_COLUMNS,
        [
            {"image_id": "1", "source_image": "1.jpg", "marked_image": "1m.jpg", "dataset_split": "train", "stratification_group": "PASS", "dirty_spot_count": 1, "quality_score": 95, "pass_fail_status": "PASS", "ground_truth_status": "final_confirmed", "split_seed": 1, "split_policy_version": "test", "notes": ""},
            {"image_id": "2", "source_image": "2.jpg", "marked_image": "2m.jpg", "dataset_split": "test", "stratification_group": "FAIL", "dirty_spot_count": 1, "quality_score": 70, "pass_fail_status": "FAIL", "ground_truth_status": "final_confirmed", "split_seed": 1, "split_policy_version": "test", "notes": ""},
        ],
    )
    final_rows = [
        {"image_id": "1", "source_image": "1.jpg", "marked_image": "1m.jpg", "spot_id": "1_spot_001", "x_center": 1, "y_center": 1, "radius": 1, "component_area": 1, "enclosing_circle_radius": 1, "quality_score": 95, "pass_fail_status": "PASS", "manually_verified_alignment": "true", "alignment_note": "", "marker_source": "blue_marker", "label_confidence": "human_verified_ground_truth", "review_status": "final_confirmed", "notes": "", "ground_truth_stage": "final", "dataset_split": "train"},
        {"image_id": "2", "source_image": "2.jpg", "marked_image": "2m.jpg", "spot_id": "2_spot_001", "x_center": 1, "y_center": 1, "radius": 1, "component_area": 1, "enclosing_circle_radius": 1, "quality_score": 70, "pass_fail_status": "FAIL", "manually_verified_alignment": "true", "alignment_note": "", "marker_source": "blue_marker", "label_confidence": "human_verified_ground_truth", "review_status": "final_confirmed", "notes": "", "ground_truth_stage": "final", "dataset_split": "test"},
    ]
    write_csv(final_dir / "final_ground_truth_manifest.csv", FINAL_COLUMNS, final_rows)
    write_csv(final_dir / "final_image_quality_summary.csv", IMAGE_COLUMNS, [
        {"image_id": "1", "source_image": "1.jpg", "marked_image": "1m.jpg", "dirty_spot_count": 1, "quality_score": 95, "pass_fail_status": "PASS", "ground_truth_status": "final_confirmed"},
        {"image_id": "2", "source_image": "2.jpg", "marked_image": "2m.jpg", "dirty_spot_count": 1, "quality_score": 70, "pass_fail_status": "FAIL", "ground_truth_status": "final_confirmed"},
    ])
    write_csv(split_dir / "final_ground_truth_with_split.csv", FINAL_COLUMNS, final_rows)
    (split_dir / "split_summary.json").write_text("{}", encoding="utf-8")
    return crops_dir, split_dir, final_dir


class CropDatasetLineageTests(unittest.TestCase):
    def test_crop_rows_map_to_source_level_split_and_no_leakage(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, split_dir, final_dir = write_fixture(root)
            out = root / "out"

            summary = audit_crop_lineage(crops_dir, split_dir, final_dir, out, enforce_empty_output=False)

            self.assertEqual(summary["crop_metadata_rows"], 3)
            self.assertEqual(summary["resolved_crop_rows"], 3)
            self.assertFalse(summary["leakage_detected"])
            with (out / "crop_lineage_manifest.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            splits = {row["output_file"]: row["dataset_split"] for row in rows}
            self.assertEqual(splits["clean/c1.jpg"], "train")
            self.assertEqual(splits["dirty/d2.jpg"], "test")
            self.assertEqual(len({row["dataset_split"] for row in rows if row["resolved_image_id"] == "1"}), 1)

    def test_unknown_image_id_and_missing_lineage_produces_insufficient_lineage(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops = [{"source_id": "99", "source_image": "99.jpg", "marked_image": "99m.jpg", "output_file": "x.jpg", "label": "clean_negative", "dirty_spot_id": ""}]
            crops_dir, split_dir, final_dir = write_fixture(root, crops)
            out = root / "out"

            summary = audit_crop_lineage(crops_dir, split_dir, final_dir, out, enforce_empty_output=False)

            self.assertEqual(summary["unresolved_crop_rows"], 1)
            self.assertEqual(summary["reuse_decision"], "INSUFFICIENT_LINEAGE")

    def test_duplicate_crop_path_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops = [
                {"source_id": "1", "source_image": "1.jpg", "marked_image": "1m.jpg", "output_file": "same.jpg", "label": "clean_negative", "dirty_spot_id": ""},
                {"source_id": "1", "source_image": "1.jpg", "marked_image": "1m.jpg", "output_file": "same.jpg", "label": "dirty_positive", "dirty_spot_id": "1"},
            ]
            crops_dir, split_dir, final_dir = write_fixture(root, crops)
            out = root / "out"

            summary = audit_crop_lineage(crops_dir, split_dir, final_dir, out, enforce_empty_output=False)

            self.assertEqual(summary["duplicate_crop_path_count"], 1)
            self.assertEqual(summary["reuse_decision"], "REUSE_WITH_SPLIT_MANIFEST_ONLY")

    def test_exact_spot_mapping_only_when_evidence_exists(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops = [
                {"source_id": "1", "source_image": "1.jpg", "marked_image": "1m.jpg", "output_file": "exact.jpg", "label": "dirty_positive", "dirty_spot_id": "1"},
                {"source_id": "1", "source_image": "1.jpg", "marked_image": "1m.jpg", "output_file": "source_only.jpg", "label": "dirty_positive", "dirty_spot_id": "9"},
            ]
            crops_dir, split_dir, final_dir = write_fixture(root, crops)
            out = root / "out"

            summary = audit_crop_lineage(crops_dir, split_dir, final_dir, out, enforce_empty_output=False)

            self.assertEqual(summary["exact_dirty_positive_traceability_count"], 1)
            self.assertEqual(summary["source_level_dirty_positive_traceability_count"], 1)

    def test_input_hashes_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, split_dir, final_dir = write_fixture(root)
            before = (crops_dir / "metadata.csv").read_text(encoding="utf-8")
            out = root / "out"

            audit_crop_lineage(crops_dir, split_dir, final_dir, out, enforce_empty_output=False)

            after = (crops_dir / "metadata.csv").read_text(encoding="utf-8")
            self.assertEqual(before, after)

    def test_output_hashes_cover_primary_csv_artifacts_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_root:
            root = Path(temp_root)
            crops_dir, split_dir, final_dir = write_fixture(root)
            out = root / "out"

            audit_crop_lineage(crops_dir, split_dir, final_dir, out, enforce_empty_output=False)

            summary = json.loads((out / "crop_reuse_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["output_hash_scope"], "primary_csv_artifacts_only")
            output_hashes = summary["output_file_hashes"]
            self.assertNotIn("crop_reuse_summary.json", output_hashes)
            for filename, expected_hash in output_hashes.items():
                artifact_path = out / filename
                self.assertTrue(artifact_path.exists(), filename)
                self.assertEqual(file_sha256(artifact_path), expected_hash, filename)


if __name__ == "__main__":
    unittest.main()
