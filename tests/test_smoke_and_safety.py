from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import crop_clean_patches
import project_panel


def crop_args(**overrides: object) -> argparse.Namespace:
    values = {
        "raw_dir": "RawPics",
        "output_dir": "Crops",
        "patch_size": 256,
        "stride": 128,
        "coverage_step": 48,
        "min_edge_shift": 24,
        "mask_dilation": 20,
        "min_content_ratio": 0.35,
        "positive_jitter_crops": 3,
        "positive_jitter_radius": 64,
        "min_blue_component_area": 20,
        "random_seed": 42,
        "dirty_crop_source": "registered_original",
        "no_clean": False,
        "no_dirty": False,
        "keep_existing": False,
        "clear_output": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class CropSafetyTests(unittest.TestCase):
    def test_crop_defaults_keep_existing_outputs(self) -> None:
        crop_clean_patches.configure_from_args(crop_args())
        self.assertFalse(crop_clean_patches.CLEAR_OUTPUT_DIRS)

    def test_crop_clear_output_requires_explicit_flag(self) -> None:
        crop_clean_patches.configure_from_args(crop_args(clear_output=True))
        self.assertTrue(crop_clean_patches.CLEAR_OUTPUT_DIRS)

    def test_clear_output_only_deletes_expected_generated_dirs(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_root:
            output_dir = Path(temp_root) / "CropsOut"
            clean_dir = output_dir / "clean_negative"
            dirty_dir = output_dir / "dirty_positive"
            debug_dir = output_dir / "debug_masks"
            for directory in (clean_dir, dirty_dir, debug_dir):
                directory.mkdir(parents=True)
            clean_file = clean_dir / "old.jpg"
            dirty_file = dirty_dir / "old.jpg"
            debug_file = debug_dir / "old.png"
            keep_file = output_dir / "keep.txt"
            clean_file.write_text("old", encoding="utf-8")
            dirty_file.write_text("old", encoding="utf-8")
            debug_file.write_text("old", encoding="utf-8")
            keep_file.write_text("keep", encoding="utf-8")

            crop_clean_patches.configure_from_args(
                crop_args(output_dir=str(output_dir), clear_output=True)
            )
            crop_clean_patches.clear_generated_outputs(clean_dir, dirty_dir, debug_dir)

            self.assertFalse(clean_file.exists())
            self.assertFalse(dirty_file.exists())
            self.assertFalse(debug_file.exists())
            self.assertTrue(keep_file.exists())

    def test_clear_output_rejects_unexpected_directory(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_root:
            output_dir = Path(temp_root) / "CropsOut"
            clean_dir = output_dir / "clean_negative"
            dirty_dir = output_dir / "dirty_positive"
            unexpected_debug = Path(temp_root) / "not_debug_masks"
            for directory in (clean_dir, dirty_dir, unexpected_debug):
                directory.mkdir(parents=True)

            crop_clean_patches.configure_from_args(
                crop_args(output_dir=str(output_dir), clear_output=True)
            )
            with self.assertRaises(ValueError):
                crop_clean_patches.clear_generated_outputs(clean_dir, dirty_dir, unexpected_debug)

    def test_crop_rejects_path_escape(self) -> None:
        with self.assertRaises(ValueError):
            crop_clean_patches.resolve_project_path("..\\outside")

    def test_crop_runs_on_synthetic_fixture_in_temp_directory(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_root:
            temp_path = Path(temp_root)
            raw_dir = temp_path / "RawPics"
            output_dir = temp_path / "Crops"
            raw_dir.mkdir()

            yy, xx = np.indices((192, 192))
            image = np.zeros((192, 192, 3), dtype=np.uint8)
            image[:, :, 0] = (xx * 2).astype(np.uint8)
            image[:, :, 1] = (yy * 2).astype(np.uint8)
            image[:, :, 2] = 120
            image[96:176, 96:176, :] = 80 + ((xx[96:176, 96:176] + yy[96:176, 96:176]) % 80)[
                :, :, None
            ].astype(np.uint8)
            marked = image.copy()
            cv2.circle(marked, (28, 28), 8, (255, 0, 0), thickness=-1)
            cv2.imwrite(str(raw_dir / "1.jpg"), image)
            cv2.imwrite(str(raw_dir / "1m.jpg"), marked)

            crop_clean_patches.configure_from_args(
                crop_args(
                    raw_dir=str(raw_dir),
                    output_dir=str(output_dir),
                    patch_size=64,
                    stride=64,
                    coverage_step=64,
                    min_edge_shift=0,
                    mask_dilation=8,
                    min_content_ratio=0.05,
                    positive_jitter_crops=0,
                    positive_jitter_radius=0,
                    min_blue_component_area=5,
                    dirty_crop_source="inpainted_marked",
                    clear_output=False,
                )
            )
            crop_clean_patches.main()

            self.assertTrue((output_dir / "metadata.csv").exists())
            self.assertTrue(any((output_dir / "clean_negative").glob("*.jpg")))
            self.assertTrue(any((output_dir / "dirty_positive").glob("*.jpg")))


class PanelValidationTests(unittest.TestCase):
    def test_panel_html_keeps_controls_without_manual_ui(self) -> None:
        html = project_panel.INDEX_HTML
        self.assertIn('id="runButton"', html)
        self.assertIn('id="refreshButton"', html)
        self.assertIn('id="statusPill"', html)
        self.assertIn('id="outputs"', html)
        self.assertIn('id="clearOutput"', html)
        self.assertIn('fetch("/api/status")', html)
        self.assertIn('fetch("/api/run"', html)
        self.assertNotIn("manualButton", html)
        self.assertNotIn("manualModal", html)
        self.assertNotIn("manualClose", html)
        self.assertNotIn("openManual", html)
        self.assertNotIn("closeManual", html)
        self.assertNotIn("modalBackdrop", html)
        self.assertNotIn(".guide", html)

    def test_default_panel_crop_command_keeps_existing_outputs(self) -> None:
        config = project_panel.validate_config(project_panel.DEFAULT_CONFIG)
        command = project_panel.crop_command(config)
        self.assertIn("--keep-existing", command)
        self.assertNotIn("--clear-output", command)

    def test_panel_rejects_path_escape(self) -> None:
        config = project_panel.merged_config({"crop": {"outputDir": "..\\outside"}})
        with self.assertRaises(ValueError):
            project_panel.validate_config(config)

    def test_panel_rejects_absolute_path(self) -> None:
        config = project_panel.merged_config({"crop": {"outputDir": "C:\\outside"}})
        with self.assertRaises(ValueError):
            project_panel.validate_config(config)

    def test_panel_rejects_forward_slash_traversal(self) -> None:
        config = project_panel.merged_config({"backtest": {"outputDir": "../outside"}})
        with self.assertRaises(ValueError):
            project_panel.validate_config(config)

    def test_panel_rejects_mixed_windows_traversal(self) -> None:
        config = project_panel.merged_config({"anomaly": {"outputDir": "safe\\..\\..\\outside"}})
        with self.assertRaises(ValueError):
            project_panel.validate_config(config)

    @unittest.skipUnless(hasattr(os, "symlink"), "os.symlink is not available")
    def test_panel_rejects_symlink_escape_when_supported(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as link_parent:
            with tempfile.TemporaryDirectory() as outside:
                link = Path(link_parent) / "outside_link"
                try:
                    os.symlink(outside, link, target_is_directory=True)
                except (OSError, NotImplementedError) as exc:
                    self.skipTest(f"symlink creation is not available: {exc}")
                relative_link = link.relative_to(ROOT)
                config = project_panel.merged_config({"crop": {"outputDir": str(relative_link)}})
                with self.assertRaises(ValueError):
                    project_panel.validate_config(config)

    def test_panel_rejects_out_of_range_numbers(self) -> None:
        config = project_panel.merged_config({"crop": {"patchSize": 0}})
        with self.assertRaises(ValueError):
            project_panel.validate_config(config)

    def test_panel_rejects_invalid_boolean(self) -> None:
        config = project_panel.merged_config({"steps": {"crop": "yes"}})
        with self.assertRaises(ValueError):
            project_panel.validate_config(config)

    def test_panel_rejects_invalid_numeric_type(self) -> None:
        config = project_panel.merged_config({"anomaly": {"contamination": "0.1"}})
        with self.assertRaises(ValueError):
            project_panel.validate_config(config)

    def test_panel_rejects_bad_json_payload(self) -> None:
        with self.assertRaises(ValueError):
            project_panel.parse_run_config(b"{bad json", 9)

    def test_panel_rejects_oversized_payload(self) -> None:
        with self.assertRaises(ValueError):
            project_panel.parse_run_config(b"{}", project_panel.MAX_REQUEST_BYTES + 1)

    def test_panel_parses_valid_payload(self) -> None:
        payload = json.dumps({"steps": {"crop": False}}).encode("utf-8")
        config = project_panel.parse_run_config(payload, len(payload))
        self.assertFalse(config["steps"]["crop"])

    def test_panel_default_binds_to_localhost(self) -> None:
        with patch.object(sys, "argv", ["project_panel.py"]):
            args = project_panel.parse_args()
        self.assertEqual(args.host, "127.0.0.1")

    def test_panel_accepts_existing_defaults(self) -> None:
        config = project_panel.validate_config(project_panel.DEFAULT_CONFIG)
        self.assertEqual(config["crop"]["rawDir"], "RawPics")
        self.assertEqual(config["backtest"]["outputDir"], "BacktestSelection")


class PanelManagerTests(unittest.TestCase):
    def test_manager_batch_has_safe_lifecycle_guards(self) -> None:
        manager = ROOT / "manage_project_panel.bat"
        text = manager.read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn("project_panel.pid", text)
        self.assertIn("project_panel.log", text)
        self.assertIn("127.0.0.1", text)
        self.assertIn("project_panel.py", text)
        self.assertIn("get-managedprocess", lowered)
        self.assertIn("stop-process -id $managed.id", lowered)
        self.assertNotIn("taskkill /im python.exe", lowered)
        self.assertNotIn("taskkill /f /im python.exe", lowered)
        for command in ('"check"', '"start"', '"status"', '"stop"'):
            self.assertIn(command, lowered)


if __name__ == "__main__":
    unittest.main()
