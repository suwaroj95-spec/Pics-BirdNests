from __future__ import annotations

import json
import hashlib
import unittest
from pathlib import Path


class ContactSheetPublicManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.manifest_path = self.root / "docs" / "contact-sheets" / "contact-sheet-manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def test_manifest_counts_and_thresholds(self) -> None:
        self.assertEqual(self.manifest["status"], "SANITIZED_PUBLIC_CONTACT_SHEET_READY")
        self.assertEqual(self.manifest["sets"]["primary"]["threshold"], "0.125")
        self.assertEqual(self.manifest["sets"]["comparison"]["threshold"], "0.175")
        self.assertEqual(self.manifest["sets"]["primary"]["model_only_records"], 1785)
        self.assertEqual(self.manifest["sets"]["comparison"]["model_only_records"], 405)
        self.assertEqual(self.manifest["sets"]["primary"]["page_count"], 90)
        self.assertEqual(self.manifest["sets"]["comparison"]["page_count"], 21)
        self.assertEqual(self.manifest["layout_version"], "raw-left_marker-plus-model-guide-right_v2")
        self.assertEqual(
            self.manifest["panel_semantics"],
            {
                "left": "RAW IMAGE (NO OVERLAY)",
                "right": "ORIGINAL MARKER IMAGE + MODEL LOCATION GUIDE",
            },
        )

    def test_page_numbers_and_filenames_are_continuous(self) -> None:
        expectations = {
            "primary": (90, "primary_0125_page_"),
            "comparison": (21, "comparison_0175_page_"),
        }
        for group, (count, prefix) in expectations.items():
            pages = self.manifest["sets"][group]["pages"]
            self.assertEqual(len(pages), count)
            self.assertEqual([page["page_number"] for page in pages], list(range(1, count + 1)))
            for number, page in enumerate(pages, start=1):
                filename = f"{prefix}{number:03d}.png"
                self.assertEqual(page["filename"], filename)
                self.assertEqual(page["public_path"].replace("\\", "/").split("/")[-1], filename)

    def test_public_paths_exist_and_are_relative(self) -> None:
        for group in ("primary", "comparison"):
            for page in self.manifest["sets"][group]["pages"]:
                public_path = page["public_path"]
                parent_tmp = ".." + "/tmp"
                self.assertFalse(public_path.startswith(("/", "\\", "C:", parent_tmp)))
                self.assertTrue((self.root / "docs" / "contact-sheets" / public_path).is_file())

    def test_manifest_sizes_and_hashes_match_files(self) -> None:
        for group in ("primary", "comparison"):
            for page in self.manifest["sets"][group]["pages"]:
                path = self.root / "docs" / "contact-sheets" / page["public_path"]
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(path.stat().st_size, page["size_bytes"])
                self.assertEqual(digest, page["sha256"])

    def test_manifest_has_no_private_path_text(self) -> None:
        text = self.manifest_path.read_text(encoding="utf-8")
        windows_drive = "C:"
        parent_tmp = ".." + "/tmp"
        forbidden_terms = (
            parent_tmp,
            windows_drive + "\\",
            windows_drive + "/",
            "local" + "host",
            "location" + ".protocol",
            "data" + "-local-target",
        )
        for forbidden in forbidden_terms:
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
