from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs" / "anchor-review-small-16-32-64-128" / "google-apps-script" / "ExpertReviewV2.gs"
CODE = ROOT / "docs" / "anchor-review-small-16-32-64-128" / "google-apps-script" / "Code.gs"
HARNESS = ROOT / "tests" / "apps_script_v2_backend_harness.js"
AUTHORITATIVE_SPREADSHEET_ID = "1c5QYrz8CJymAO3LAu8szYnBoubnoT82dPQkf0UJRGTg"


class AppsScriptV2BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.legacy = CODE.read_text(encoding="utf-8")

    def test_v2_backend_is_isolated_from_legacy_code(self) -> None:
        self.assertTrue(SCRIPT.exists())
        self.assertIn("function handleExpertReviewV2Post", self.source)
        self.assertIn("function isExpertReviewV2Action_", self.source)
        self.assertIn("handleExpertReviewV2Post(payload, { lockAlreadyHeld: true })", self.legacy)
        handoff_index = self.legacy.index("handleExpertReviewV2Post(payload, { lockAlreadyHeld: true })")
        legacy_validation_index = self.legacy.index("validatePayloadShape(payload)")
        self.assertLess(handoff_index, legacy_validation_index)
        for action in ("LOAD_PROGRESS", "SAVE_PROGRESS", "SUBMIT_FINAL"):
            self.assertIn(f'payload.action === "{action}"', self.legacy)

    def test_legacy_spreadsheet_binding_matches_expert_review_v2(self) -> None:
        self.assertNotIn("PASTE_TARGET_SPREADSHEET_ID_HERE", self.legacy)
        legacy_match = re.search(r'const\s+SPREADSHEET_ID\s*=\s*"([^"]+)";', self.legacy)
        v2_match = re.search(r'spreadsheetId:\s*"([^"]+)"', self.source)
        self.assertIsNotNone(legacy_match)
        self.assertIsNotNone(v2_match)
        self.assertEqual(legacy_match.group(1), AUTHORITATIVE_SPREADSHEET_ID)
        self.assertEqual(v2_match.group(1), AUTHORITATIVE_SPREADSHEET_ID)
        self.assertEqual(legacy_match.group(1), v2_match.group(1))

    def test_production_identity_fails_closed_without_script_properties(self) -> None:
        for value in (
            "ERV2_REVIEWER_TOKEN_MAP_JSON",
            "PropertiesService.getScriptProperties()",
            "UNAUTHORIZED_REVIEWER",
            "tokenHash",
        ):
            self.assertIn(value, self.source)
        self.assertNotIn("REV_A_TOKEN", self.source)
        self.assertNotIn("REV_B_TOKEN", self.source)

    def test_review_privacy_and_immutability_guards_are_present(self) -> None:
        for value in (
            "RESPONSE_ALREADY_SUBMITTED",
            "STALE_STATE",
            "LockService.getScriptLock",
            "Utilities.computeDigest",
            "erv2CanonicalResponseJson_",
            "ReviewSessionsV2",
            "ReviewResponses",
        ):
            self.assertIn(value, self.source)
        self.assertNotIn("ResearcherCaseMeta", self.source)

    def test_no_deployment_or_live_gate_mutation_capabilities_added(self) -> None:
        for value in (
            "ScriptApp.newDeployment",
            "setSharing",
            "setShareableByEditors",
            "addViewer",
            "addEditor",
            "review_start_enabled\", \"TRUE",
            "launch_gate_status\", \"LAUNCHED",
            "UrlFetchApp",
            "MailApp",
            "GmailApp",
        ):
            self.assertNotIn(value, self.source)

    def test_local_deterministic_harness_passes(self) -> None:
        result = subprocess.run(
            ["node", str(HARNESS)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("APPS_SCRIPT_V2_BACKEND_HARNESS_PASS", result.stdout)

    def test_private_drive_asset_layer_uses_server_side_config(self) -> None:
        for value in (
            "ERV2_REVIEW_ASSET_FOLDER_ID",
            "verifyExpertReviewV2DriveAssetInventory",
            "verifyExpertReviewV2DriveAssetHashesBatch",
            "resetExpertReviewV2DriveAssetVerification",
            "V2_GET_CASE_ASSET",
            "ASSET_FOLDER_NOT_CONFIGURED",
            "ASSET_INTEGRITY_MISMATCH",
            "Utilities.base64Encode",
        ):
            self.assertIn(value, self.source)
        self.assertNotIn("1ZmmUTkemUfLQH2uwY_1khaATH578_ntS", self.source)

    def test_reviewer_safe_case_payload_excludes_asset_internals(self) -> None:
        safe_payload_body = self.source.split("function erv2SafeCasePayload_")[1].split("function erv2OwnCaseResponsePayload_")[0]
        self.assertNotIn("asset_sha256:", safe_payload_body)
        self.assertNotIn("review_asset_ref:", safe_payload_body)

    def test_drive_hash_batch_has_unambiguous_final_state_and_locking(self) -> None:
        batch_body = self.source.split("function erv2VerifyDriveAssetHashesBatch_")[1].split("function erv2GetCaseAsset_")[0]
        self.assertIn("erv2WithScriptLock_", batch_body)
        self.assertIn("DRIVE_ASSET_FULL_SHA256_VERIFIED", batch_body)
        self.assertIn("DRIVE_ASSET_FULL_SHA256_FAILED", batch_body)
        self.assertIn("DRIVE_ASSET_SHA256_BATCH_IN_PROGRESS", batch_body)
        self.assertIn("batch_failures", batch_body)
        self.assertNotIn("failures: failures", batch_body)
        for value in (
            "ERV2_ASSET_VERIFY_MISMATCH_COUNT",
            "ERV2_ASSET_VERIFY_MISSING_COUNT",
            "ERV2_ASSET_VERIFY_DUPLICATE_COUNT",
            "ERV2_ASSET_VERIFY_INVALID_MIME_COUNT",
            "ERV2_ASSET_VERIFY_INTERNAL_ERROR_COUNT",
            "ERV2_ASSET_VERIFY_FOLDER_ID",
            "ASSET_VERIFICATION_STATE_MISMATCH",
        ):
            self.assertIn(value, self.source)


if __name__ == "__main__":
    unittest.main()
