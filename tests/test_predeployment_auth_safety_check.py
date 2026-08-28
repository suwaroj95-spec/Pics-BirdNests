from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools" / "expert_review_admin" / "predeployment_auth_safety_check.gs"


class PredeploymentAuthSafetyCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = CHECKER.read_text(encoding="utf-8")
        cls.returned_object_body = cls.source.split("console.log(JSON.stringify(result))", 1)[0]

    def test_checker_file_exists(self) -> None:
        self.assertTrue(CHECKER.exists())

    def test_expected_function_exists(self) -> None:
        self.assertIn("function runExpertReviewV2PredeploymentSafetyCheck()", self.source)

    def test_token_map_contents_are_never_logged(self) -> None:
        self.assertIn("const rawTokenMap = props.getProperty", self.source)
        self.assertNotIn("console.log(rawTokenMap", self.source)
        self.assertNotIn("console.log(parsed", self.source)
        self.assertEqual(1, self.source.count("console.log("))
        self.assertIn("console.log(JSON.stringify(result))", self.source)

    def test_token_hash_keys_are_never_returned(self) -> None:
        self.assertIn("const hashKeys = Object.keys(parsed)", self.source)
        self.assertNotRegex(self.returned_object_body, re.compile(r"\bhashKeys\b\s*[:,]"))
        self.assertNotIn("token_hashes", self.source)
        self.assertNotIn("partial_hash", self.source)

    def test_no_script_property_writes(self) -> None:
        forbidden = re.compile(r"\.(setProperty|deleteProperty|setProperties|deleteAllProperties)\s*\(")
        self.assertIsNone(forbidden.search(self.source))

    def test_no_sheet_writes(self) -> None:
        forbidden = re.compile(
            r"\.(setValue|setValues|appendRow|deleteRow|deleteRows|insertRow|insertRows|"
            r"clear|clearContent)\s*\("
        )
        self.assertIsNone(forbidden.search(self.source))

    def test_no_drive_writes(self) -> None:
        forbidden_patterns = (
            r"\bDriveApp\.create",
            r"\.setSharing\s*\(",
            r"\.setShareableByEditors\s*\(",
            r"\.addViewer\s*\(",
            r"\.addEditor\s*\(",
            r"\.setName\s*\(",
            r"\.setContent\s*\(",
            r"\.setDescription\s*\(",
            r"\.setTrashed\s*\(",
        )
        for pattern in forbidden_patterns:
            self.assertIsNone(re.search(pattern, self.source))

    def test_expected_counts_are_encoded_as_assertions(self) -> None:
        for value in ("expectedCases: 1169", "expectedAssignments: 1461"):
            self.assertIn(value, self.source)
        self.assertIn("expectedRevAAssignments: 1169", self.source)
        self.assertIn("expectedRevBAssignments: 292", self.source)
        self.assertIn("cursor === ERV2_PREDEPLOYMENT_EXPECTED_.expectedCases", self.source)
        self.assertIn("assignmentRows.length === ERV2_PREDEPLOYMENT_EXPECTED_.expectedAssignments", self.source)
        self.assertIn("revAAssignments === ERV2_PREDEPLOYMENT_EXPECTED_.expectedRevAAssignments", self.source)
        self.assertIn("revBAssignments === ERV2_PREDEPLOYMENT_EXPECTED_.expectedRevBAssignments", self.source)

    def test_expected_launch_state_blocked_false(self) -> None:
        self.assertIn('expectedLaunchGateStatus: "BLOCKED"', self.source)
        self.assertIn("expectedReviewStartEnabled: false", self.source)
        self.assertIn("LAUNCH_GATE_STATUS_MISMATCH", self.source)
        self.assertIn("REVIEW_START_ENABLED_MISMATCH", self.source)

    def test_result_schema_is_sanitized(self) -> None:
        for field in (
            "token_map_present",
            "token_map_parse_ok",
            "token_map_entry_count",
            "token_map_reviewer_set_ok",
            "token_hash_format_ok",
            "asset_folder_property_present",
            "asset_folder_binding_matches",
            "reviewer_a_present",
            "reviewer_b_present",
            "reviewer_a_active",
            "reviewer_b_active",
            "total_assignments",
            "rev_a_assignments",
            "rev_b_assignments",
            "review_responses",
            "review_sessions_v2",
            "launch_gate_status",
            "review_start_enabled",
            "live_writes_performed",
        ):
            self.assertIn(field, self.source)
        for forbidden in (
            "token_map_json",
            "raw_token",
            "reviewerToken",
            "accessToken",
            "folder_id:",
            "drive_url",
            "case_id:",
            "comment:",
            "response_contents",
        ):
            self.assertNotIn(forbidden, self.source)

    def test_checker_fails_closed(self) -> None:
        self.assertIn('status: "PREDEPLOYMENT_SAFETY_BLOCKED"', self.source)
        self.assertIn('"PREDEPLOYMENT_SAFETY_BLOCKED"', self.source)
        self.assertIn("catch (error)", self.source)
        self.assertIn("failure_codes", self.source)
        self.assertIn('result.ok = !result.failure_codes', self.source)

    def test_existing_backend_helpers_are_used_for_authoritative_reads(self) -> None:
        self.assertIn("erv2ReadRows_(sheets.reviewers, ERV2_HEADERS.Reviewers)", self.source)
        self.assertIn("erv2ReadRows_(sheets.assignments, ERV2_HEADERS.ReviewAssignments)", self.source)
        self.assertIn("erv2ReadRows_(sheets.responses, ERV2_HEADERS.ReviewResponses)", self.source)
        self.assertIn("erv2ReadRows_(sheets.sessions, ERV2_HEADERS.ReviewSessionsV2)", self.source)
        self.assertIn("const config = erv2ReadConfigV2_(sheets.config)", self.source)

    def test_no_deployment_or_remote_side_effect_capabilities(self) -> None:
        for forbidden in (
            "ScriptApp.newDeployment",
            "UrlFetchApp",
            "MailApp",
            "GmailApp",
            "LockService.getScriptLock",
            "SpreadsheetApp.create",
        ):
            self.assertNotIn(forbidden, self.source)


if __name__ == "__main__":
    unittest.main()
