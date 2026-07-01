from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import materialize_approved_reconciliation as materialize


def write_image(path: Path, value: int) -> None:
    image = np.full((8, 8, 3), value, dtype=np.uint8)
    if not cv2.imwrite(str(path), image):
        raise AssertionError(f"Could not write {path}")


class ApprovedReconciliationMaterializationTests(unittest.TestCase):
    def test_only_first_approved_duplicate_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            input_dir, audit_dir, output_dir = self._fixture(base)
            rows, _ = materialize.build_plan(input_dir, audit_dir, output_dir, 370, 368, 184)
            by_name = {row["source_filename"]: row for row in rows}

            self.assertEqual("EXCLUDE_APPROVED_EXACT_DUPLICATE", by_name["S__3956902_2.jpg"]["approved_action"])
            self.assertEqual("false", by_name["S__3956902_2.jpg"]["retained"])
            self.assertEqual("KEEP", by_name["S__3956902_0.jpg"]["approved_action"])
            self.assertEqual("KEEP", by_name["S__3956902_1.jpg"]["approved_action"])

    def test_only_second_approved_duplicate_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            input_dir, audit_dir, output_dir = self._fixture(base)
            rows, _ = materialize.build_plan(input_dir, audit_dir, output_dir, 370, 368, 184)
            by_name = {row["source_filename"]: row for row in rows}

            self.assertEqual("EXCLUDE_APPROVED_EXACT_DUPLICATE", by_name["S__10690658_1.jpg"]["approved_action"])
            self.assertEqual("false", by_name["S__10690658_1.jpg"]["retained"])
            self.assertEqual("KEEP", by_name["S__10690658_0.jpg"]["approved_action"])

    def test_mismatch_in_filename_position_sha_or_group_blocks_run(self) -> None:
        for field, value in [
            ("source_filename", "wrong.jpg"),
            ("original_sort_position", "31"),
            ("sha256", "0" * 64),
            ("duplicate_group_id", "DUP-9999"),
        ]:
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                    base = Path(tmp)
                    input_dir, audit_dir, output_dir = self._fixture(base)
                    self._mutate_audit(audit_dir, "S__3956902_2.jpg", field, value)
                    with self.assertRaises(materialize.MaterializationError):
                        materialize.build_plan(input_dir, audit_dir, output_dir, 370, 368, 184)

    def test_no_unique_sha256_file_can_be_excluded(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            input_dir, audit_dir, output_dir = self._fixture(base)
            self._mutate_audit(audit_dir, "S__3956902_2.jpg", "is_unique_sha256", "true")

            with self.assertRaises(materialize.MaterializationError):
                materialize.build_plan(input_dir, audit_dir, output_dir, 370, 368, 184)

    def test_retained_count_pair_count_and_future_id_range(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            input_dir, audit_dir, output_dir = self._fixture(base)
            _, summary = materialize.build_plan(input_dir, audit_dir, output_dir, 370, 368, 184)

            self.assertEqual(368, summary["retained_file_count"])
            self.assertEqual(184, summary["projected_adjacent_pair_count"])
            self.assertEqual(16, summary["future_start_id"])
            self.assertEqual(199, summary["future_end_id"])

    def test_preflight_changes_no_source_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            input_dir, audit_dir, output_dir = self._fixture(base)
            before = self._source_hashes(input_dir)
            rows, summary = materialize.build_plan(input_dir, audit_dir, output_dir, 370, 368, 184)
            materialize.write_preflight(rows, summary, base)
            after = self._source_hashes(input_dir)

            self.assertEqual(before, after)
            self.assertFalse(output_dir.exists())

    def test_apply_without_apply_changes_nothing(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan_csv, output_dir, input_dir = self._preflight(base)
            before = self._source_hashes(input_dir)

            with self.assertRaises(materialize.MaterializationError):
                materialize.apply_plan(plan_csv, output_dir, False)

            self.assertEqual(before, self._source_hashes(input_dir))
            self.assertFalse(output_dir.exists())

    def test_apply_preserves_source_bytes_and_sha256_for_retained_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan_csv, output_dir, input_dir = self._preflight(base)
            materialize.apply_plan(plan_csv, output_dir, True)

            output_files = [path for path in output_dir.iterdir() if path.suffix.casefold() == ".jpg"]
            self.assertEqual(368, len(output_files))
            with (output_dir / "approved_reconciliation_manifest.csv").open("r", newline="", encoding="utf-8") as handle:
                manifest = list(csv.DictReader(handle))
            self.assertEqual(368, len(manifest))
            for row in manifest:
                self.assertEqual(row["source_sha256"], row["output_sha256"])
                self.assertEqual((input_dir / row["source_filename"]).read_bytes(), (output_dir / row["output_filename"]).read_bytes())

    def test_non_empty_output_directory_blocks_apply_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan_csv, output_dir, _ = self._preflight(base)
            output_dir.mkdir()
            (output_dir / "collision.txt").write_text("stop", encoding="utf-8")

            with self.assertRaises(materialize.MaterializationError):
                materialize.apply_plan(plan_csv, output_dir, True)

            self.assertEqual(["collision.txt"], [path.name for path in output_dir.iterdir()])

    def test_rawpics_is_rejected_as_output_directory(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            input_dir, audit_dir, _ = self._fixture(base)
            with self.assertRaises(materialize.MaterializationError):
                materialize.build_plan(input_dir, audit_dir, ROOT / "RawPics", 370, 368, 184)

    def test_original_line_source_files_are_never_renamed_moved_or_deleted(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan_csv, output_dir, input_dir = self._preflight(base)
            before_names = sorted(path.name for path in input_dir.iterdir())
            before_hashes = self._source_hashes(input_dir)

            materialize.apply_plan(plan_csv, output_dir, True)

            self.assertEqual(before_names, sorted(path.name for path in input_dir.iterdir()))
            self.assertEqual(before_hashes, self._source_hashes(input_dir))

    def _preflight(self, base: Path) -> tuple[Path, Path, Path]:
        input_dir, audit_dir, output_dir = self._fixture(base)
        rows, summary = materialize.build_plan(input_dir, audit_dir, output_dir, 370, 368, 184)
        preflight_dir = materialize.write_preflight(rows, summary, base)
        return preflight_dir / "approved_reconciliation_plan.csv", output_dir, input_dir

    def _fixture(self, base: Path) -> tuple[Path, Path, Path]:
        input_dir = base / "input"
        audit_dir = base / "audit"
        output_dir = base / "cleaned"
        input_dir.mkdir()
        audit_dir.mkdir()

        names = self._fixture_names()
        for index, name in enumerate(names, start=1):
            write_image(input_dir / name, index % 240)
        for name in ["S__3956902_1.jpg", "S__3956902_2.jpg"]:
            (input_dir / name).write_bytes((input_dir / "S__3956902_0.jpg").read_bytes())
        (input_dir / "S__10690658_1.jpg").write_bytes((input_dir / "S__10690658_0.jpg").read_bytes())

        sorted_paths = materialize.discover_images(input_dir)
        self.assertEqual("S__3956902_2.jpg", sorted_paths[31].name)
        self.assertEqual("S__10690658_1.jpg", sorted_paths[199].name)
        self._write_audit(audit_dir, sorted_paths)
        return input_dir, audit_dir, output_dir

    def _fixture_names(self) -> list[str]:
        names = [f"S__{number}.jpg" for number in range(1, 30)]
        names.extend(["S__3956902_0.jpg", "S__3956902_1.jpg", "S__3956902_2.jpg"])
        names.extend(f"S__{number}.jpg" for number in range(4_000_000, 4_000_000 + 166))
        names.extend(["S__10690658_0.jpg", "S__10690658_1.jpg"])
        names.extend(f"S__{number}.jpg" for number in range(11_000_000, 11_000_000 + 170))
        self.assertEqual(370, len(names))
        return names

    def _write_audit(self, audit_dir: Path, sorted_paths: list[Path]) -> None:
        groups = {
            "S__3956902_0.jpg": ("DUP-0001", "3", "false"),
            "S__3956902_1.jpg": ("DUP-0001", "3", "false"),
            "S__3956902_2.jpg": ("DUP-0001", "3", "false"),
            "S__10690658_0.jpg": ("DUP-0029", "2", "false"),
            "S__10690658_1.jpg": ("DUP-0029", "2", "false"),
        }
        fieldnames = [
            "original_sort_position",
            "source_filename",
            "source_path",
            "sha256",
            "duplicate_group_id",
            "duplicate_group_size",
            "is_unique_sha256",
        ]
        with (audit_dir / "reconciliation_plan.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for position, path in enumerate(sorted_paths, start=1):
                group_id, group_size, is_unique = groups.get(path.name, ("", "1", "true"))
                writer.writerow(
                    {
                        "original_sort_position": str(position),
                        "source_filename": path.name,
                        "source_path": str(path),
                        "sha256": materialize.sha256_file(path),
                        "duplicate_group_id": group_id,
                        "duplicate_group_size": group_size,
                        "is_unique_sha256": is_unique,
                    }
                )

    def _mutate_audit(self, audit_dir: Path, filename: str, field: str, value: str) -> None:
        path = audit_dir / "reconciliation_plan.csv"
        with path.open("r", newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
            fieldnames = list(rows[0].keys())
        for row in rows:
            if row["source_filename"] == filename:
                row[field] = value
                break
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _source_hashes(self, input_dir: Path) -> dict[str, str]:
        return {path.name: materialize.sha256_file(path) for path in input_dir.iterdir() if path.is_file()}


if __name__ == "__main__":
    unittest.main()
