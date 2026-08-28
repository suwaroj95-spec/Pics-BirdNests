from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser

from tools import build_web_phase2_pages as web_phase2


REVIEWER_WEB_APP_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbxr5yysjT4AOmUvy_VX4IfobRHAELHp3ZfklGK5xafB2GErI-hlWnfJ0cGmcF6AA4Ex"
    "/exec?ui=v2"
)


class _StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []
        self.links: list[str] = []
        self.meta_robots = ""
        self.meta_refresh = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        if tag == "a":
            self.links.append(attrs_dict.get("href", ""))
        if tag == "meta" and attrs_dict.get("name") == "robots":
            self.meta_robots = attrs_dict.get("content", "")
        if tag == "meta" and attrs_dict.get("http-equiv") == "refresh":
            self.meta_refresh = attrs_dict.get("content", "")
        if tag not in {"meta", "link", "br", "img", "input"}:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"meta", "link", "br", "img", "input"}:
            return
        if not self.stack:
            self.errors.append(f"unexpected closing tag: {tag}")
            return
        current = self.stack.pop()
        if current != tag:
            self.errors.append(f"expected closing {current}, got {tag}")


class WebPhase2PagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        web_phase2.build()
        cls.summary_html = (web_phase2.SUMMARY_DIR / "index.html").read_text(encoding="utf-8")
        cls.review_html = (web_phase2.REVIEW_DIR / "index.html").read_text(encoding="utf-8")
        cls.summary_css = (web_phase2.SUMMARY_DIR / "styles.css").read_text(encoding="utf-8")
        cls.summary_data = (web_phase2.SUMMARY_DIR / "data" / "summary-data.json").read_text(encoding="utf-8")
        cls.review_data = (web_phase2.REVIEW_DIR / "data" / "review-data.json").read_text(encoding="utf-8")
        cls.docs_index = (web_phase2.ROOT / "docs" / "index.html").read_text(encoding="utf-8")

    def test_summary_is_complete_through_expert_review_launch(self) -> None:
        for value in (
            "EXPERT REVIEW",
            "LAUNCHED",
            "IN PROGRESS",
            "Deep Research",
            "Dataset preparation",
            "Marker-derived Ground Truth",
            "Source-level split",
            "Faster R-CNN baseline",
            "Model Lock",
            "One-time untouched Final Test E22",
            "Production Reviewer UI",
            "Expert Review production launch",
        ):
            self.assertIn(value, self.summary_html)
        self.assertIn('"expert_review_status": "LAUNCHED_IN_PROGRESS"', self.summary_data)

    def test_e22_values_are_present_and_correct(self) -> None:
        for value in (
            "36",
            "432",
            "918",
            "536 / 382",
            "1,565",
            "0.583878",
            "58.4%",
            "0.342492",
            "34.2%",
            "1,029",
            "0.431736",
            "0.511743",
            "0.059057",
            "GENERALIZATION_CONSISTENT",
        ):
            self.assertIn(value, self.summary_html)
        self.assertIn("not COCO AP", self.summary_html)

    def test_tile_semantics_are_correct(self) -> None:
        self.assertIn("ACTUAL MODEL-INPUT VALIDATION TILES", self.summary_html)
        self.assertIn("<strong>432</strong>", self.summary_html)
        self.assertIn("468 = 36 source-image opens + 432 tile inference opens", self.summary_html)
        self.assertNotRegex(self.summary_html, re.compile(r"468\s+(actual\s+)?(model-input|inference)\s+tiles", re.IGNORECASE))

    def test_expert_review_counts_and_reviewer_workloads_are_present(self) -> None:
        for value in (
            "Total Expert Review cases",
            "1,169",
            "Unmatched/model-only",
            "1,029",
            "TP QC",
            "60",
            "FN controls",
            "80",
            "16 batches",
            "final 44",
            "REV_A workload",
            "REV_B workload",
            "292",
            "257",
            "15",
            "Q1-Q4, 5 each",
        ):
            self.assertIn(value, self.summary_html)

    def test_asset_verification_and_auth_status_are_present(self) -> None:
        for value in (
            "1,169 / 1,169",
            "Missing / mismatch / duplicate",
            "Invalid MIME / internal errors",
            "PRODUCTION AUTHENTICATION VERIFIED",
            "UNAUTHORIZED_REVIEWER",
            "REVIEWER_INACTIVE",
            "Responses / sessions created",
            "0 / 0",
        ):
            self.assertIn(value, self.summary_html)

    def test_reviewer_web_app_cta_is_present_and_safe(self) -> None:
        self.assertIn(REVIEWER_WEB_APP_URL, self.summary_html)
        self.assertIn('target="_blank"', self.summary_html)
        self.assertIn('rel="noopener noreferrer"', self.summary_html)
        self.assertIn("สำหรับผู้ประเมินที่ได้รับ Access Token เท่านั้น", self.summary_html)

    def test_public_pages_do_not_expose_secrets_or_private_ids(self) -> None:
        combined = "\n".join([self.summary_html, self.review_html, self.summary_data, self.review_data])
        forbidden = (
            "ERV2_REVIEWER_TOKEN_MAP_JSON",
            "Script Properties",
            "review_assets",
            "candidate_box",
            "candidate_x",
            "prediction_score",
            "fasterrcnn_prediction_cache",
            "original_image_path",
            "expert_review_researcher_manifest",
            "INVALID-TEST-TOKEN-NOT-REAL",
            "REV_A_TOKEN",
            "REV_B_TOKEN",
            "drive_folder_id",
            "drive_file_id",
            "webViewLink",
        )
        for term in forbidden:
            self.assertNotIn(term, combined)

    def test_public_docs_index_promotes_summary_and_does_not_link_old_gallery(self) -> None:
        self.assertIn('href="anchor-experiment-summary/"', self.docs_index)
        self.assertIn("สรุปโครงการ BirdNests ฉบับสมบูรณ์", self.docs_index)
        self.assertNotIn('href="anchor-review-small-16-32-64-128/"', self.docs_index)

    def test_old_review_public_index_is_retired(self) -> None:
        parser = _StructureParser()
        parser.feed(self.review_html)
        self.assertIn("noindex,nofollow", parser.meta_robots)
        self.assertIn("../anchor-experiment-summary/", self.review_html)
        self.assertIn("หน้านี้เลิกใช้งานแล้ว", self.review_html)
        self.assertNotIn("Expert Review - 1,169 Cases", self.review_html)
        self.assertNotIn("Batch Structure", self.review_html)
        self.assertIn('"status": "RETIRED"', self.review_data)

    def test_old_apps_script_and_reviewer_ui_sources_remain_present(self) -> None:
        gas_dir = web_phase2.REVIEW_DIR / "google-apps-script"
        for name in ("ReviewerUIV2.html", "ExpertReviewV2.gs", "Code.gs", "appsscript.json"):
            self.assertTrue((gas_dir / name).exists())

    def test_responsive_html_is_structurally_valid(self) -> None:
        for source in (self.summary_html, self.review_html):
            parser = _StructureParser()
            parser.feed(source)
            self.assertEqual([], parser.errors)
            self.assertEqual([], parser.stack)
        for value in ("min-width: 320px", "@media (max-width: 720px)", "grid-template-columns", "focus-visible"):
            self.assertIn(value, self.summary_css)


if __name__ == "__main__":
    unittest.main()
