from __future__ import annotations

import json
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
        self.lang = ""
        self.font_links: list[str] = []
        self.links: list[dict[str, str]] = []
        self.meta_robots = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.lang = attrs_dict.get("lang", "")
        if tag == "link":
            href = attrs_dict.get("href", "")
            if "fonts.googleapis.com/css2" in href:
                self.font_links.append(href)
        if tag == "a":
            self.links.append(attrs_dict)
        if tag == "meta" and attrs_dict.get("name") == "robots":
            self.meta_robots = attrs_dict.get("content", "")
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
        cls.payload = web_phase2.build_payload()
        cls.summary_html = (web_phase2.SUMMARY_DIR / "index.html").read_text(encoding="utf-8")
        cls.review_html = (web_phase2.REVIEW_DIR / "index.html").read_text(encoding="utf-8")
        cls.summary_css = (web_phase2.SUMMARY_DIR / "styles.css").read_text(encoding="utf-8")
        cls.summary_data = json.loads((web_phase2.SUMMARY_DIR / "data" / "summary-data.json").read_text(encoding="utf-8"))
        cls.review_data = json.loads((web_phase2.REVIEW_DIR / "data" / "review-data.json").read_text(encoding="utf-8"))

    def test_generated_outputs_match_authoritative_generator(self) -> None:
        self.assertEqual(web_phase2.render_summary_page(self.payload), self.summary_html)
        self.assertEqual(web_phase2.render_review_page(self.payload), self.review_html)
        self.assertEqual(web_phase2.shared_css(), self.summary_css)

    def test_summary_html_lang_is_thai_and_sarabun_only(self) -> None:
        parser = _StructureParser()
        parser.feed(self.summary_html)
        self.assertEqual("th", parser.lang)
        self.assertEqual(1, len(parser.font_links))
        self.assertIn("family=Sarabun", parser.font_links[0])
        self.assertNotIn("Atkinson", self.summary_html + self.summary_css)
        self.assertNotIn("Hyperlegible", self.summary_html + self.summary_css)
        self.assertIn('font-family: "Sarabun", Tahoma, sans-serif', self.summary_css)

    def test_page_is_thai_first_research_book(self) -> None:
        thai_chars = len(re.findall(r"[\u0E00-\u0E7F]", self.summary_html))
        ascii_words = len(re.findall(r"\b[A-Za-z][A-Za-z-]{2,}\b", self.summary_html))
        self.assertGreater(thai_chars, ascii_words * 2)
        for value in (
            "หนังสือสรุปงานวิจัย",
            "โครงการนี้ทำอะไร และทำไมต้องทำ",
            "ชุดข้อมูล 240 คู่ภาพ และ Marker 7,115 จุด",
            "เส้นทางการทดลองอย่างเป็นระบบ E00-E22",
            "ทำไม 1,029 Unmatched จึงยังไม่ควรถูกเรียกว่า False Positive",
            "อภิธานศัพท์ ข้อจำกัด และสิ่งที่จะทำต่อ",
            "สารบัญ",
            "book-layout",
            "toc",
        ):
            self.assertIn(value, self.summary_html)
        for old_heading in ("FACT", "INTERPRETATION", "CURRENT STATUS", "SYSTEMATIC EXPERIMENTS", "SECURITY / INTEGRITY"):
            self.assertNotIn(f">{old_heading}<", self.summary_html)

    def test_reviewer_web_app_cta_is_preserved_and_safe(self) -> None:
        parser = _StructureParser()
        parser.feed(self.summary_html)
        matching_links = [link for link in parser.links if link.get("href") == REVIEWER_WEB_APP_URL]
        self.assertEqual(1, len(matching_links))
        self.assertEqual("_blank", matching_links[0].get("target"))
        self.assertEqual("noopener noreferrer", matching_links[0].get("rel"))
        self.assertIn("เปิดระบบ Expert Review", self.summary_html)
        self.assertIn("สำหรับผู้ประเมินที่ได้รับ Access Token เท่านั้น", self.summary_html)

    def test_e22_values_are_present_and_unchanged(self) -> None:
        expected = {
            "test_source_image_count": 36,
            "test_tile_count": 432,
            "test_gt_count": 918,
            "tp": 536,
            "fn": 382,
            "prediction_count": 1565,
            "unmatched": 1029,
            "recall": 0.5838779956,
            "precision_proxy": 0.3424920128,
            "f1": 0.4317358035,
            "f2": 0.5117433645,
        }
        for key, value in expected.items():
            self.assertEqual(value, self.summary_data["e22"][key])
        self.assertEqual(0.0590570586, self.summary_data["e22"]["project_ap"])
        for value in (
            "36",
            "432",
            "918",
            "536",
            "382",
            "1,565",
            "1,029",
            "0.5838779956 ≈ 58.4%",
            "0.3424920128 ≈ 34.2%",
            "0.4317358035",
            "0.5117433645",
            "0.0590570586",
            "GENERALIZATION_CONSISTENT",
        ):
            self.assertIn(value, self.summary_html)

    def test_tile_semantics_are_locked(self) -> None:
        self.assertIn("ACTUAL MODEL-INPUT VALIDATION TILES = 432", self.summary_html)
        self.assertIn("468 = 36 source-image opens + 432 tile-image inference opens", self.summary_html)
        self.assertNotRegex(self.summary_html, re.compile(r"468\s+(actual\s+)?(model-input|inference|validation)\s+tiles", re.IGNORECASE))

    def test_model_metric_cautions_are_present(self) -> None:
        for value in (
            "Precision proxy",
            "annotation-relative",
            "ไม่ใช่ expert-confirmed precision",
            "PROJECT_AP",
            "ไม่ใช่ COCO AP, AP50, AP75 หรือ AP-small",
            "ไม่ใช่ production accuracy",
            "production-ready",
            "high-accuracy automated QC",
        ):
            self.assertIn(value, self.summary_html)

    def test_experiment_journey_covers_required_milestones(self) -> None:
        for value in (
            "E00 Baseline",
            "E03 Anchors 8 / 16 / 32 / 64",
            "E04 Larger anchors",
            "E06 RPN proposal budget",
            "E10 ROI / score diagnostic",
            "E12 / E13 / E14 Learning control",
            "E15 Partial backbone unfreeze",
            "E16 / E17 Augmentation",
            "E19 Higher input resolution",
            "E20 Frontier finalist selection",
            "E21 Five-seed robustness",
            "DURATION-R1 Training duration",
            "SATURATION-R2 / Model Lock",
            "E22 Untouched Final Test",
            "คำถามที่ทดสอบ",
            "สิ่งที่เปลี่ยน",
            "ผลที่พบ",
            "E00 MULTISEED_LEADER",
            "4 epochs = REGRESSION",
        ):
            self.assertIn(value, self.summary_html)

    def test_expert_review_values_and_status_are_unchanged(self) -> None:
        expert = self.summary_data["expert_review"]
        self.assertEqual(1169, expert["cases"]["total"])
        self.assertEqual(1029, expert["cases"]["unmatched_model_only"])
        self.assertEqual(60, expert["cases"]["tp_controls"])
        self.assertEqual(80, expert["cases"]["fn_controls"])
        self.assertEqual(1169, expert["rev_a_assignments"])
        self.assertEqual(292, expert["rev_b_assignments"])
        self.assertEqual("LAUNCHED_IN_PROGRESS", self.summary_data["expert_review_status"])
        for value in (
            "EXPERT REVIEW: LAUNCHED / IN PROGRESS",
            "REV_A",
            "1,169 cases",
            "REV_B",
            "292 cases",
            "257",
            "15",
            "Q1-Q4: 5 each",
            "NOT YET CALCULATED",
            "ณ เวลาตรวจสอบก่อนเริ่มการประเมินจริง",
        ):
            self.assertIn(value, self.summary_html)

    def test_asset_verification_and_auth_status_are_present(self) -> None:
        for value in (
            "Expected assets",
            "1,169 / 1,169",
            "SHA-256 verified",
            "Missing",
            "Mismatch",
            "Duplicates",
            "Invalid MIME",
            "Internal errors",
            "server-side authorization",
            "reviewer assignment check",
            "private asset delivery",
        ):
            self.assertIn(value, self.summary_html)

    def test_public_pages_do_not_expose_secrets_or_private_ids(self) -> None:
        combined = "\n".join(
            [
                self.summary_html,
                self.review_html,
                json.dumps(self.summary_data, ensure_ascii=False),
                json.dumps(self.review_data, ensure_ascii=False),
            ]
        )
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
            "Drive folder IDs",
            "token hash",
            "token hashes",
        )
        for term in forbidden:
            self.assertNotIn(term, combined)

        hex_values = set(re.findall(r"\b[a-f0-9]{64}\b", combined))
        self.assertEqual({web_phase2.LOCKED_CHECKPOINT_SHA256}, hex_values)

    def test_old_review_public_index_is_retired(self) -> None:
        parser = _StructureParser()
        parser.feed(self.review_html)
        self.assertEqual("th", parser.lang)
        self.assertIn("noindex,nofollow", parser.meta_robots)
        self.assertIn("../anchor-experiment-summary/", self.review_html)
        self.assertIn("หน้านี้เลิกใช้งานแล้ว", self.review_html)
        self.assertNotIn("Expert Review - 1,169 Cases", self.review_html)
        self.assertEqual("RETIRED", self.review_data["status"])

    def test_old_apps_script_and_reviewer_ui_sources_remain_present(self) -> None:
        gas_dir = web_phase2.REVIEW_DIR / "google-apps-script"
        for name in ("ReviewerUIV2.html", "ExpertReviewV2.gs", "Code.gs", "appsscript.json"):
            self.assertTrue((gas_dir / name).exists())

    def test_responsive_and_accessibility_css_is_present(self) -> None:
        for value in (
            "min-width: 320px",
            "@media (max-width: 1024px)",
            "@media (max-width: 720px)",
            "@media (max-width: 360px)",
            "@media print",
            "prefers-reduced-motion",
            "focus-visible",
            "min-height: 44px",
            "grid-template-columns: 250px minmax(0, 1fr)",
            "max-width: var(--measure)",
        ):
            self.assertIn(value, self.summary_css)

    def test_html_is_structurally_valid(self) -> None:
        for source in (self.summary_html, self.review_html):
            parser = _StructureParser()
            parser.feed(source)
            self.assertEqual([], parser.errors)
            self.assertEqual([], parser.stack)


if __name__ == "__main__":
    unittest.main()
