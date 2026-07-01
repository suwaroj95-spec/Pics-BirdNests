from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import preflight_red_marker_batch as preflight


def write_image(
    path: Path,
    red_components: list[tuple[int, int, int]] | None = None,
    size: tuple[int, int] = (24, 24),
    value: int = 230,
) -> None:
    image = np.full((size[1], size[0], 3), value, dtype=np.uint8)
    for x, y, radius in red_components or []:
        cv2.circle(image, (x, y), radius, (0, 0, 255), thickness=-1)
    if not cv2.imwrite(str(path), image):
        raise AssertionError(f"Could not write {path}")


class RedMarkerPreflightTests(unittest.TestCase):
    def test_valid_red_pair_is_safe(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            batch = self._batch(Path(tmp))
            output = preflight.run_preflight(batch)
            row = self._row(output, 16)

            self.assertEqual("SAFE_MARKER_PAIR", row["validation_status"])

    def test_marker_components_smaller_than_20_are_not_counted(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            batch = self._batch(Path(tmp))
            write_image(batch / "16m.jpg", [(8, 8, 1)])
            output = preflight.run_preflight(batch)
            row = self._row(output, 16)

            self.assertEqual("WEAK_RED_MARKER", row["validation_status"])
            self.assertEqual("0", row["eligible_component_count"])

    def test_no_red_marker_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            batch = self._batch(Path(tmp))
            write_image(batch / "16m.jpg", value=210)
            output = preflight.run_preflight(batch)

            self.assertEqual("NO_RED_MARKER", self._row(output, 16)["validation_status"])

    def test_matching_dimensions_are_required(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            batch = self._batch(Path(tmp))
            write_image(batch / "16m.jpg", [(8, 8, 3)], size=(26, 24))
            output = preflight.run_preflight(batch)

            self.assertEqual("DIMENSION_MISMATCH", self._row(output, 16)["validation_status"])

    def test_same_sha256_inside_pair_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            batch = self._batch(Path(tmp))
            (batch / "16m.jpg").write_bytes((batch / "16.jpg").read_bytes())
            output = preflight.run_preflight(batch)

            self.assertEqual("PAIR_STRUCTURE_ERROR", self._row(output, 16)["validation_status"])

    def test_no_source_image_is_modified(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            batch = self._batch(Path(tmp))
            before = {path.name: preflight.sha256_file(path) for path in batch.iterdir()}
            preflight.run_preflight(batch)

            self.assertEqual(before, {path.name: preflight.sha256_file(path) for path in batch.iterdir()})

    def test_expected_174_pairs_and_348_files_fixture_validates(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            batch = self._batch(Path(tmp))
            output = preflight.run_preflight(batch)
            summary = json.loads((output / "red_marker_preflight_summary.json").read_text(encoding="utf-8"))

            self.assertEqual(174, summary["total_pair_count"])
            self.assertEqual(348, summary["total_image_file_count"])
            self.assertEqual(174, summary["safe_pair_count"])
            self.assertEqual(0, summary["exception_count"])
            self.assertTrue(summary["safe_to_proceed_to_red_ground_truth"])

    def test_approved_raw_sha_with_composite_key_is_approved(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            batch = self._batch(base)
            write_image(batch / "16.jpg", [(8, 8, 3)], value=210)
            self._write_manifest(batch, "16.jpg", "source_a.jpg", "1")
            resolution = self._write_resolution(base, [(preflight.sha256_file(batch / "16.jpg"), "source_a.jpg", "1", "16")])

            output = preflight.run_preflight(batch, review_resolution_csv=resolution)

            self.assertEqual("APPROVED_RAW_RED_CONTENT", self._row(output, 16)["validation_status"])
            self.assertEqual(0, len(list((output / "review_pairs").iterdir())))

    def test_same_sha_wrong_source_filename_or_pair_is_not_approved(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            batch = self._batch(base)
            write_image(batch / "16.jpg", [(8, 8, 3)], value=210)
            self._write_manifest(batch, "16.jpg", "source_a.jpg", "1")
            resolution = self._write_resolution(base, [(preflight.sha256_file(batch / "16.jpg"), "source_b.jpg", "1", "16")])
            output = preflight.run_preflight(batch, base / "out1", review_resolution_csv=resolution)
            self.assertEqual("RAW_RED_ANOMALY", self._row(output, 16)["validation_status"])

            resolution = self._write_resolution(base, [(preflight.sha256_file(batch / "16.jpg"), "source_a.jpg", "2", "16")])
            output = preflight.run_preflight(batch, base / "out2", review_resolution_csv=resolution)
            self.assertEqual("RAW_RED_ANOMALY", self._row(output, 16)["validation_status"])

    def test_two_approved_rows_may_share_sha_when_composite_key_differs(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            batch = self._batch(base)
            write_image(batch / "16.jpg", [(8, 8, 3)], value=210)
            (batch / "17.jpg").write_bytes((batch / "16.jpg").read_bytes())
            self._write_manifest(batch, "16.jpg", "source_a.jpg", "1", extra=[("17.jpg", "source_b.jpg", "2")])
            shared_sha = preflight.sha256_file(batch / "16.jpg")
            resolution = self._write_resolution(base, [(shared_sha, "source_a.jpg", "1", "16"), (shared_sha, "source_b.jpg", "2", "17")])

            output = preflight.run_preflight(batch, review_resolution_csv=resolution)

            self.assertEqual("APPROVED_RAW_RED_CONTENT", self._row(output, 16)["validation_status"])
            self.assertEqual("APPROVED_RAW_RED_CONTENT", self._row(output, 17)["validation_status"])

    def test_duplicate_composite_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            resolution = self._write_resolution(base, [("a" * 64, "source.jpg", "1", "16"), ("a" * 64, "source.jpg", "1", "17")])

            with self.assertRaises(preflight.RedMarkerPreflightError):
                preflight.load_review_resolution(resolution)

    def test_v2_resolution_csv_has_13_rows_and_excludes_removed_v1_ids(self) -> None:
        path = ROOT / "docs" / "red_marker_preflight_review_resolution_20260701_v2.csv"
        with path.open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(13, len(rows))
        self.assertFalse({"96", "101", "103"} & {row["previous_v1_target_id"] for row in rows})

    def _batch(self, base: Path) -> Path:
        batch = base / "batch"
        batch.mkdir()
        for image_id in range(16, 190):
            write_image(batch / f"{image_id}.jpg")
            write_image(batch / f"{image_id}m.jpg", [(8, 8, 3)])
        return batch

    def _write_manifest(
        self,
        batch: Path,
        output_filename: str,
        source_filename: str,
        original_pair_sequence: str,
        extra: list[tuple[str, str, str]] | None = None,
    ) -> None:
        rows = [
            {
                "output_filename": output_filename,
                "source_filename": source_filename,
                "source_sha256": preflight.sha256_file(batch / output_filename),
                "original_pair_sequence": original_pair_sequence,
            }
        ]
        for output, source, pair in extra or []:
            rows.append(
                {
                    "output_filename": output,
                    "source_filename": source,
                    "source_sha256": preflight.sha256_file(batch / output),
                    "original_pair_sequence": pair,
                }
            )
        with (batch / "final_training_manifest_v2.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["output_filename", "source_filename", "source_sha256", "original_pair_sequence"])
            writer.writeheader()
            writer.writerows(rows)

    def _write_resolution(self, base: Path, rows: list[tuple[str, str, str, str]]) -> Path:
        path = base / f"resolution_{len(list(base.glob('resolution_*.csv')))}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=preflight.REVIEW_FIELDS)
            writer.writeheader()
            for sha, source, pair, previous_id in rows:
                writer.writerow(
                    {
                        "raw_source_sha256": sha,
                        "source_filename": source,
                        "previous_v1_target_id": previous_id,
                        "final_v2_target_id": previous_id,
                        "original_pair_sequence": pair,
                        "decision": "APPROVED_RAW_RED_CONTENT",
                        "reason": "manually_reviewed_legitimate_red_content_in_raw_image",
                        "review_status": "APPROVED",
                    }
                )
        return path

    def _row(self, output: Path, image_id: int) -> dict[str, str]:
        csv_path = output / "red_marker_preflight_v2.csv"
        if not csv_path.exists():
            csv_path = output / "red_marker_preflight.csv"
        with csv_path.open("r", newline="", encoding="utf-8") as handle:
            rows = {int(row["id"]): row for row in csv.DictReader(handle)}
        return rows[image_id]


if __name__ == "__main__":
    unittest.main()
