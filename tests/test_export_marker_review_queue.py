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

from tools import export_marker_review_queue as exporter


def write_image(path: Path, value: int = 220) -> None:
    image = np.full((12, 12, 3), value, dtype=np.uint8)
    if not cv2.imwrite(str(path), image):
        raise AssertionError(f"Could not write {path}")


class MarkerReviewQueueExportTests(unittest.TestCase):
    def test_default_selects_only_pending_review_required_rows(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, _ = self._write_plan(base)
            rows = exporter.load_plan(plan)
            selected = exporter.select_review_rows(rows)

            self.assertEqual(["a.jpg", "b.jpg"], [row["source_filename"] for row in selected])

    def test_output_order_follows_pair_then_sorted_position(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, _ = self._write_plan(base, unordered=True)
            selected = exporter.select_review_rows(exporter.load_plan(plan))

            self.assertEqual(["2", "3"], [row["sorted_position"] for row in selected])

    def test_copied_filenames_sort_like_review_queue(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, _ = self._write_plan(base)
            output = exporter.export_review_queue(plan, base / "out")
            with (output / "review_queue.csv").open("r", newline="", encoding="utf-8") as handle:
                queue = list(csv.DictReader(handle))

            queue_names = [row["copied_filename"] for row in queue]
            image_names = sorted(path.name for path in (output / "images").iterdir())
            self.assertEqual(queue_names, image_names)

    def test_every_review_pair_must_contain_two_rows(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, rows = self._write_plan(base)
            rows = [row for row in rows if row["source_filename"] != "b.jpg"]
            self._rewrite_plan(plan, rows)

            with self.assertRaises(exporter.ReviewExportError):
                exporter.export_review_queue(plan, base / "out")

    def test_odd_selected_row_count_blocks_export(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, rows = self._write_plan(base)
            rows[2]["review_required"] = "TRUE"
            rows[2]["human_review_status"] = "PENDING"
            rows[2]["pair_sequence"] = "2"
            self._rewrite_plan(plan, rows)

            with self.assertRaises(exporter.ReviewExportError):
                exporter.export_review_queue(plan, base / "out")

    def test_missing_source_blocks_before_finalize(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, _ = self._write_plan(base)
            (base / "src" / "a.jpg").unlink()

            with self.assertRaises(exporter.ReviewExportError):
                exporter.export_review_queue(plan, base / "out")
            self.assertFalse((base / "out").exists())

    def test_sha_mismatch_blocks_export(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, _ = self._write_plan(base)
            write_image(base / "src" / "a.jpg", 10)

            with self.assertRaises(exporter.ReviewExportError):
                exporter.export_review_queue(plan, base / "out")
            self.assertFalse((base / "out").exists())

    def test_copied_sha256_matches_source_sha256(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, _ = self._write_plan(base)
            output = exporter.export_review_queue(plan, base / "out")
            with (output / "review_queue.csv").open("r", newline="", encoding="utf-8") as handle:
                queue = list(csv.DictReader(handle))

            self.assertTrue(all(row["source_sha256"] == row["output_sha256"] for row in queue))

    def test_source_images_remain_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, _ = self._write_plan(base)
            before = self._source_hashes(base / "src")
            exporter.export_review_queue(plan, base / "out")

            self.assertEqual(before, self._source_hashes(base / "src"))

    def test_output_inside_rawpics_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, _ = self._write_plan(base)
            with self.assertRaises(exporter.ReviewExportError):
                exporter.export_review_queue(plan, ROOT / "RawPics" / "manual_review")

    def test_non_empty_output_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, _ = self._write_plan(base)
            output = base / "out"
            output.mkdir()
            (output / "existing.txt").write_text("busy", encoding="utf-8")

            with self.assertRaises(exporter.ReviewExportError):
                exporter.export_review_queue(plan, output)

    def test_no_review_required_pending_row_is_silently_skipped(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            plan, rows = self._write_plan(base)
            rows[2]["review_required"] = "TRUE"
            rows[2]["human_review_status"] = "APPROVED"
            rows[2]["pair_sequence"] = "2"
            self._rewrite_plan(plan, rows)

            with self.assertRaisesRegex(exporter.ReviewExportError, "Selection is incomplete"):
                exporter.export_review_queue(plan, base / "out")

    def test_26_pair_52_image_plan_fixture_exports_correctly(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            src = base / "src"
            src.mkdir()
            rows: list[dict[str, str]] = []
            for pair_sequence in range(1, 27):
                for offset in range(2):
                    sorted_position = ((pair_sequence - 1) * 2) + offset + 1
                    source = src / f"pair_{pair_sequence:04d}_{offset}.jpg"
                    write_image(source, 20 + pair_sequence + offset)
                    rows.append(self._row(source, str(sorted_position), str(pair_sequence), "TRUE", "PENDING"))
            plan = base / "rename_plan.csv"
            self._rewrite_plan(plan, rows)
            output = exporter.export_review_queue(plan, base / "review")
            with (output / "review_summary.json").open("r", encoding="utf-8") as handle:
                summary = __import__("json").load(handle)

            self.assertEqual(26, summary["selected_pair_count"])
            self.assertEqual(52, summary["selected_row_count"])
            self.assertEqual(52, summary["copied_file_count"])
            self.assertEqual(52, len(list((output / "images").iterdir())))

    def _write_plan(self, base: Path, unordered: bool = False) -> tuple[Path, list[dict[str, str]]]:
        src = base / "src"
        src.mkdir()
        for index, name in enumerate(["a.jpg", "b.jpg", "c.jpg", "d.jpg"], start=1):
            write_image(src / name, 40 + index)
        rows = [
            self._row(src / "a.jpg", "2", "1", "TRUE", "PENDING"),
            self._row(src / "b.jpg", "3", "1", "TRUE", "PENDING"),
            self._row(src / "c.jpg", "1", "1", "FALSE", "APPROVED"),
            self._row(src / "d.jpg", "4", "2", "FALSE", "APPROVED"),
        ]
        if unordered:
            rows = [rows[1], rows[0], rows[2], rows[3]]
        plan = base / "rename_plan.csv"
        self._rewrite_plan(plan, rows)
        return plan, rows

    def _row(
        self,
        source: Path,
        sorted_position: str,
        pair_sequence: str,
        review_required: str,
        human_review_status: str,
    ) -> dict[str, str]:
        target_id = str(15 + int(pair_sequence))
        return {
            "sorted_position": sorted_position,
            "pair_sequence": pair_sequence,
            "source_filename": source.name,
            "source_path": str(source),
            "source_sha256": exporter.sha256_file(source),
            "role_proposed": "marker" if int(sorted_position) % 2 == 0 else "raw",
            "marker_color": "red",
            "marker_evidence_score": "100",
            "confidence_margin": "0",
            "validation_status": "BOTH_MARKER_LIKE" if review_required == "TRUE" else "AUTO_CONFIDENT",
            "target_id": target_id,
            "target_filename": f"{target_id}.jpg",
            "review_required": review_required,
            "human_review_status": human_review_status,
        }

    def _rewrite_plan(self, plan: Path, rows: list[dict[str, str]]) -> None:
        with plan.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=exporter.REQUIRED_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    def _source_hashes(self, src: Path) -> dict[str, str]:
        return {path.name: exporter.sha256_file(path) for path in src.iterdir()}


if __name__ == "__main__":
    unittest.main()
