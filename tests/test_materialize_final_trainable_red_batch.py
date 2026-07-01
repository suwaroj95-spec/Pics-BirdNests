from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import materialize_final_trainable_red_batch as finalizer


def write_image(path: Path, value: int) -> None:
    image = np.full((10, 10, 3), value, dtype=np.uint8)
    if not cv2.imwrite(str(path), image):
        raise AssertionError(f"Could not write {path}")


class FinalTrainableRedBatchTests(unittest.TestCase):
    def test_exact_10_pairs_are_quarantined_and_absent_from_final_plan(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            final_rows, quarantine_rows, _ = self._build(Path(tmp))
            quarantined = {int(row["original_pair_sequence"]) for row in quarantine_rows}
            final_pairs = {int(row["original_pair_sequence"]) for row in final_rows}

            self.assertEqual(set(finalizer.APPROVED_QUARANTINE), quarantined)
            self.assertFalse(quarantined & final_pairs)

    def test_pair_17_preferred_reference_position_33_is_recorded_only_in_quarantine(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            final_rows, quarantine_rows, _ = self._build(Path(tmp))
            pair_17 = [row for row in quarantine_rows if row["original_pair_sequence"] == "17"]

            self.assertEqual(["33", "34"], [row["original_sorted_position"] for row in pair_17])
            self.assertEqual(["true", "false"], [row["preferred_reference"] for row in pair_17])
            self.assertTrue(all(row["training_eligible"] == "false" for row in pair_17))
            self.assertNotIn("17", {row["original_pair_sequence"] for row in final_rows})

    def test_pair_95_is_included_and_roles_are_swapped_once(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            final_rows, _, _ = self._build(Path(tmp))
            pair_95 = [row for row in final_rows if row["original_pair_sequence"] == "95"]

            by_position = {row["original_sorted_position"]: row for row in pair_95}
            self.assertEqual("raw", by_position["189"]["final_role"])
            self.assertEqual("marker", by_position["190"]["final_role"])
            self.assertEqual("", by_position["189"]["final_marker_color"])
            self.assertEqual("red", by_position["190"]["final_marker_color"])

    def test_other_included_pairs_preserve_roles_and_original_order_without_repairing(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            final_rows, _, _ = self._build(Path(tmp))
            pair_18 = [row for row in final_rows if row["original_pair_sequence"] == "18"]
            original_pairs = []
            for row in final_rows[::2]:
                original_pairs.append(int(row["original_pair_sequence"]))

            self.assertEqual(["marker", "raw"], [row["final_role"] for row in pair_18])
            self.assertEqual([1, 2, 3], original_pairs[:3])
            self.assertEqual(18, original_pairs[16])

    def test_final_counts_ids_and_pair_roles_are_valid(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            final_rows, _, summary = self._build(Path(tmp))
            ids = sorted({int(row["final_target_id"]) for row in final_rows})

            self.assertEqual(174, summary["final_training_pair_count"])
            self.assertEqual(348, summary["final_training_file_count"])
            self.assertEqual(list(range(16, 190)), ids)
            for final_pair in range(1, 175):
                rows = [row for row in final_rows if row["final_pair_sequence"] == str(final_pair)]
                self.assertEqual(["marker", "raw"], sorted(row["final_role"] for row in rows))
                self.assertNotEqual(rows[0]["source_sha256"], rows[1]["source_sha256"])

    def test_source_file_reuse_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, resolution, input_dir, output = self._fixture(base)
            rows = self._read_csv(plan)
            rows[2]["source_path"] = rows[0]["source_path"]
            rows[2]["source_sha256"] = rows[0]["source_sha256"]
            self._write_csv(plan, finalizer.PLAN_REQUIRED, rows)

            with self.assertRaises(finalizer.FinalBatchError):
                finalizer.build_preflight(plan, input_dir, resolution, output, 16)

    def test_source_hash_mismatch_blocks_preflight(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, resolution, input_dir, output = self._fixture(base)
            write_image(input_dir / "pair_001_marker.jpg", 3)

            with self.assertRaises(finalizer.FinalBatchError):
                finalizer.build_preflight(plan, input_dir, resolution, output, 16)

    def test_preflight_changes_no_source_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, resolution, input_dir, output = self._fixture(base)
            before = self._hashes(input_dir)
            finalizer.build_preflight(plan, input_dir, resolution, output, 16)

            self.assertEqual(before, self._hashes(input_dir))

    def test_apply_without_apply_changes_nothing(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan_csv, output, input_dir = self._preflight_files(base)
            before = self._hashes(input_dir)

            with self.assertRaises(finalizer.FinalBatchError):
                finalizer.apply_plan(plan_csv, output, False)
            self.assertFalse(output.exists())
            self.assertEqual(before, self._hashes(input_dir))

    def test_apply_preserves_source_bytes_and_output_sha256(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan_csv, output, _ = self._preflight_files(base)
            finalizer.apply_plan(plan_csv, output, True)
            manifest = self._read_csv(output / "final_training_manifest.csv")

            self.assertEqual(348, len([path for path in output.iterdir() if path.suffix == ".jpg"]))
            self.assertTrue(all(row["source_sha256"] == row["output_sha256"] for row in manifest))

    def test_non_empty_output_dir_and_forbidden_locations_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan_csv, output, input_dir = self._preflight_files(base)
            output.mkdir()
            (output / "busy.txt").write_text("busy", encoding="utf-8")

            with self.assertRaises(finalizer.FinalBatchError):
                finalizer.apply_plan(plan_csv, output, True)
            with self.assertRaises(finalizer.FinalBatchError):
                finalizer.build_preflight(plan_csv, input_dir, base / "resolution.csv", ROOT / "RawPics", 16)
            with self.assertRaises(finalizer.FinalBatchError):
                finalizer.apply_plan(plan_csv, input_dir, True)

    def test_windows_finalization_retry_is_bounded_and_retrying(self) -> None:
        with mock.patch.object(Path, "rename", side_effect=[PermissionError("busy"), None]) as rename:
            finalizer.finalize_staging_dir(Path("staging"), Path("output"))

        self.assertEqual(2, rename.call_count)

    def test_v2_target_ids_map_through_v1_plan_and_pair_95_is_quarantined(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, _resolution, input_dir, output = self._fixture(base)
            v2_resolution = self._write_v2_resolution(base)
            v1_plan = self._write_synthetic_v1_final_plan(base)
            mapping = finalizer.map_v1_targets_to_original_pairs(v1_plan, [96, 101, 103])

            final_rows, quarantine_rows, summary = finalizer.build_preflight(
                plan, input_dir, v2_resolution, output, 16, 184, 13, 171, 342, v1_plan
            )

            self.assertEqual({96: (85, 100), 101: (93, 108), 103: (95, 110)}, mapping)
            self.assertEqual(13, summary["quarantined_pair_count"])
            self.assertEqual([], summary["role_swap_pair_sequences"])
            self.assertNotIn("95", {row["original_pair_sequence"] for row in final_rows})
            self.assertIn("95", {row["original_pair_sequence"] for row in quarantine_rows})

    def test_v2_counts_ids_order_no_quarantine_sources_and_apply_copy(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, _resolution, input_dir, output = self._fixture(base)
            v2_resolution = self._write_v2_resolution(base)
            v1_plan = self._write_synthetic_v1_final_plan(base)
            v1_before = self._hashes(input_dir)
            final_rows, quarantine_rows, summary = finalizer.build_preflight(
                plan, input_dir, v2_resolution, output, 16, 184, 13, 171, 342, v1_plan
            )
            preflight = finalizer.write_preflight(final_rows, quarantine_rows, summary, "v2")
            plan_csv = preflight / "final_training_plan_v2.csv"
            with self.assertRaises(finalizer.FinalBatchError):
                finalizer.apply_plan(plan_csv, output, False)
            finalizer.apply_plan(plan_csv, output, True)
            manifest = self._read_csv(output / "final_training_manifest_v2.csv")
            quarantined_sources = {row["source_filename"] for row in quarantine_rows}
            ids = sorted({int(row["final_target_id"]) for row in manifest})
            original_pairs = [int(row["original_pair_sequence"]) for row in final_rows[::2]]

            self.assertEqual(171, summary["final_training_pair_count"])
            self.assertEqual(342, summary["final_training_file_count"])
            self.assertEqual(list(range(16, 187)), ids)
            self.assertEqual(sorted(original_pairs), original_pairs)
            self.assertFalse(quarantined_sources & {row["source_filename"] for row in manifest})
            self.assertTrue(all(row["source_sha256"] == row["output_sha256"] for row in manifest))
            self.assertEqual(v1_before, self._hashes(input_dir))

    def _build(self, base: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, object]]:
        plan, resolution, input_dir, output = self._fixture(base)
        return finalizer.build_preflight(
            plan,
            input_dir,
            resolution,
            output,
            16,
            expected_source_pairs=184,
            expected_quarantined_pairs=10,
            expected_final_pairs=174,
            expected_final_files=348,
        )

    def _preflight_files(self, base: Path) -> tuple[Path, Path, Path]:
        plan, resolution, input_dir, output = self._fixture(base)
        final_rows, quarantine_rows, summary = finalizer.build_preflight(plan, input_dir, resolution, output, 16, 184, 10, 174, 348)
        preflight = finalizer.write_preflight(final_rows, quarantine_rows, summary)
        return preflight / "final_training_plan.csv", output, input_dir

    def _fixture(self, base: Path) -> tuple[Path, Path, Path, Path]:
        input_dir = base / "input"
        input_dir.mkdir()
        rows: list[dict[str, str]] = []
        for pair in range(1, 185):
            target_id = 15 + pair
            marker = input_dir / f"pair_{pair:03d}_marker.jpg"
            raw = input_dir / f"pair_{pair:03d}_raw.jpg"
            write_image(marker, (pair % 220) + 20)
            write_image(raw, (pair % 220) + 21)
            if pair in {100, 101, 102}:
                raw.write_bytes(marker.read_bytes())
            roles = [("marker", marker), ("raw", raw)]
            if pair == 17:
                roles = [("marker", marker), ("marker", raw)]
            for offset, (role, path) in enumerate(roles, start=1):
                rows.append(self._plan_row(pair, target_id, ((pair - 1) * 2) + offset, role, path))
        plan = base / "rename_plan.csv"
        self._write_csv(plan, finalizer.PLAN_REQUIRED, rows)
        resolution = base / "resolution.csv"
        shutil_source = ROOT / "docs" / "final_training_resolution_20260701.csv"
        resolution.write_bytes(shutil_source.read_bytes())
        return plan, resolution, input_dir, base / "out"

    def _write_v2_resolution(self, base: Path) -> Path:
        resolution = base / "resolution_v2.csv"
        resolution.write_bytes((ROOT / "docs" / "final_training_resolution_20260701_v2.csv").read_bytes())
        return resolution

    def _write_synthetic_v1_final_plan(self, base: Path) -> Path:
        plan = base / "v1_final_plan.csv"
        rows = [
            {"final_target_id": "96", "original_pair_sequence": "85", "original_target_id": "100"},
            {"final_target_id": "96", "original_pair_sequence": "85", "original_target_id": "100"},
            {"final_target_id": "101", "original_pair_sequence": "93", "original_target_id": "108"},
            {"final_target_id": "101", "original_pair_sequence": "93", "original_target_id": "108"},
            {"final_target_id": "103", "original_pair_sequence": "95", "original_target_id": "110"},
            {"final_target_id": "103", "original_pair_sequence": "95", "original_target_id": "110"},
        ]
        self._write_csv(plan, ["final_target_id", "original_pair_sequence", "original_target_id"], rows)
        return plan

    def _plan_row(self, pair: int, target_id: int, sorted_position: int, role: str, path: Path) -> dict[str, str]:
        readable, width, height = finalizer.read_image_size(path)
        self.assertTrue(readable)
        return {
            "sorted_position": str(sorted_position),
            "pair_sequence": str(pair),
            "source_filename": path.name,
            "source_path": str(path),
            "source_sha256": finalizer.sha256_file(path),
            "width": str(width),
            "height": str(height),
            "role_proposed": role,
            "marker_color": "red" if role == "marker" else "",
            "target_id": str(target_id),
        }

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        with path.open("r", newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def _write_csv(self, path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def _hashes(self, input_dir: Path) -> dict[str, str]:
        return {path.name: finalizer.sha256_file(path) for path in input_dir.iterdir()}


if __name__ == "__main__":
    unittest.main()
