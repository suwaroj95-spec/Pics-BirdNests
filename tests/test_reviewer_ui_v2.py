from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAS_DIR = ROOT / "docs" / "anchor-review-small-16-32-64-128" / "google-apps-script"
CODE = GAS_DIR / "Code.gs"
BACKEND = GAS_DIR / "ExpertReviewV2.gs"
UI = GAS_DIR / "ReviewerUIV2.html"


class ReviewerUIV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.code = CODE.read_text(encoding="utf-8")
        cls.backend = BACKEND.read_text(encoding="utf-8")
        cls.ui = UI.read_text(encoding="utf-8")

    def test_scoped_ui_route_preserves_default_legacy_do_get(self) -> None:
        self.assertIn("function doGet(event)", self.code)
        self.assertIn('String(params.ui || "") === "v2"', self.code)
        self.assertIn('createHtmlOutputFromFile("ReviewerUIV2")', self.code)
        self.assertIn('service: "Pics-BirdNests Expert Review Google Sheets bridge"', self.code)
        self.assertIn("reviewSiteOrigin: REVIEW_SITE_ORIGIN", self.code)

    def test_server_rpc_forces_production_validation_and_ignores_identity(self) -> None:
        rpc_body = self.backend.split("function reviewerV2Rpc_")[1].split("function erv2ReviewerRpcPayload_")[0]
        payload_body = self.backend.split("function erv2ReviewerRpcPayload_")[1].split("function erv2ReviewerFacingPayload_")[0]
        self.assertIn("handleExpertReviewV2Post", rpc_body)
        self.assertIn("safeOptions.allowDryRun = false", rpc_body)
        self.assertIn("delete safeOptions.testReviewerIdentity", rpc_body)
        self.assertIn("out.dryRun = false", payload_body)
        for forbidden in ("reviewer_id", "reviewer_role", "assignment_group", "dryRun"):
            self.assertNotIn(f'"{forbidden}"', payload_body.split("const allowed = [", 1)[1].split("];", 1)[0])

    def test_reviewer_facing_payload_is_neutral_and_local_ordered(self) -> None:
        facing_body = self.backend.split("function erv2ReviewerFacingPayload_")[1].split("function erv2ReviewerFacingError_")[0]
        assignments_body = self.backend.split("function erv2ReviewerAssignmentsPayload_")[1].split("function erv2ReviewerCasePayload_")[0]
        case_body = self.backend.split("function erv2ReviewerCasePayload_")[1].split("function erv2ReviewerResponsePayload_")[0]
        self.assertIn("reviewer: { authenticated: true }", facing_body)
        self.assertIn("reviewer_position: index + 1", assignments_body)
        self.assertIn("case_id", case_body)
        self.assertIn("definition_version", case_body)
        for forbidden in (
            "reviewer_id:",
            "reviewer_role:",
            "assignment_group:",
            "review_order:",
            "batch_id:",
            "case_index:",
            "batch_position:",
            "asset_sha256:",
            "review_asset_ref:",
        ):
            self.assertNotIn(forbidden, facing_body + assignments_body + case_body)

    def test_ui_has_required_controls_and_states(self) -> None:
        for value in (
            "accessScreen",
            "loadingScreen",
            "reviewScreen",
            "notLaunchedScreen",
            "completeScreen",
            "errorScreen",
            "บันทึกร่าง",
            "ยืนยันคำตอบ",
            "กลับไปตรวจ",
            "ยืนยันและส่ง",
            "Previous",
            "Next",
            "100%",
        ):
            self.assertIn(value, self.ui)

    def test_decision_and_confidence_codes_remain_exact(self) -> None:
        for code, label in (
            ("CONFIRMED_DIRTY_SPOT", "ยืนยันว่าเป็นจุดสกปรก"),
            ("NOT_DIRTY_SPOT", "ไม่ใช่จุดสกปรก"),
            ("AMBIGUOUS", "ไม่แน่ชัด"),
            ("UNJUDGEABLE", "ไม่สามารถประเมินจากภาพได้"),
            ("ANNOTATION_LOCALIZATION_ISSUE", "ตำแหน่ง Annotation ไม่ตรงกับจุดสกปรก"),
            ("HIGH", "มั่นใจสูง"),
            ("MEDIUM", "มั่นใจปานกลาง"),
            ("LOW", "มั่นใจต่ำ"),
        ):
            self.assertIn(code, self.ui)
            self.assertIn(label, self.ui)

    def test_token_is_tab_scoped_not_url_logged_or_persistent_storage(self) -> None:
        self.assertIn("sessionStorage.setItem(TOKEN_KEY", self.ui)
        self.assertIn("sessionStorage.removeItem(TOKEN_KEY)", self.ui)
        self.assertNotIn("localStorage", self.ui)
        self.assertNotIn("console.log", self.ui)
        self.assertNotIn("location.hash", self.ui)
        self.assertNotIn("URLSearchParams", self.ui)
        self.assertNotIn("reviewerToken=", self.ui)

    def test_image_is_lazy_loaded_and_not_persisted_client_side(self) -> None:
        self.assertIn('action: "V2_GET_CASE_ASSET"', self.ui)
        self.assertIn("loadCurrentAsset", self.ui)
        self.assertIn("caseImage.src", self.ui)
        self.assertIn("releaseImage", self.ui)
        self.assertNotIn("sessionStorage.setItem(\"image", self.ui)
        self.assertNotIn("sessionStorage.setItem('image", self.ui)

    def test_submit_locking_and_unsaved_warning_are_present(self) -> None:
        self.assertIn("submitDialog.showModal()", self.ui)
        self.assertIn('response_status === "SUBMITTED"', self.ui)
        self.assertIn("setFormLocked", self.ui)
        self.assertIn("beforeunload", self.ui)
        self.assertIn("window.confirm", self.ui)

    def test_ui_source_avoids_reviewer_and_research_metadata_literals(self) -> None:
        for forbidden in (
            "REV_A",
            "REV_B",
            "PRIMARY",
            "RELIABILITY",
            "RELIABILITY_25PCT",
            "ResearcherCaseMeta",
            "prediction score",
            "bbox",
            "asset_sha256",
            "review_asset_ref",
            "Drive file ID",
            "Drive folder ID",
        ):
            self.assertNotIn(forbidden, self.ui)
        self.assertNotIn(".innerHTML", self.ui)
        self.assertNotIn("eval(", self.ui)

    def test_local_preview_uses_fake_data_only(self) -> None:
        self.assertIn("isPreviewMode", self.ui)
        self.assertIn("mockRpc", self.ui)
        self.assertIn("DEMO_CASE_001", self.ui)
        self.assertIn("demoImageBase64", self.ui)


if __name__ == "__main__":
    unittest.main()
