from __future__ import annotations

import argparse
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools import run_prototype_inference as runner


class PrototypeInferenceCliTests(unittest.TestCase):
    def test_threshold_validation_accepts_frozen_points(self) -> None:
        self.assertEqual(runner.positive_threshold("0.125"), 0.125)
        self.assertEqual(runner.positive_threshold("0.175"), 0.175)

    def test_threshold_validation_rejects_unfrozen_point(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            runner.positive_threshold("0.150")

    def test_device_validation(self) -> None:
        self.assertEqual(runner.device_option("CPU"), "cpu")
        self.assertEqual(runner.device_option("cuda"), "cuda")
        with self.assertRaises(argparse.ArgumentTypeError):
            runner.device_option("mps")

    def test_argument_validation_without_checkpoint_load(self) -> None:
        root = Path(__file__).resolve().parents[1]
        image = root / "docs" / "contact-sheets" / "pages" / "primary" / "primary_0125_page_001.png"
        checkpoint = root / "tmp" / "fasterrcnn_training" / "controlled_20260711_fasterrcnn_cuda_pilot_001" / "final_checkpoint.pt"
        config = root / "handoff" / "prototype_v1" / "prototype_runtime_config.json"
        args = SimpleNamespace(
            input=str(image),
            output=str(root / "tmp" / "prototype_inference_output"),
            checkpoint=str(checkpoint),
            config=str(config),
            threshold=0.125,
            device="cpu",
            save_json="predictions.json",
            save_preview="",
        )
        validated = runner.validate_args(args)
        self.assertEqual(validated["inputs"], [image])
        self.assertEqual(validated["threshold"], 0.125)

    def test_empty_payload_schema(self) -> None:
        payload = runner.make_empty_payload(
            {"model": {"prototype_status": "FASTER_RCNN_PILOT_PROMISING"}},
            "abc123",
            Path("sample.jpg"),
            640,
            480,
            0.125,
            ["warning"],
        )
        self.assertEqual(payload["schema_version"], runner.SCHEMA_VERSION)
        self.assertEqual(payload["source_file"], "sample.jpg")
        self.assertEqual(payload["coordinate_system"], "pixel coordinates in original source image, origin at top-left")
        self.assertEqual(payload["predictions"], [])


if __name__ == "__main__":
    unittest.main()
