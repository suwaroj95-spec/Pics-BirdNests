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

from tools import audit_unresolved_pair_integrity as audit


def write_image(path: Path, size: tuple[int, int] = (24, 24), value: int = 220) -> None:
    image = np.full((size[1], size[0], 3), value, dtype=np.uint8)
    if not cv2.imwrite(str(path), image):
        raise AssertionError(f"Could not write {path}")


class UnresolvedPairIntegrityAuditTests(unittest.TestCase):
    def test_same_sha256_within_pair_becomes_exact_duplicate(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            plan, src = self._plan(Path(tmp), "duplicate")
            output = audit.audit_pairs(plan, src)
            rows = self._csv_rows(output)

            self.assertEqual({"EXACT_DUPLICATE_WITHIN_PAIR"}, {row["integrity_classification"] for row in rows})

    def test_different_hashes_with_valid_images_become_role_uncertain(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            plan, src = self._plan(Path(tmp), "distinct")
            output = audit.audit_pairs(plan, src)
            rows = self._csv_rows(output)

            self.assertEqual({"DISTINCT_IMAGES_ROLE_UNCERTAIN"}, {row["integrity_classification"] for row in rows})

    def test_dimension_mismatch_is_classified_separately(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            plan, src = self._plan(Path(tmp), "mismatch")
            output = audit.audit_pairs(plan, src)
            rows = self._csv_rows(output)

            self.assertEqual({"DISTINCT_IMAGES_DIMENSION_MISMATCH"}, {row["integrity_classification"] for row in rows})

    def test_missing_source_image_becomes_image_read_error(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            plan, src = self._plan(Path(tmp), "distinct")
            (src / "b.jpg").unlink()
            output = audit.audit_pairs(plan, src)
            rows = self._csv_rows(output)

            self.assertEqual({"IMAGE_READ_ERROR"}, {row["integrity_classification"] for row in rows})

    def test_pair_with_not_exactly_two_rows_becomes_plan_structure_error(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            plan, src = self._plan(Path(tmp), "one_row")
            output = audit.audit_pairs(plan, src)
            rows = self._csv_rows(output)

            self.assertEqual({"PLAN_STRUCTURE_ERROR"}, {row["integrity_classification"] for row in rows})

    def test_exact_duplicate_pairs_are_never_rename_eligible(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            plan, src = self._plan(Path(tmp), "duplicate")
            output = audit.audit_pairs(plan, src)

            self.assertTrue(all(row["rename_eligible"] == "false" for row in self._csv_rows(output)))

    def test_distinct_unresolved_pairs_are_marked_for_human_review(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            plan, src = self._plan(Path(tmp), "distinct")
            output = audit.audit_pairs(plan, src)

            self.assertTrue(all(row["human_review_required"] == "true" for row in self._csv_rows(output)))

    def test_audit_does_not_modify_source_files_or_plan(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            plan, src = self._plan(Path(tmp), "distinct")
            before_plan = plan.read_bytes()
            before_hashes = {path.name: audit.sha256_file(path) for path in src.iterdir()}
            audit.audit_pairs(plan, src)

            self.assertEqual(before_plan, plan.read_bytes())
            self.assertEqual(before_hashes, {path.name: audit.sha256_file(path) for path in src.iterdir()})

    def test_review_images_are_created_only_in_matching_category_folder(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            plan, src = self._plan(Path(tmp), "duplicate")
            duplicate_output = audit.audit_pairs(plan, src, Path(tmp) / "dup_out")
            plan, src = self._plan(Path(tmp) / "distinct_case", "distinct")
            distinct_output = audit.audit_pairs(plan, src, Path(tmp) / "distinct_out")

            self.assertEqual(1, len(list((duplicate_output / "duplicate_pair_review").iterdir())))
            self.assertEqual(0, len(list((duplicate_output / "marker_role_review").iterdir())))
            self.assertEqual(0, len(list((distinct_output / "duplicate_pair_review").iterdir())))
            self.assertEqual(1, len(list((distinct_output / "marker_role_review").iterdir())))

    def test_summary_counts_match_csv_classifications(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            plan, src = self._plan(Path(tmp), "distinct")
            output = audit.audit_pairs(plan, src)
            rows = self._csv_rows(output)
            summary = json.loads((output / "unresolved_pair_integrity_summary.json").read_text(encoding="utf-8"))

            self.assertEqual(1, summary["distinct_images_role_uncertain_count"])
            self.assertEqual(2, len(rows))
            self.assertEqual({"DISTINCT_IMAGES_ROLE_UNCERTAIN"}, {row["integrity_classification"] for row in rows})

    def _plan(self, base: Path, kind: str) -> tuple[Path, Path]:
        src = base / "src"
        src.mkdir(parents=True)
        write_image(src / "a.jpg", value=50)
        if kind == "duplicate":
            (src / "b.jpg").write_bytes((src / "a.jpg").read_bytes())
        elif kind == "mismatch":
            write_image(src / "b.jpg", size=(28, 24), value=80)
        else:
            write_image(src / "b.jpg", value=80)

        rows = [self._row(src / "a.jpg", 1, "marker")]
        if kind != "one_row":
            rows.append(self._row(src / "b.jpg", 2, "marker"))
        plan = base / "rename_plan.csv"
        with plan.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=audit.REQUIRED_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return plan, src

    def _row(self, path: Path, sorted_position: int, role: str) -> dict[str, str]:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        height, width = image.shape[:2]
        return {
            "sorted_position": str(sorted_position),
            "pair_sequence": "1",
            "source_filename": path.name,
            "source_path": str(path),
            "source_sha256": audit.sha256_file(path),
            "width": str(width),
            "height": str(height),
            "role_proposed": role,
            "marker_evidence_score": str(100 - sorted_position),
            "validation_status": "BOTH_MARKER_LIKE",
            "target_id": "16",
        }

    def _csv_rows(self, output: Path) -> list[dict[str, str]]:
        with (output / "unresolved_pair_integrity.csv").open("r", newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
