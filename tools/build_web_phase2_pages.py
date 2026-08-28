from __future__ import annotations

import html
import json
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "fasterrcnn_experiments"
SUMMARY_DIR = ROOT / "docs" / "anchor-experiment-summary"
REVIEW_DIR = ROOT / "docs" / "anchor-review-small-16-32-64-128"
REVIEWER_WEB_APP_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbxr5yysjT4AOmUvy_VX4IfobRHAELHp3ZfklGK5xafB2GErI-hlWnfJ0cGmcF6AA4Ex"
    "/exec?ui=v2"
)
LOCKED_CHECKPOINT_SHA256 = "54eb334d15a2e07ac715782bc6aa66a2d7d5921d13ddb3fac25c7bf853d05bdd"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def metric(exp_id: str) -> dict[str, Any]:
    return read_json(ARTIFACTS / exp_id / exp_id / "metrics.json")


def decision(exp_id: str) -> dict[str, Any]:
    return read_json(ARTIFACTS / exp_id / exp_id / "decision.json")


def build_payload() -> dict[str, Any]:
    e02 = read_json(ARTIFACTS / "E02-R1" / "E02-R1" / "runtime_anchor_proposal_diagnostic.json")
    e20 = read_json(ARTIFACTS / "E20-R1" / "E20-R1" / "e20_finalists.json")
    e21_ranking = read_json(ARTIFACTS / "E21-R1" / "E21-R1" / "e21_configuration_ranking.json")
    e21_summary = read_json(ARTIFACTS / "E21-R1" / "E21-R1" / "e21_multiseed_summary.json")
    duration = read_json(ARTIFACTS / "DURATION-R1" / "DURATION-R1" / "duration_analysis.json")
    duration_decision = read_json(ARTIFACTS / "DURATION-R1" / "DURATION-R1" / "duration_decision.json")
    saturation_r2 = read_json(ARTIFACTS / "SATURATION-R2" / "SATURATION-R2" / "final_saturation_reevaluation.json")
    e22 = read_json(ARTIFACTS / "E22-R1" / "E22-R1" / "e22_primary_metrics.json")
    e22_ap = read_json(ARTIFACTS / "E22-R1" / "E22-R1" / "e22_project_ap.json")
    e22_generalization = read_json(ARTIFACTS / "E22-R1" / "E22-R1" / "e22_generalization_assessment.json")
    e22_manifest = read_json(ARTIFACTS / "E22-R1" / "E22-R1" / "e22_result_manifest.json")
    expert = read_json(ARTIFACTS / "EXPERT-REVIEW-R1" / "expert_review_summary.json")
    sampling = read_json(ARTIFACTS / "EXPERT-REVIEW-R1" / "expert_review_sampling_manifest.json")
    batches = read_json(ARTIFACTS / "EXPERT-REVIEW-R1" / "expert_review_batch_manifest.json")
    auth = read_json(ARTIFACTS / "EXPERT-REVIEW-R1" / "controlled_auth_smoke_test_20260827.json")

    epoch2 = duration["epoch2_metrics"]
    epoch4 = duration["epoch4_metrics"]
    duration_means = {
        "epoch2_recall": mean(float(row["recall"]) for row in epoch2),
        "epoch4_recall": mean(float(row["recall"]) for row in epoch4),
        "epoch2_unmatched": mean(float(row["unmatched"]) for row in epoch2),
        "epoch4_unmatched": mean(float(row["unmatched"]) for row in epoch4),
    }

    families = [
        ("A", "Anchor geometry", "E00-E05", "E00 baseline established the incumbent. E03 anchors 8/16/32/64 raised recall substantially but unmatched predictions increased greatly, so the result was HOLD. E04 larger anchors regressed."),
        ("B", "RPN / proposals", "E06-E09", f"E06 showed proposal recall improved when the RPN budget increased; E02 current-budget proposal recall@0.50 was {fmt(e02['proposal_recall']['1000']['iou_0_50'])}. The final detector still remained budget/score limited."),
        ("C", "ROI / score behavior", "E10", f"E10 found POSTPROCESSING_SATURATED and {decision('E10-ROI-DIAG-R1')['decision']}: localization was usable, but score discrimination was limited."),
        ("D", "Learning rate and scheduler", "E12-E14", "E12 LR 0.0025 regressed. E13 LR 0.010 improved recall but produced excessive unmatched predictions. E14 scheduler was HOLD."),
        ("E", "Partial backbone unfreeze", "E15", f"E15 reached very high single-run recall {fmt(float(metric('E15-R1')['recall']))}, but score inflation and {fmt(int(metric('E15-R1')['unmatched_predictions']))} unmatched predictions made it HOLD."),
        ("F", "Augmentation", "E16-E17", "Horizontal flip did not provide meaningful improvement. Brightness/contrast augmentation regressed the operating trade-off."),
        ("G", "Input resolution", "E19", "Higher input resolution was promising, but not stable enough at the operating threshold to replace the incumbent."),
        ("H", "Threshold/frontier analysis", "E20", f"E20 compared calibrated frontier finalists: E19 @ {e20[1]['candidate_threshold']} and E15 @ {e20[2]['candidate_threshold']} were sent to multi-seed confirmation."),
        ("I", "Multi-seed robustness", "E21", f"Five-seed study concluded {e21_ranking['classifications']['E00']}. Single-run improvements were not reliable enough across seeds."),
        ("J", "Training duration", "DURATION-R1", f"Four epochs raised mean recall to {fmt(duration_means['epoch4_recall'], 4)} but unmatched predictions rose to {fmt(duration_means['epoch4_unmatched'], 1)}. Result: {duration_decision['duration_configuration_decision']}."),
        ("K", "Saturation / Model Lock", "SATURATION-R2", f"Final saturation was {saturation_r2['saturation_decision']['saturation_classification']} with {saturation_r2['saturation_decision']['model_lock_readiness']}."),
        ("L", "Final untouched test", "E22", f"One-time test: {e22['test_source_image_count']} source images, {e22['test_tile_count']} actual model-input tiles, GT {e22['test_gt_count']}, recall {fmt(e22['recall'], 10)}."),
    ]

    return {
        "families": families,
        "e21_summary": e21_summary,
        "e21_ranking": e21_ranking,
        "duration_means": duration_means,
        "e22": e22,
        "e22_ap": e22_ap,
        "e22_generalization": e22_generalization,
        "lock": {
            "configuration": "E00_2_EPOCH",
            "seed": 20260713,
            "threshold": 0.125,
            "checkpoint_sha256": LOCKED_CHECKPOINT_SHA256,
            "one_time_test_completed": e22_manifest["one_time_test_completed"],
        },
        "expert": expert,
        "sampling": sampling,
        "batches": batches,
        "auth": auth,
        "sources": [
            "dataset marker registry and finalization artifacts",
            "E00-E22 Faster R-CNN experiment artifacts",
            "DURATION-R1 and SATURATION-R2 artifacts",
            "EXPERT-REVIEW-R1 manifests and launch-readiness evidence",
        ],
    }


def card(label: str, value: Any, note: str = "") -> str:
    return f'<article class="metric-card"><span>{html.escape(label)}</span><strong>{html.escape(str(value))}</strong><p>{html.escape(note)}</p></article>'


def tag_card(kind: str, title: str, body: str) -> str:
    return f'<article class="info-card"><span>{html.escape(kind)}</span><h3>{html.escape(title)}</h3><p>{html.escape(body)}</p></article>'


def render_summary_page(payload: dict[str, Any]) -> str:
    e22 = payload["e22"]
    expert = payload["expert"]
    batches = payload["batches"]
    e21 = payload["e21_summary"]
    decisions = {
        "CONFIRMED_DIRTY_SPOT": "ยืนยันว่าเป็นจุดสกปรก",
        "NOT_DIRTY_SPOT": "ไม่ใช่จุดสกปรก",
        "AMBIGUOUS": "ไม่แน่ชัด",
        "UNJUDGEABLE": "ไม่สามารถประเมินจากภาพได้",
        "ANNOTATION_LOCALIZATION_ISSUE": "ตำแหน่ง Annotation ไม่ตรงกับจุดสกปรก",
    }
    family_cards = "\n".join(
        f'<article class="timeline-card"><div><span>{fid}</span><h3>{html.escape(title)}</h3><p>{html.escape(exps)}</p></div><p>{html.escape(body)}</p></article>'
        for fid, title, exps, body in payload["families"]
    )
    decision_items = "\n".join(
        f"<li><code>{html.escape(code)}</code><span>{html.escape(label)}</span></li>"
        for code, label in decisions.items()
    )
    workflow = [
        "Deep Research", "Dataset preparation", "Marker-derived Ground Truth",
        "Source-level split", "Tiling", "Faster R-CNN baseline",
        "Systematic experiments E00-E21", "Multi-seed confirmation",
        "Duration / saturation research", "Model Lock",
        "One-time untouched Final Test E22", "Error interpretation",
        "Expert Review protocol", "Reviewer setup", "Private asset verification",
        "Reviewer authentication", "Production Reviewer UI", "EXPERT REVIEW LAUNCHED",
    ]
    workflow_html = "\n".join(f"<li>{html.escape(item)}</li>" for item in workflow)
    multiseed_cards = "\n".join(
        card(exp, f"Recall {fmt(e21[exp]['recall']['mean'], 3)}", f"Precision proxy {fmt(e21[exp]['precision_proxy']['mean'], 3)} / F2 {fmt(e21[exp]['f2']['mean'], 3)}")
        for exp in ("E00", "E19", "E15")
    )
    return f"""<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BirdNests Expert Review Launched - Complete Research Narrative</title>
  <meta name="description" content="Thai-first scientific infographic for the Pics-BirdNests Faster R-CNN research prototype through Expert Review launch and in-progress human review.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Sarabun:wght@400;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <a class="skip-link" href="#main">ข้ามไปเนื้อหา</a>
  <header class="site-header">
    <nav class="topbar" aria-label="Section navigation">
      <a href="../">Docs Home</a>
      <a href="#overview">ภาพรวม</a>
      <a href="#data">ข้อมูล</a>
      <a href="#experiments">การทดลอง</a>
      <a href="#model-lock">Model Lock</a>
      <a href="#e22">E22 Final Test</a>
      <a href="#expert-review">Expert Review</a>
      <a href="#current-status">สถานะปัจจุบัน</a>
    </nav>
    <section class="hero" id="overview">
      <p class="eyebrow">ENGINEERING / RESEARCH PROTOTYPE</p>
      <h1>BirdNests Faster R-CNN: จากงานวิจัยสู่ Expert Review ที่เปิดใช้งานแล้ว</h1>
      <p class="subtitle">สรุปสาธารณะของโครงการตรวจจับ candidate dirty spots ในภาพรังนก ตั้งแต่ Deep Research, dataset, systematic experiments E00-E22, model lock, final untouched test, ไปจนถึงระบบ Expert Review production launch.</p>
      <div class="status-banner" aria-label="Expert Review current status">
        <span>EXPERT REVIEW: LAUNCHED / IN PROGRESS</span>
        <strong>LAUNCHED</strong>
        <em>IN PROGRESS</em>
      </div>
      <div class="hero-actions">
        <a class="cta" href="{REVIEWER_WEB_APP_URL}" target="_blank" rel="noopener noreferrer">เปิดระบบ Expert Review</a>
        <p>สำหรับผู้ประเมินที่ได้รับ Access Token เท่านั้น</p>
      </div>
      <div class="hero-grid">
        {card("Raw / marker image pairs", "240", "คู่ภาพต้นฉบับและภาพ marker")}
        {card("Historical marker points", "7,115", "positive reference source")}
        {card("Locked model", payload["lock"]["configuration"], "seed 20260713 / threshold 0.125")}
        {card("Expert Review", "LAUNCHED / IN PROGRESS", "results are not final yet")}
      </div>
    </section>
  </header>
  <main id="main">
    <section class="section" id="data">
      <div class="section-heading"><p class="section-kicker">FACT</p><h2>Dataset และความหมายของ marker</h2></div>
      <div class="split">
        <div>
          <p>โครงการนี้ศึกษาการตรวจจับ <strong>candidate dirty spots</strong> ในภาพรังนกด้วย computer vision โดยรักษา scientific traceability ตลอด workflow.</p>
          <p>ภาพ marker ในอดีตถูกใช้เป็นแหล่งอ้างอิงเชิงบวก: <strong>marker presence = positive reference</strong>. แต่ <strong>marker absence ไม่เท่ากับ confirmed negative</strong> จึงห้ามสรุปว่า prediction ที่ไม่ตรง marker เป็น false positive โดยอัตโนมัติ.</p>
        </div>
        <div class="metric-grid small">{card("Pairs", "240")}{card("Markers", "7,115")}{card("System label", "Research prototype")}</div>
      </div>
    </section>
    <section class="section">
      <div class="section-heading"><p class="section-kicker">FACT</p><h2>Source-level split และ tiling</h2></div>
      <p>ใช้ source-level split เพื่อป้องกัน leakage ระหว่าง train / validation / test. ภาพถูกตัดเป็น tile สำหรับโมเดลด้วย tile size = <strong>512</strong>, overlap = <strong>128</strong>, stride = <strong>384</strong>.</p>
      <div class="notice strong">ACTUAL MODEL-INPUT VALIDATION TILES = <strong>432</strong>. ค่า historical 468 ไม่ใช่จำนวน tile input สำหรับ inference: 468 = 36 source-image opens + 432 tile inference opens.</div>
    </section>
    <section class="section">
      <div class="section-heading"><p class="section-kicker">MODEL</p><h2>Faster R-CNN MobileNetV3-Large-FPN</h2></div>
      <p>โมเดลเป็น Faster R-CNN แบบ 2 classes. อธิบายแบบง่าย: Faster R-CNN จะหา candidate regions ก่อน แล้วประเมินว่าแต่ละตำแหน่งน่าจะเป็นจุดสกปรกหรือไม่ พร้อมกรอบตำแหน่งโดยประมาณ.</p>
      <details><summary>รายละเอียดทางเทคนิค</summary><p>Backbone คือ MobileNetV3-Large-FPN. การทดลองควบคุม anchor geometry, RPN proposal behavior, ROI score behavior, learning rate, scheduler, backbone unfreeze, augmentation, input resolution, threshold frontier, seeds, และ training duration.</p></details>
    </section>
    <section class="section" id="experiments">
      <div class="section-heading"><p class="section-kicker">INTERPRETATION</p><h2>Systematic experiments E00-E22</h2></div>
      <ol class="workflow">{workflow_html}</ol>
      <div class="timeline-grid">{family_cards}</div>
    </section>
    <section class="section">
      <div class="section-heading"><p class="section-kicker">FACT + LIMITATION</p><h2>Five-seed robustness: E00, E19, E15</h2></div>
      <p>แม้บาง single-run จะดูดีกว่า แต่ promotion criteria ไม่ผ่านอย่างสม่ำเสมอข้าม random seeds. ดังนั้น E21 สรุปว่า <strong>E00 MULTISEED_LEADER</strong>; single-run improvements ยังไม่ reproducible พอสำหรับ lock.</p>
      <div class="metric-grid">{multiseed_cards}</div>
    </section>
    <section class="section">
      <div class="section-heading"><p class="section-kicker">INTERPRETATION</p><h2>Training duration: ฝึกนานขึ้นไม่ได้แปลว่าดีขึ้นเสมอไป</h2></div>
      <div class="metric-grid">{card("2 epochs recall mean", fmt(payload["duration_means"]["epoch2_recall"], 4), f"unmatched {fmt(payload['duration_means']['epoch2_unmatched'], 1)}")}{card("4 epochs recall mean", fmt(payload["duration_means"]["epoch4_recall"], 4), f"unmatched {fmt(payload['duration_means']['epoch4_unmatched'], 1)}")}{card("Conclusion", "4 epochs = REGRESSION", "2 epochs retained")}</div>
    </section>
    <section class="section lock" id="model-lock">
      <div class="section-heading"><p class="section-kicker">MODEL LOCK</p><h2>Frozen before final test access</h2></div>
      <div class="metric-grid">{card("Configuration", payload["lock"]["configuration"])}{card("Seed", payload["lock"]["seed"])}{card("Threshold", payload["lock"]["threshold"])}{card("Checkpoint SHA256", "54eb334d15a2...d05bdd", "full hash below")}</div>
      <details><summary>Full checkpoint SHA256</summary><code>{LOCKED_CHECKPOINT_SHA256}</code></details>
      <p class="notice">After Model Lock: NO further model tuning, NO threshold retuning, and NO test-set-driven changes.</p>
    </section>
    <section class="section" id="e22">
      <div class="section-heading"><p class="section-kicker">FACT</p><h2>E22 one-time untouched Final Test</h2></div>
      <div class="metric-grid">{card("Source images", e22["test_source_image_count"])}{card("Actual model-input tiles", e22["test_tile_count"])}{card("GT", e22["test_gt_count"])}{card("TP / FN", f"{e22['tp']} / {e22['fn']}")}{card("Predictions", fmt(e22["prediction_count"]))}{card("Recall", f"{fmt(e22['recall'], 6)} / {pct(e22['recall'])}")}{card("Precision proxy", f"{fmt(e22['precision_proxy'], 6)} / {pct(e22['precision_proxy'])}", "annotation-relative")}{card("Unmatched", fmt(e22["unmatched"]))}{card("F1", fmt(e22["f1"], 6))}{card("F2", fmt(e22["f2"], 6))}{card("PROJECT_AP", fmt(payload["e22_ap"]["project_ap"], 6), "annotation-relative project metric")}{card("Assessment", payload["e22_generalization"]["classification"])}</div>
      <div class="notice">PROJECT_AP is an annotation-relative project metric. It is not COCO AP and is NOT full COCO AP / AP50 / AP75 / AP-small. Precision proxy is annotation-relative and is NOT expert-confirmed precision.</div>
      <p>Selected validation seed recall ≈ 0.5792 and final test recall ≈ 0.5839, so the locked model generalized consistently relative to validation behavior. This does not mean 58.4% recall is production-grade.</p>
    </section>
    <section class="section" id="expert-review">
      <div class="section-heading"><p class="section-kicker">WHY EXPERT REVIEW</p><h2>Unmatched/model-only predictions are scientifically unresolved</h2></div>
      <p>E22 produced <strong>1,029 unmatched/model-only predictions</strong>. Because marker absence is not confirmed negative evidence, these cases must be reviewed by humans before being interpreted.</p>
      <div class="info-grid">{tag_card("possible outcome", "real dirty spot", "จุดสกปรกจริงที่ marker เดิมอาจไม่ได้ระบุ")}{tag_card("possible outcome", "real false positive", "โมเดลเสนอ candidate ที่ไม่ใช่จุดสกปรก")}{tag_card("possible outcome", "ambiguous / unjudgeable", "ภาพไม่ชัดหรือประเมินไม่ได้")}{tag_card("possible outcome", "localization issue", "candidate กับ marker มีปัญหาตำแหน่ง")}</div>
    </section>
    <section class="section">
      <div class="section-heading"><p class="section-kicker">FACT</p><h2>EXPERT-REVIEW-R1 case package</h2></div>
      <div class="metric-grid">{card("Total Expert Review cases", fmt(expert["cases"]["total"]))}{card("Unmatched/model-only", fmt(expert["cases"]["unmatched_model_only"]))}{card("TP QC", expert["cases"]["tp_controls"])}{card("FN controls", expert["cases"]["fn_controls"], "Q1-Q4, 20 cases each")}{card("Batches", f"{batches['number_of_batches']} batches", "nominal 75 / final 44")}</div>
    </section>
    <section class="section">
      <div class="section-heading"><p class="section-kicker">HUMAN DECISION DEFINITIONS</p><h2>Allowed decisions and confidence</h2></div>
      <ul class="decision-list">{decision_items}</ul>
      <p class="confidence-row"><strong>Confidence:</strong> <span>HIGH</span><span>MEDIUM</span><span>LOW</span></p>
      <p>Model score is intentionally hidden from reviewers.</p>
    </section>
    <section class="section">
      <div class="section-heading"><p class="section-kicker">REVIEWER DESIGN</p><h2>PRIMARY_PLUS_RELIABILITY_SUBSET</h2></div>
      <div class="metric-grid">{card("REV_A workload", "1,169", "all review cases")}{card("REV_B workload", "292", "deterministic reliability subset")}{card("REV_B unmatched", "257")}{card("REV_B TP QC", "15")}{card("REV_B FN controls", "20", "Q1-Q4, 5 each")}</div>
      <p>The second reviewer evaluates a deterministic reliability subset to estimate inter-rater agreement while reducing total expert workload. Reviewer identities and operational tokens are not public.</p>
    </section>
    <section class="section">
      <div class="section-heading"><p class="section-kicker">AGREEMENT PLAN</p><h2>Agreement analysis is not yet calculated</h2></div>
      <p>On the 292 shared cases, the project will calculate raw agreement and Cohen's kappa before adjudication. Status: <strong>NOT YET CALCULATED</strong> because Expert Review is still in progress.</p>
    </section>
    <section class="section">
      <div class="section-heading"><p class="section-kicker">SECURITY / INTEGRITY</p><h2>Private asset verification and reviewer system</h2></div>
      <div class="metric-grid">{card("Expected review assets", "1,169")}{card("Inventory matched", "1,169 / 1,169")}{card("SHA-256 verified", "1,169 / 1,169")}{card("Missing / mismatch / duplicate", "0 / 0 / 0")}{card("Invalid MIME / internal errors", "0 / 0")}</div>
      <p>Private review images are served only after server-side authorization. The system flow is: public Web App login page → Access Token → server-side SHA-256 token mapping → reviewer authorization → assignment validation → private image retrieval → review decision.</p>
      <p>No raw reviewer token is stored in GitHub, Google Sheet, URL, or localStorage.</p>
    </section>
    <section class="section">
      <div class="section-heading"><p class="section-kicker">PRODUCTION AUTHENTICATION TEST</p><h2>Authentication verified before launch</h2></div>
      <div class="metric-grid">{card("Invalid token", payload["auth"]["invalid_token_result"]["error_code"], "correctly rejected")}{card("Valid REV_A token while inactive", payload["auth"]["rev_a_valid_token_result"]["error_code"], "recognized but blocked")}{card("Valid REV_B token while inactive", payload["auth"]["rev_b_valid_token_result"]["error_code"], "recognized but blocked")}{card("Responses / sessions created", "0 / 0")}</div>
      <p><strong>PRODUCTION AUTHENTICATION VERIFIED.</strong> No raw tokens or secret digest values are published.</p>
    </section>
    <section class="section launched">
      <div class="section-heading"><p class="section-kicker">CURRENT STATUS</p><h2>EXPERT REVIEW LAUNCHED</h2></div>
      <div class="metric-grid">{card("REV_A active", "TRUE")}{card("REV_B active", "TRUE")}{card("launch_gate_status", "REVIEW_LAUNCHED")}{card("review_start_enabled", "TRUE")}{card("REV_A smoke test", "Case 1 of 1,169 loaded successfully")}{card("REV_B smoke test", "Case 1 of 292 loaded successfully")}{card("At production launch verification", "ReviewResponses = 0")}{card("At production launch verification", "ReviewSessionsV2 = 0")}</div>
      <p>Private images loaded successfully in the no-submit production smoke test. Status after this milestone: <strong>EXPERT REVIEW IN PROGRESS</strong>.</p>
    </section>
    <section class="section" id="current-status">
      <div class="section-heading"><p class="section-kicker">CURRENT PROJECT STATUS</p><h2>Completed now, final scientific conclusion later</h2></div>
      <div class="status-columns">
        <article><h3>Completed</h3><ul><li>Dataset preparation</li><li>Ground-truth pipeline</li><li>Source-level split</li><li>Faster R-CNN systematic experiments</li><li>Multi-seed validation</li><li>Duration research</li><li>Model lock</li><li>One-time untouched test E22</li><li>Expert Review protocol</li><li>Reviewer assignment freeze</li><li>Private asset integrity verification</li><li>Production reviewer authentication</li><li>Reviewer UI deployment</li><li>Expert Review production launch</li></ul></article>
        <article><h3>Current</h3><p><strong>Expert Review - IN PROGRESS</strong></p></article>
        <article><h3>Next</h3><p>Expert Review completion → agreement analysis → Cohen's kappa → adjudication where required → annotation-corrected interpretation → final scientific conclusion.</p></article>
      </div>
    </section>
  </main>
  <footer>Public scientific summary. Expert Review results are not final. No private review assets, raw tokens, secret digest values, Drive private folder IDs, or researcher-only metadata are published.</footer>
</body>
</html>
"""


def render_review_page(_payload: dict[str, Any]) -> str:
    return """<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <meta http-equiv="refresh" content="3; url=../anchor-experiment-summary/">
  <title>หน้านี้เลิกใช้งานแล้ว</title>
  <style>
    * { box-sizing: border-box; }
    body { min-width: 320px; margin: 0; font-family: "Segoe UI", Tahoma, sans-serif; color: #0f172a; background: #f8fafc; line-height: 1.6; }
    main { width: min(720px, calc(100% - 32px)); margin: 12vh auto; padding: 24px; background: #fff; border: 1px solid #dbe4ee; border-radius: 8px; }
    a { color: #0369a1; font-weight: 700; }
  </style>
  <script>
    window.setTimeout(function () {
      window.location.replace("../anchor-experiment-summary/");
    }, 600);
  </script>
</head>
<body>
  <main>
    <h1>หน้านี้เลิกใช้งานแล้ว</h1>
    <p>Public review gallery เดิมถูก retire ออกจาก workflow ปัจจุบันแล้ว และไม่มีการแสดงชุดภาพ review ผ่านหน้านี้อีกต่อไป</p>
    <p>กำลังพาไปยัง <a href="../anchor-experiment-summary/">สรุปโครงการฉบับปัจจุบัน</a></p>
  </main>
</body>
</html>
"""


def shared_css() -> str:
    return """ :root {
  --ink: #0f172a;
  --muted: #475569;
  --body: #334155;
  --soft: #f8fafc;
  --paper: #ffffff;
  --line: #dbe4ee;
  --blue: #0369a1;
  --blue-soft: #e0f2fe;
  --green: #047857;
  --green-soft: #dcfce7;
  --amber-soft: #fef3c7;
  --radius: 8px;
  --shadow: 0 14px 38px rgba(15, 23, 42, 0.08);
  --max: 1180px;
}
* { box-sizing: border-box; }
html { min-width: 320px; scroll-behavior: smooth; background: var(--soft); }
body { margin: 0; color: var(--ink); background: var(--soft); font-family: "Atkinson Hyperlegible", "Sarabun", "Segoe UI", Arial, sans-serif; font-size: 17px; line-height: 1.68; letter-spacing: 0; }
body, a, button, td, th, code { overflow-wrap: break-word; }
a { color: inherit; }
.skip-link { position: fixed; left: 16px; top: 16px; z-index: 100; transform: translateY(-160%); padding: 9px 12px; color: #fff; background: var(--ink); border-radius: var(--radius); }
.skip-link:focus { transform: translateY(0); outline: 4px solid #bae6fd; }
.site-header { background: linear-gradient(180deg, #ffffff 0%, #ecfeff 100%); border-bottom: 1px solid var(--line); }
.topbar { position: sticky; top: 0; z-index: 20; width: min(var(--max), calc(100% - 32px)); margin: 0 auto; padding: 12px 0; display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 8px; background: rgba(248, 250, 252, 0.92); backdrop-filter: blur(12px); }
.topbar a { min-height: 40px; display: inline-flex; align-items: center; padding: 8px 11px; color: var(--blue); background: #fff; border: 1px solid var(--line); border-radius: var(--radius); font-weight: 800; font-size: 0.92rem; text-decoration: none; cursor: pointer; transition: border-color 180ms ease, background 180ms ease; }
.topbar a:focus-visible, .topbar a:hover, .cta:focus-visible, .cta:hover { outline: 3px solid rgba(3, 105, 161, 0.24); border-color: #7dd3fc; }
.hero { width: min(var(--max), calc(100% - 32px)); margin: 0 auto; padding: clamp(28px, 5vw, 64px) 0 clamp(26px, 4vw, 50px); }
.eyebrow, .section-kicker { margin: 0 0 8px; color: var(--blue); font-size: 0.82rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0; }
h1, h2, h3, p { margin-top: 0; }
h1, h2, h3 { letter-spacing: 0; text-wrap: balance; }
h1 { max-width: 1020px; margin-bottom: 14px; font-size: clamp(2.05rem, 4.4vw, 4.15rem); line-height: 1.16; }
h2 { margin-bottom: 10px; font-size: clamp(1.42rem, 2.3vw, 2.1rem); line-height: 1.22; }
h3 { margin-bottom: 8px; font-size: 1.08rem; line-height: 1.36; }
.subtitle { max-width: 960px; margin-bottom: 20px; color: var(--body); font-size: clamp(1.03rem, 1.5vw, 1.22rem); }
main { width: min(var(--max), calc(100% - 32px)); margin: 20px auto 0; padding-bottom: 48px; display: grid; gap: 18px; }
.section { min-width: 0; padding: clamp(18px, 2.4vw, 28px); background: var(--paper); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow); }
.section-heading { margin-bottom: 14px; }
.status-banner { display: inline-grid; grid-template-columns: auto auto auto; gap: 10px; align-items: center; margin: 8px 0 18px; padding: 10px 14px; background: var(--green-soft); color: #064e3b; border: 1px solid #86efac; border-radius: var(--radius); font-weight: 800; }
.status-banner strong { font-size: clamp(1.4rem, 3vw, 2.4rem); line-height: 1; }
.status-banner em { font-style: normal; color: var(--green); }
.hero-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 20px; }
.hero-actions p { margin: 0; color: var(--muted); font-weight: 700; }
.cta { min-height: 48px; display: inline-flex; align-items: center; padding: 11px 16px; color: #fff; background: var(--blue); border: 1px solid var(--blue); border-radius: var(--radius); text-decoration: none; font-weight: 800; cursor: pointer; }
.hero-grid, .metric-grid, .info-grid, .timeline-grid, .status-columns { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }
.metric-grid.small { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
.metric-card, .info-card, .timeline-card, .status-columns article { min-width: 0; padding: 16px; background: #fff; border: 1px solid var(--line); border-radius: var(--radius); }
.metric-card span, .info-card > span { display: block; color: var(--muted); font-size: 0.86rem; font-weight: 800; }
.metric-card strong { display: block; margin: 5px 0; color: var(--ink); font-size: clamp(1.28rem, 2vw, 1.9rem); line-height: 1.12; }
.metric-card p, .info-card p, .timeline-card p { margin: 0; color: var(--body); }
.split { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(240px, 0.6fr); gap: 16px; align-items: start; }
.notice { padding: 14px 16px; background: var(--amber-soft); border: 1px solid #f0ce88; border-radius: var(--radius); color: #543b00; }
.notice.strong { font-size: 1.08rem; }
.workflow { list-style: none; counter-reset: step; margin: 0 0 18px; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }
.workflow li { counter-increment: step; min-width: 0; padding: 12px; background: var(--blue-soft); border: 1px solid #bae6fd; border-radius: var(--radius); font-weight: 800; }
.workflow li::before { content: counter(step, decimal-leading-zero); display: block; color: var(--blue); font-size: 0.78rem; }
.timeline-card div { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 8px; }
.timeline-card div > span { flex: 0 0 auto; width: 34px; height: 34px; display: inline-grid; place-items: center; color: #fff; background: var(--blue); border-radius: 50%; font-weight: 800; }
.timeline-card h3 { margin-bottom: 0; }
.timeline-card div p { color: var(--muted); font-weight: 800; }
details { margin-top: 12px; padding: 12px 14px; border: 1px solid var(--line); border-radius: var(--radius); background: #fff; }
summary { cursor: pointer; font-weight: 800; color: var(--blue); }
code { font-family: Consolas, "Courier New", monospace; }
.decision-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.decision-list li { display: grid; gap: 4px; padding: 14px; border: 1px solid var(--line); border-radius: var(--radius); background: #fff; }
.decision-list span { color: var(--body); }
.confidence-row { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.confidence-row span { padding: 6px 10px; background: var(--green-soft); color: var(--green); border-radius: var(--radius); font-weight: 800; }
.lock { border-color: #93c5fd; }
.launched { border-color: #86efac; background: linear-gradient(180deg, #fff 0%, #f0fdf4 100%); }
.status-columns ul { margin: 0; padding-left: 20px; }
footer { width: min(var(--max), calc(100% - 32px)); margin: 0 auto; padding: 26px 0 42px; color: var(--muted); }
@media (max-width: 720px) {
  body { font-size: 16px; }
  .topbar { justify-content: flex-start; }
  h1 { font-size: 2.25rem; line-height: 1.18; }
  .split { grid-template-columns: 1fr; }
  .status-banner { grid-template-columns: 1fr; }
  .metric-card strong { font-size: 1.35rem; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; }
}
"""


def write_public_data(payload: dict[str, Any]) -> None:
    summary_data = {
        "schema_version": 3,
        "route": "anchor-experiment-summary",
        "purpose": "complete_public_research_summary_through_expert_review_launch",
        "expert_review_status": "LAUNCHED_IN_PROGRESS",
        "reviewer_web_app_url": REVIEWER_WEB_APP_URL,
        "e22": payload["e22"],
        "lock": payload["lock"],
        "expert_review": {
            "cases": payload["expert"]["cases"],
            "reviewer_mode": "PRIMARY_PLUS_RELIABILITY_SUBSET",
            "rev_a_assignments": 1169,
            "rev_b_assignments": 292,
            "asset_verification": "1169/1169",
            "launch_gate_status": "REVIEW_LAUNCHED",
            "review_start_enabled": True,
            "results_final": False,
        },
        "artifact_sources": payload["sources"],
    }
    review_data = {
        "schema_version": 3,
        "route": "anchor-review-small-16-32-64-128",
        "purpose": "retired_public_review_gallery_redirect",
        "status": "RETIRED",
        "redirect_target": "../anchor-experiment-summary/",
    }
    write_text(SUMMARY_DIR / "data" / "summary-data.json", json.dumps(summary_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    write_text(REVIEW_DIR / "data" / "review-data.json", json.dumps(review_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def build() -> None:
    payload = build_payload()
    write_text(SUMMARY_DIR / "index.html", render_summary_page(payload))
    write_text(REVIEW_DIR / "index.html", render_review_page(payload))
    css = shared_css()
    write_text(SUMMARY_DIR / "styles.css", css)
    write_public_data(payload)


if __name__ == "__main__":
    build()
