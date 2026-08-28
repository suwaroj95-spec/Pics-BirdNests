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

    experiments = [
        {
            "chapter": "05.1",
            "title": "E00 Baseline",
            "question": "โมเดลตั้งต้นที่เรียบง่ายและควบคุมได้ให้พฤติกรรมพื้นฐานอย่างไร",
            "changed": "ใช้ Faster R-CNN configuration ตั้งต้นเป็นเส้นอ้างอิง",
            "result": "ให้ baseline ที่อธิบายได้และกลายเป็น incumbent สำหรับการเปรียบเทียบรอบต่อไป",
            "decision": "PROMOTED AS BASELINE",
        },
        {
            "chapter": "05.2",
            "title": "E03 Anchors 8 / 16 / 32 / 64",
            "question": "anchor ขนาดเล็กช่วยจับจุดเล็กในภาพรังนกได้มากขึ้นหรือไม่",
            "changed": "ปรับ anchor geometry ให้ละเอียดขึ้น",
            "result": "Recall ดีขึ้นชัดเจน แต่ unmatched predictions เพิ่มขึ้นมาก จึงยังไม่ใช่ trade-off ที่พร้อมใช้",
            "decision": "HOLD",
        },
        {
            "chapter": "05.3",
            "title": "E04 Larger anchors",
            "question": "anchor ใหญ่ขึ้นช่วยให้โมเดลมั่นคงขึ้นหรือไม่",
            "changed": "ขยาย anchor range ไปทางขนาดใหญ่",
            "result": "พฤติกรรมถดถอยเมื่อเทียบกับ baseline และไม่ได้แก้ปัญหาหลัก",
            "decision": "REGRESSION",
        },
        {
            "chapter": "05.4",
            "title": "E06 RPN proposal budget",
            "question": "ขั้นตอนเสนอ candidate region ถูกจำกัดด้วยจำนวน proposal หรือไม่",
            "changed": "เพิ่ม RPN proposal budget ในการวินิจฉัย",
            "result": f"Proposal recall ดีขึ้นเมื่อเพิ่ม budget; proposal recall@0.50 ที่ budget 1000 จาก E02 คือ {fmt(e02['proposal_recall']['1000']['iou_0_50'])}",
            "decision": "DIAGNOSTIC INSIGHT",
        },
        {
            "chapter": "05.5",
            "title": "E10 ROI / score diagnostic",
            "question": "ตำแหน่ง prediction ใช้งานได้หรือปัญหาอยู่ที่ score discrimination",
            "changed": "แยกตรวจ post-processing, ROI, และ score behavior",
            "result": f"พบ POSTPROCESSING_SATURATED และผลตัดสิน {decision('E10-ROI-DIAG-R1')['decision']}: localization พอใช้ได้ แต่ score ยังแยกคุณภาพ prediction ได้จำกัด",
            "decision": "DIAGNOSTIC HOLD",
        },
        {
            "chapter": "05.6",
            "title": "E12 / E13 / E14 Learning control",
            "question": "learning rate หรือ scheduler ช่วยยกระดับผลโดยไม่เพิ่ม unmatched มากเกินไปหรือไม่",
            "changed": "ทดสอบ LR 0.0025, LR 0.010 และ scheduler",
            "result": "E12 ถดถอย, E13 เพิ่ม Recall แต่ unmatched สูงเกินควบคุม, E14 ยังเป็น HOLD",
            "decision": "REGRESSION / HOLD",
        },
        {
            "chapter": "05.7",
            "title": "E15 Partial backbone unfreeze",
            "question": "ปลดล็อก backbone บางส่วนจะช่วยให้โมเดลเรียนรู้ features เฉพาะโดเมนได้ดีขึ้นหรือไม่",
            "changed": "partial backbone unfreeze",
            "result": f"single-run recall สูงมาก ({fmt(float(metric('E15-R1')['recall']))}) แต่เกิด score inflation และ unmatched {fmt(int(metric('E15-R1')['unmatched_predictions']))} รายการ",
            "decision": "HOLD",
        },
        {
            "chapter": "05.8",
            "title": "E16 / E17 Augmentation",
            "question": "augmentation แบบง่ายช่วย generalization หรือทำให้สัญญาณ marker อ่อนลง",
            "changed": "ทดสอบ horizontal flip และ brightness / contrast",
            "result": "horizontal flip ไม่ให้ improvement ที่มีนัยสำคัญ ส่วน brightness / contrast ทำให้ trade-off ถดถอย",
            "decision": "NO IMPROVEMENT / REGRESSION",
        },
        {
            "chapter": "05.9",
            "title": "E19 Higher input resolution",
            "question": "ภาพ input ที่ละเอียดขึ้นช่วยจับจุดเล็กได้ดีขึ้นหรือไม่",
            "changed": "เพิ่ม input resolution",
            "result": "ผลดูมีศักยภาพ แต่ยังไม่มั่นคงพอที่ operating threshold จะชนะ baseline อย่างปลอดภัย",
            "decision": "PROMISING BUT NOT LOCKED",
        },
        {
            "chapter": "05.10",
            "title": "E20 Frontier finalist selection",
            "question": "configuration ใดควรเข้าสู่การพิสูจน์แบบ multi-seed",
            "changed": "เปรียบเทียบ frontier finalists และ threshold candidates",
            "result": f"E19 @ {e20[1]['candidate_threshold']} และ E15 @ {e20[2]['candidate_threshold']} ถูกส่งต่อไปตรวจสอบความแข็งแรงกับหลาย seed",
            "decision": "FINALISTS SELECTED",
        },
        {
            "chapter": "05.11",
            "title": "E21 Five-seed robustness",
            "question": "ผลที่ดูดีในรอบเดียว reproducible ข้าม random seeds หรือไม่",
            "changed": "รัน E00, E19, E15 แบบ five-seed",
            "result": f"สรุปการจัดอันดับคือ {e21_ranking['classifications']['E00']} เพราะ improvement ของคู่แข่งยังไม่สม่ำเสมอพอเมื่อเทียบกับความเสี่ยง unmatched",
            "decision": "E00 MULTISEED_LEADER",
        },
        {
            "chapter": "07",
            "title": "DURATION-R1 Training duration",
            "question": "ฝึก 4 epochs ดีกว่า 2 epochs จริงหรือไม่",
            "changed": "เปรียบเทียบ 2 epochs กับ 4 epochs แบบ controlled",
            "result": f"4 epochs เพิ่ม mean Recall เป็น {fmt(duration_means['epoch4_recall'], 4)} แต่ unmatched เพิ่มเป็น {fmt(duration_means['epoch4_unmatched'], 1)} ทำให้ operating trade-off แย่ลง",
            "decision": duration_decision["duration_configuration_decision"],
        },
        {
            "chapter": "08",
            "title": "SATURATION-R2 / Model Lock",
            "question": "โมเดลพร้อมถูกล็อกก่อน Final Test หรือยัง",
            "changed": "ประเมิน saturation และ readiness ก่อนแตะ untouched test",
            "result": f"Final saturation = {saturation_r2['saturation_decision']['saturation_classification']} และ readiness = {saturation_r2['saturation_decision']['model_lock_readiness']}",
            "decision": "MODEL LOCK READY",
        },
        {
            "chapter": "09",
            "title": "E22 Untouched Final Test",
            "question": "เมื่อล็อกโมเดลแล้ว ผลบนชุดข้อมูลที่ไม่เคยใช้มาก่อนเป็นอย่างไร",
            "changed": "รัน one-time final test หลัง Model Lock",
            "result": f"{e22['test_source_image_count']} source images, {e22['test_tile_count']} actual model-input tiles, GT {e22['test_gt_count']}, Recall {fmt(e22['recall'], 10)}",
            "decision": "GENERALIZATION_CONSISTENT",
        },
    ]

    return {
        "experiments": experiments,
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
    return (
        '<article class="metric-card">'
        f"<span>{html.escape(str(label))}</span>"
        f"<strong>{html.escape(str(value))}</strong>"
        f"<p>{html.escape(str(note))}</p>"
        "</article>"
    )


def tag_card(kind: str, title: str, body: str) -> str:
    return (
        '<article class="info-card">'
        f"<span>{html.escape(kind)}</span>"
        f"<h3>{html.escape(title)}</h3>"
        f"<p>{html.escape(body)}</p>"
        "</article>"
    )


def render_summary_page(payload: dict[str, Any]) -> str:
    e22 = payload["e22"]
    expert = payload["expert"]
    batches = payload["batches"]
    e21 = payload["e21_summary"]
    duration_means = payload["duration_means"]

    chapters = [
        ("01", "โครงการนี้ทำอะไร", "purpose"),
        ("02", "ชุดข้อมูลและ Marker", "dataset"),
        ("03", "Split และ Tile", "split-tiling"),
        ("04", "โมเดลและตัวชี้วัด", "model-metrics"),
        ("05", "เส้นทาง E00-E22", "experiment-journey"),
        ("06", "Multi-seed", "multi-seed"),
        ("07", "Training Duration", "duration"),
        ("08", "Model Lock", "model-lock"),
        ("09", "E22 Final Test", "e22"),
        ("10", "ทำไมต้อง Expert Review", "why-review"),
        ("11", "ชุดเคส 1,169", "review-package"),
        ("12", "Reviewer A/B", "reviewer-design"),
        ("13", "ความปลอดภัย", "security"),
        ("14", "สถานะปัจจุบัน", "current-status"),
        ("15", "ข้อจำกัดและขั้นต่อไป", "next"),
    ]
    decisions = {
        "CONFIRMED_DIRTY_SPOT": "ยืนยันว่าเป็นจุดสกปรก",
        "NOT_DIRTY_SPOT": "ไม่ใช่จุดสกปรก",
        "AMBIGUOUS": "ไม่แน่ชัด",
        "UNJUDGEABLE": "ไม่สามารถประเมินจากภาพได้",
        "ANNOTATION_LOCALIZATION_ISSUE": "ตำแหน่ง Annotation ไม่ตรงกับจุดสกปรก",
    }

    toc = "\n".join(
        f'<a href="#{anchor}"><span>{num}</span>{html.escape(title)}</a>'
        for num, title, anchor in chapters
    )
    top_nav = "\n".join(f'<a href="#{anchor}">{num}</a>' for num, _title, anchor in chapters)
    decision_items = "\n".join(
        f"<li><code>{html.escape(code)}</code><span>{html.escape(label)}</span></li>"
        for code, label in decisions.items()
    )
    multiseed_cards = "\n".join(
        card(
            exp,
            f"Recall {fmt(e21[exp]['recall']['mean'], 3)}",
            f"Precision proxy {fmt(e21[exp]['precision_proxy']['mean'], 3)} / F2 {fmt(e21[exp]['f2']['mean'], 3)}",
        )
        for exp in ("E00", "E19", "E15")
    )
    experiment_cards = "\n".join(
        '<article class="experiment-card">'
        '<div class="experiment-head">'
        f'<span>{html.escape(item["chapter"])}</span>'
        "<div>"
        f'<h3>{html.escape(item["title"])}</h3>'
        f'<p>{html.escape(item["decision"])}</p>'
        "</div>"
        "</div>"
        "<dl>"
        f'<dt>คำถามที่ทดสอบ</dt><dd>{html.escape(item["question"])}</dd>'
        f'<dt>สิ่งที่เปลี่ยน</dt><dd>{html.escape(item["changed"])}</dd>'
        f'<dt>ผลที่พบ</dt><dd>{html.escape(item["result"])}</dd>'
        "</dl>"
        "</article>"
        for item in payload["experiments"]
    )
    duration_cards = (
        card("2 epochs", f"Recall {fmt(duration_means['epoch2_recall'], 4)}", f"unmatched {fmt(duration_means['epoch2_unmatched'], 1)}")
        + card("4 epochs", f"Recall {fmt(duration_means['epoch4_recall'], 4)}", f"unmatched {fmt(duration_means['epoch4_unmatched'], 1)}")
        + card("Conclusion", "4 epochs = REGRESSION", "2 epochs retained")
    )
    e22_cards = "".join(
        [
            card("Source images", e22["test_source_image_count"]),
            card("Actual model-input tiles", e22["test_tile_count"]),
            card("GT", e22["test_gt_count"]),
            card("TP", e22["tp"]),
            card("FN", e22["fn"]),
            card("Predictions", fmt(e22["prediction_count"])),
            card("Recall", f"{fmt(e22['recall'], 10)} ≈ {pct(e22['recall'])}"),
            card("Precision proxy", f"{fmt(e22['precision_proxy'], 10)} ≈ {pct(e22['precision_proxy'])}"),
            card("Unmatched/model-only", fmt(e22["unmatched"])),
            card("F1", fmt(e22["f1"], 10)),
            card("F2", fmt(e22["f2"], 10)),
            card("PROJECT_AP", fmt(payload["e22_ap"]["project_ap"], 10)),
        ]
    )

    return f"""<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BirdNests Faster R-CNN - หนังสือสรุปงานวิจัยและ Expert Review</title>
  <meta name="description" content="หนังสือสรุปงานวิจัย BirdNests Faster R-CNN ภาษาไทย ตั้งแต่ชุดข้อมูล การทดลอง E00-E22 Model Lock E22 Final Test และ Expert Review ที่เปิดใช้งานแล้ว">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <a class="skip-link" href="#main">ข้ามไปเนื้อหา</a>
  <header class="site-header">
    <nav class="topbar" aria-label="ทางลัดบทสำคัญ">
      <a href="../">Docs Home</a>
      {top_nav}
    </nav>
    <section class="cover" id="cover">
      <p class="eyebrow">ENGINEERING / RESEARCH PROTOTYPE</p>
      <h1>BirdNests Faster R-CNN</h1>
      <p class="subtitle">เส้นทางการพัฒนาต้นแบบตรวจจับจุดสกปรกในภาพรังนก ตั้งแต่การเตรียมข้อมูล การทดลองอย่างเป็นระบบ การล็อกโมเดล การทดสอบชุดข้อมูลที่ไม่เคยใช้มาก่อน จนถึงการเปิด Expert Review</p>
      <div class="status-banner" aria-label="Expert Review current status">
        <span>EXPERT REVIEW: LAUNCHED / IN PROGRESS</span>
        <strong>LAUNCHED / IN PROGRESS</strong>
      </div>
      <div class="hero-actions">
        <a class="cta" href="{REVIEWER_WEB_APP_URL}" target="_blank" rel="noopener noreferrer">เปิดระบบ Expert Review</a>
        <p>สำหรับผู้ประเมินที่ได้รับ Access Token เท่านั้น</p>
      </div>
      <div class="cover-grid">
        {card("240", "คู่ภาพ Raw / Marker", "ชุดภาพต้นฉบับและภาพ marker ที่ใช้เป็นฐานข้อมูล")}
        {card("7,115", "Marker reference points", "จุดอ้างอิงเชิงบวกจาก marker เดิม")}
        {card("1,169", "Expert Review cases", "เคสสำหรับผู้เชี่ยวชาญตรวจซ้ำ")}
        {card("58.4%", "E22 Recall", "สัดส่วน reference ที่ตรวจพบใน Final Test ไม่ใช่ production accuracy")}
      </div>
    </section>
  </header>
  <div class="book-layout">
    <aside class="toc" aria-label="สารบัญ">
      <p>สารบัญ</p>
      <nav>{toc}</nav>
    </aside>
    <main id="main" class="book">
      <section class="chapter" id="purpose">
        <p class="chapter-number">01</p>
        <h2>โครงการนี้ทำอะไร และทำไมต้องทำ</h2>
        <p>โครงการนี้ศึกษาการใช้ computer vision ช่วยตรวจจับ <strong>candidate dirty spots</strong> หรือ “ตำแหน่งที่อาจเป็นจุดสกปรก” ในภาพรังนก เป้าหมายไม่ใช่การประกาศระบบตรวจคุณภาพอัตโนมัติสำเร็จรูป แต่คือการสร้างต้นแบบเชิงวิศวกรรมที่ตรวจสอบได้ทุกขั้นตอน</p>
        <p>ระบบถูกจัดเป็น <strong>ENGINEERING / RESEARCH PROTOTYPE</strong> หมายถึงต้นแบบเพื่อพิสูจน์วิธีการ ทดลองข้อจำกัด และเตรียมข้อมูลสำหรับการประเมินโดยผู้เชี่ยวชาญ ยังไม่ใช่ production quality-control software, commercial automated inspection, หรือเครื่องมือแทนผู้เชี่ยวชาญมนุษย์</p>
        <div class="callout teal"><strong>แก่นของงานวิจัย</strong><span>จาก marker reference เดิม สู่โมเดล Faster R-CNN ที่ถูกทดลองอย่างเป็นระบบ แล้วส่ง prediction ที่ยังตีความไม่ได้เข้าสู่ Expert Review</span></div>
      </section>
      <section class="chapter" id="dataset">
        <p class="chapter-number">02</p>
        <h2>ชุดข้อมูล 240 คู่ภาพ และ Marker 7,115 จุด</h2>
        <p>ชุดข้อมูลตั้งต้นมี <strong>240 คู่ภาพ Raw / Marker</strong> และมี <strong>7,115 Marker reference points</strong> ที่ใช้เป็นหลักฐานเชิงบวกว่าในตำแหน่งนั้นมีสิ่งที่ควรถูกตรวจจับ</p>
        <p>ประเด็นสำคัญคือ <strong>Marker presence = positive reference</strong> หรือการมี marker คือหลักฐานเชิงบวก แต่ <strong>Marker absence ไม่เท่ากับ confirmed negative</strong> การไม่มี marker จึงไม่ใช่หลักฐานว่าบริเวณนั้นไม่มีจุดสกปรกจริงเสมอไป</p>
        <div class="metric-grid">{card("240", "คู่ภาพ Raw / Marker", "ฐานภาพต้นฉบับและภาพ marker")}{card("7,115", "Marker reference points", "positive reference source")}{card("ข้อควรระวัง", "absence ≠ negative", "ห้ามตีความ unmatched เป็น false positive ทันที")}</div>
      </section>
      <section class="chapter" id="split-tiling">
        <p class="chapter-number">03</p>
        <h2>การแบ่งข้อมูลและการตัดภาพเป็น Tile</h2>
        <p>การแบ่งข้อมูลใช้ <strong>source-level split</strong> คือแยกตามภาพต้นทาง เพื่อป้องกัน leakage ระหว่าง train, validation และ test ถ้า tile จากภาพเดียวกันหลุดไปอยู่คนละชุด ผลประเมินอาจดูดีเกินจริง</p>
        <div class="definition-grid"><article><strong>Tile size</strong><span>512 pixels</span></article><article><strong>Overlap</strong><span>128 pixels</span></article><article><strong>Stride</strong><span>384 pixels</span></article></div>
        <div class="callout amber"><strong>ACTUAL MODEL-INPUT VALIDATION TILES = 432</strong><span>ค่า historical 468 ไม่ใช่จำนวน tile input สำหรับ inference; 468 = 36 source-image opens + 432 tile-image inference opens</span></div>
      </section>
      <section class="chapter" id="model-metrics">
        <p class="chapter-number">04</p>
        <h2>Faster R-CNN คืออะไร และตัวชี้วัดหมายถึงอะไร</h2>
        <p><strong>Faster R-CNN MobileNetV3-Large-FPN</strong> เป็นโมเดลตรวจจับวัตถุที่หา candidate regions ก่อน แล้วประเมินว่าตำแหน่งนั้นเข้ากับ class ที่สนใจหรือไม่ งานนี้ใช้ <strong>2 classes</strong> และรายงานผลแบบระมัดระวัง เพราะ Ground Truth มาจาก marker reference เดิม ไม่ใช่คำตัดสินสุดท้ายจากผู้เชี่ยวชาญ</p>
        <div class="glossary-grid">{tag_card("Recall", "สัดส่วนจุดอ้างอิงที่ตรวจพบ", "ถ้า reference มี 100 จุดและโมเดลจับได้ 60 จุด Recall คือ 60%")}{tag_card("Precision proxy", "ค่าประมาณเทียบ marker", "เป็น annotation-relative ไม่ใช่ expert-confirmed precision")}{tag_card("Unmatched prediction", "prediction ที่ยังจับคู่กับ Marker reference ไม่ได้", "ยังไม่ควรเรียกว่า false positive จนกว่าจะผ่าน Expert Review")}{tag_card("F1 / F2", "คะแนนรวมระหว่าง Recall และ Precision proxy", "F2 ให้น้ำหนัก Recall มากกว่า F1")}{tag_card("PROJECT_AP", "metric เฉพาะโครงการ", "ไม่ใช่ COCO AP, AP50, AP75 หรือ AP-small")}</div>
      </section>
      <section class="chapter" id="experiment-journey">
        <p class="chapter-number">05</p>
        <h2>เส้นทางการทดลองอย่างเป็นระบบ E00-E22</h2>
        <p>การทดลองไม่ได้เป็นการสุ่มปรับค่าจนได้ตัวเลขที่ดูดี แต่เป็นลำดับคำถามเชิงวิศวกรรม: anchor เหมาะหรือไม่, proposal budget จำกัดหรือไม่, score แยกคุณภาพได้หรือไม่, augmentation ช่วยจริงหรือไม่, และ improvement reproducible ข้าม seed หรือเปล่า</p>
        <div class="experiment-list">{experiment_cards}</div>
      </section>
      <section class="chapter" id="multi-seed">
        <p class="chapter-number">06</p>
        <h2>Multi-seed: ทำไม E00 จึงยังเป็นโมเดลที่เลือก</h2>
        <p>ผลเฉลี่ยที่สูงกว่าไม่ได้แปลว่าควรแทน baseline โดยอัตโนมัติ การ promote configuration ต้องเห็น improvement ที่สม่ำเสมอข้าม seed และต้องควบคุม trade-off ของ unmatched predictions ได้</p>
        <div class="metric-grid">{multiseed_cards}</div>
        <div class="callout teal"><strong>ข้อสรุป E21</strong><span>E00 MULTISEED_LEADER เพราะคู่แข่งยังไม่ชนะอย่างมั่นคงพอ แม้บาง metric เฉลี่ยจะสูงกว่าในบางมุม</span></div>
      </section>
      <section class="chapter" id="duration">
        <p class="chapter-number">07</p>
        <h2>Training Duration: ทำไมฝึกนานขึ้นไม่ได้แปลว่าดีขึ้น</h2>
        <p>การเปรียบเทียบ 2 epochs กับ 4 epochs เป็น controlled duration study. 4 epochs เพิ่ม Recall ได้ แต่เพิ่ม unmatched count มากกว่าอย่างมีนัยสำคัญ ทำให้ trade-off ของระบบแย่ลงสำหรับ workflow นี้</p>
        <div class="metric-grid">{duration_cards}</div>
        <div class="callout amber"><strong>ฝึกนานขึ้นไม่ได้แปลว่าโมเดลดีขึ้นเสมอไป</strong><span>เมื่อตัวเลข Recall ดีขึ้นพร้อมกับ unmatched ที่เพิ่มมากเกินไป ระบบอาจสร้างภาระ review และความเสี่ยงการตีความมากกว่าเดิม</span></div>
      </section>
      <section class="chapter" id="model-lock">
        <p class="chapter-number">08</p>
        <h2>Model Lock: ล็อกโมเดลก่อนเปิด Final Test</h2>
        <p>ก่อนแตะชุด Final Test โครงการล็อก configuration เพื่อป้องกัน test-set-driven modifications. หลังจุดนี้ไม่มีการ tuning โมเดล ไม่มีการ retune threshold และไม่มีการใช้ผล test เพื่อย้อนกลับไปปรับระบบ</p>
        <div class="metric-grid">{card("Configuration", payload["lock"]["configuration"])}{card("Seed", payload["lock"]["seed"])}{card("Threshold", payload["lock"]["threshold"])}{card("One-time test", str(payload["lock"]["one_time_test_completed"]).upper())}</div>
        <details><summary>Checkpoint SHA-256 สำหรับตรวจสอบความคงเดิมของโมเดล</summary><p><code>{LOCKED_CHECKPOINT_SHA256}</code></p></details>
      </section>
      <section class="chapter emphasis" id="e22">
        <p class="chapter-number">09</p>
        <h2>E22: Untouched Final Test ที่ใช้เพียงครั้งเดียว</h2>
        <p>E22 คือการทดสอบหลัง Model Lock บนข้อมูลที่ไม่เคยใช้ในการเลือกโมเดลหรือปรับ threshold มาก่อน จึงเป็นหลักฐานสำคัญที่สุดของพฤติกรรมโมเดลก่อนเข้าสู่ Expert Review</p>
        <div class="metric-grid e22-grid">{e22_cards}</div>
        <div class="callout teal"><strong>Assessment: GENERALIZATION_CONSISTENT</strong><span>selected validation seed recall ≈ 0.5792 และ final test recall ≈ 0.5839 จึงสอดคล้องกันในเชิงพฤติกรรม แต่ยังไม่ใช่หลักฐานว่าเป็น production-ready หรือ high-accuracy automated QC</span></div>
        <div class="callout amber"><strong>ข้อจำกัดของ PROJECT_AP</strong><span>PROJECT_AP เป็น metric เฉพาะโครงการเทียบกับ annotation เดิม ไม่ใช่ COCO AP, AP50, AP75 หรือ AP-small</span></div>
      </section>
      <section class="chapter" id="why-review">
        <p class="chapter-number">10</p>
        <h2>ทำไม 1,029 Unmatched จึงยังไม่ควรถูกเรียกว่า False Positive</h2>
        <p>โมเดลสร้าง <strong>1,029 unmatched/model-only predictions</strong> บน E22. คำว่า unmatched แปลเพียงว่ายังจับคู่กับ Marker reference เดิมไม่ได้ ไม่ได้แปลว่าผิดแน่นอน</p>
        <div class="interpretation-grid">{tag_card("ความเป็นไปได้", "จุดสกปรกจริงที่ marker เดิมพลาด", "ต้องให้ผู้เชี่ยวชาญยืนยัน")}{tag_card("ความเป็นไปได้", "False positive จริง", "prediction ไม่ใช่จุดสกปรก")}{tag_card("ความเป็นไปได้", "Ambiguous", "ภาพหรือบริบทไม่ชัดพอ")}{tag_card("ความเป็นไปได้", "Unjudgeable", "ไม่สามารถประเมินจากภาพที่มี")}{tag_card("ความเป็นไปได้", "Annotation localization issue", "ตำแหน่ง reference กับ candidate ไม่ตรงกัน")}</div>
      </section>
      <section class="chapter" id="review-package">
        <p class="chapter-number">11</p>
        <h2>การออกแบบ Expert Review จำนวน 1,169 เคส</h2>
        <p>ชุด Expert Review ถูกสร้างเพื่อแยกความหมายของ unmatched predictions และมี control cases เพื่อวัดคุณภาพการประเมิน ไม่ใช่เป็นเพียง gallery ภาพสาธารณะ</p>
        <div class="metric-grid">{card("Total", fmt(expert["cases"]["total"]), "Expert Review cases")}{card("Unmatched/model-only", fmt(expert["cases"]["unmatched_model_only"]))}{card("TP quality-control", expert["cases"]["tp_controls"])}{card("FN controls", expert["cases"]["fn_controls"], "Q1-Q4, 20 each")}{card("Batches", f"{batches['number_of_batches']}", "nominal 75 / final 44")}</div>
        <h3>Allowed decisions</h3>
        <ul class="decision-list">{decision_items}</ul>
        <p class="confidence-row"><strong>Confidence</strong><span>HIGH</span><span>MEDIUM</span><span>LOW</span></p>
        <p>Model scores are intentionally hidden from reviewers เพื่อไม่ให้คะแนนของโมเดลชี้นำการตัดสินใจของมนุษย์</p>
      </section>
      <section class="chapter" id="reviewer-design">
        <p class="chapter-number">12</p>
        <h2>Reviewer A/B และแผนวิเคราะห์ Agreement</h2>
        <p>โหมด review คือ <strong>PRIMARY_PLUS_RELIABILITY_SUBSET</strong>. Reviewer หลักตรวจครบทุกเคส ส่วน reviewer ที่สองตรวจ subset แบบ deterministic เพื่อประเมินความสอดคล้องโดยไม่เพิ่มภาระงานจนเกินจำเป็น</p>
        <div class="metric-grid">{card("REV_A", "1,169 cases", "primary full review")}{card("REV_B", "292 cases", "reliability subset")}{card("REV_B unmatched", "257")}{card("REV_B TP QC", "15")}{card("REV_B FN controls", "20", "Q1-Q4: 5 each")}</div>
        <div class="callout teal"><strong>แผนวิเคราะห์ความสอดคล้อง</strong><span>จะคำนวณ Raw Agreement และ Cohen's kappa บน shared subset หลัง review เสร็จ สถานะตอนนี้คือ NOT YET CALCULATED</span></div>
      </section>
      <section class="chapter" id="security">
        <p class="chapter-number">13</p>
        <h2>ความปลอดภัยและความถูกต้องของระบบ Expert Review</h2>
        <p>ก่อน launch มีการตรวจสอบ private asset inventory และ integrity ครบทุกเคส เพื่อให้แน่ใจว่าภาพที่ reviewer เห็นตรงกับ package ที่ freeze ไว้</p>
        <div class="metric-grid">{card("Expected assets", "1,169")}{card("Inventory matched", "1,169 / 1,169")}{card("SHA-256 verified", "1,169 / 1,169")}{card("Missing", "0")}{card("Mismatch", "0")}{card("Duplicates", "0")}{card("Invalid MIME", "0")}{card("Internal errors", "0")}</div>
        <div class="flow" aria-label="reviewer access architecture"><span>Web App</span><span>Access Token</span><span>server-side authorization</span><span>reviewer assignment check</span><span>private asset delivery</span><span>review decision</span></div>
        <p class="privacy-note">หน้า public นี้ไม่เผยแพร่ access token ดิบ, ค่าลับสำหรับยืนยันสิทธิ์, private asset identifiers หรือ researcher-only metadata</p>
      </section>
      <section class="chapter launched" id="current-status">
        <p class="chapter-number">14</p>
        <h2>สถานะปัจจุบัน: EXPERT REVIEW — LAUNCHED / IN PROGRESS</h2>
        <p>ระบบ Expert Review เปิดใช้งานแล้ว และผล review ยังไม่ final. หน้า public จึงต้องสื่อสารสถานะเป็น launched / in progress เท่านั้น ไม่สรุปผลทางวิทยาศาสตร์แทนผู้เชี่ยวชาญ</p>
        <div class="metric-grid">{card("REV_A active", "TRUE")}{card("REV_B active", "TRUE")}{card("launch_gate_status", "REVIEW_LAUNCHED")}{card("review_start_enabled", "TRUE")}{card("REV_A smoke test", "Case 1 of 1,169 loaded")}{card("REV_B smoke test", "Case 1 of 292 loaded")}{card("ReviewResponses", "0", "ณ เวลาตรวจสอบก่อนเริ่มการประเมินจริง")}{card("ReviewSessionsV2", "0", "ณ เวลาตรวจสอบก่อนเริ่มการประเมินจริง")}</div>
        <p>Production no-submit smoke test ยืนยันว่า private assets loaded สำหรับ reviewer flow แล้ว</p>
      </section>
      <section class="chapter" id="next">
        <p class="chapter-number">15</p>
        <h2>อภิธานศัพท์ ข้อจำกัด และสิ่งที่จะทำต่อ</h2>
        <div class="status-columns">
          <article><h3>เสร็จแล้ว</h3><ul><li>dataset preparation</li><li>marker reference pipeline</li><li>source-level split</li><li>systematic Faster R-CNN experiments</li><li>multi-seed testing</li><li>duration research</li><li>Model Lock</li><li>one-time E22 final test</li><li>Expert Review protocol</li><li>reviewer assignment freeze</li><li>asset SHA verification</li><li>authentication verification</li><li>production Reviewer UI deployment</li><li>Expert Review launch</li></ul></article>
          <article><h3>กำลังดำเนินการ</h3><p><strong>Expert Review — IN PROGRESS</strong></p></article>
          <article><h3>ขั้นต่อไป</h3><p>Expert Review completion → Raw Agreement → Cohen's kappa → adjudication → annotation-corrected interpretation → final scientific conclusions</p></article>
        </div>
        <div class="callout amber"><strong>ข้อจำกัดสำคัญ</strong><span>Expert-adjusted Recall ยังไม่สามารถ claim ได้ เว้นแต่มี denominator ที่ valid หลังการตรวจของผู้เชี่ยวชาญ</span></div>
      </section>
    </main>
  </div>
  <footer>Public scientific summary. Expert Review results are not final. No private review assets, raw tokens, secret authorization values, private asset identifiers, or researcher-only metadata are published.</footer>
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
    body { min-width: 320px; margin: 0; font-family: "Sarabun", Tahoma, sans-serif; color: #0f172a; background: #f8fafc; line-height: 1.7; }
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
    return """:root {
  --ink: #0f172a;
  --body: #334155;
  --muted: #64748b;
  --paper: #ffffff;
  --soft: #f6f8fb;
  --soft-blue: #eef6ff;
  --line: #d7e0ea;
  --blue: #075985;
  --blue-strong: #0c4a6e;
  --teal: #0f766e;
  --teal-soft: #e6fffb;
  --green: #047857;
  --green-soft: #e8f8ef;
  --amber: #92400e;
  --amber-soft: #fff7df;
  --radius: 8px;
  --max: 1340px;
  --measure: 76ch;
  --shadow: 0 18px 48px rgba(15, 23, 42, 0.08);
}
* { box-sizing: border-box; }
html { min-width: 320px; scroll-behavior: smooth; background: var(--soft); }
body {
  margin: 0;
  color: var(--ink);
  background: linear-gradient(180deg, #ffffff 0%, var(--soft-blue) 520px, var(--soft) 100%);
  font-family: "Sarabun", Tahoma, sans-serif;
  font-size: 18px;
  line-height: 1.78;
  letter-spacing: 0;
  text-rendering: optimizeLegibility;
}
body, a, button, td, th, code, strong, h1, h2, h3, li, dd { overflow-wrap: anywhere; }
a { color: inherit; }
.skip-link {
  position: fixed;
  left: 16px;
  top: 16px;
  z-index: 100;
  transform: translateY(-160%);
  padding: 10px 14px;
  color: #fff;
  background: var(--ink);
  border-radius: var(--radius);
  font-weight: 700;
}
.skip-link:focus { transform: translateY(0); outline: 4px solid #7dd3fc; }
.site-header { border-bottom: 1px solid var(--line); }
.topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  width: min(var(--max), calc(100% - 32px));
  margin: 0 auto;
  padding: 12px 0;
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
  background: rgba(246, 248, 251, 0.94);
  backdrop-filter: blur(12px);
}
.topbar a {
  min-width: 44px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 12px;
  color: var(--blue);
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  font-weight: 800;
  font-size: 0.92rem;
  text-decoration: none;
  cursor: pointer;
}
.topbar a:hover, .topbar a:focus-visible, .cta:hover, .cta:focus-visible, .toc a:hover, .toc a:focus-visible {
  outline: 3px solid rgba(14, 165, 233, 0.28);
  border-color: #7dd3fc;
}
.cover {
  width: min(var(--max), calc(100% - 32px));
  margin: 0 auto;
  padding: clamp(42px, 6vw, 86px) 0 clamp(34px, 5vw, 64px);
}
.eyebrow, .chapter-number {
  margin: 0 0 10px;
  color: var(--blue);
  font-size: 0.82rem;
  font-weight: 800;
  letter-spacing: 0;
}
h1, h2, h3, p { margin-top: 0; }
h1, h2, h3 { letter-spacing: 0; text-wrap: balance; }
h1 {
  max-width: 980px;
  margin-bottom: 12px;
  font-size: clamp(3rem, 7vw, 5rem);
  line-height: 1.06;
}
h2 {
  max-width: 900px;
  margin-bottom: 14px;
  font-size: clamp(2rem, 3.2vw, 2.55rem);
  line-height: 1.23;
}
h3 { margin-bottom: 8px; font-size: 1.25rem; line-height: 1.35; }
p { max-width: var(--measure); color: var(--body); }
.subtitle {
  max-width: 880px;
  margin-bottom: 22px;
  color: var(--body);
  font-size: clamp(1.15rem, 2vw, 1.36rem);
  line-height: 1.86;
}
.status-banner {
  width: fit-content;
  max-width: 100%;
  display: grid;
  gap: 4px;
  margin: 12px 0 18px;
  padding: 14px 18px;
  color: #064e3b;
  background: var(--green-soft);
  border: 1px solid #9fd8ba;
  border-radius: var(--radius);
}
.status-banner span { font-weight: 800; }
.status-banner strong { font-size: clamp(1.35rem, 2.8vw, 2.35rem); line-height: 1.15; }
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px;
  margin-bottom: 24px;
}
.hero-actions p { margin: 0; color: var(--muted); font-weight: 700; }
.cta {
  min-height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 11px 18px;
  color: #fff;
  background: var(--blue);
  border: 1px solid var(--blue);
  border-radius: var(--radius);
  text-decoration: none;
  font-weight: 800;
  cursor: pointer;
}
.cover-grid, .metric-grid, .definition-grid, .glossary-grid, .interpretation-grid, .status-columns {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px;
}
.book-layout {
  width: min(var(--max), calc(100% - 32px));
  margin: 28px auto 0;
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr);
  gap: 28px;
  align-items: start;
}
.toc {
  position: sticky;
  top: 76px;
  max-height: calc(100vh - 96px);
  overflow: auto;
  padding: 16px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.toc p {
  margin: 0 0 10px;
  color: var(--ink);
  font-weight: 800;
}
.toc nav { display: grid; gap: 4px; }
.toc a {
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  color: var(--body);
  border: 1px solid transparent;
  border-radius: var(--radius);
  text-decoration: none;
  font-size: 0.94rem;
  font-weight: 700;
}
.toc a span {
  color: var(--blue);
  font-weight: 800;
}
.book {
  min-width: 0;
  display: grid;
  gap: 22px;
  padding-bottom: 56px;
}
.chapter {
  min-width: 0;
  padding: clamp(22px, 3vw, 38px);
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
.chapter.emphasis { border-color: #93c5fd; }
.chapter.launched {
  border-color: #9fd8ba;
  background: linear-gradient(180deg, #ffffff 0%, #f0fdf4 100%);
}
.metric-card, .info-card, .definition-grid article, .experiment-card, .status-columns article {
  min-width: 0;
  padding: 16px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.metric-card span, .info-card > span, dt {
  display: block;
  color: var(--muted);
  font-size: 0.88rem;
  font-weight: 800;
}
.metric-card strong {
  display: block;
  margin: 4px 0;
  color: var(--ink);
  font-size: clamp(1.35rem, 2vw, 2rem);
  line-height: 1.18;
}
.metric-card p, .info-card p, dd { margin: 0; color: var(--body); }
.definition-grid article strong { display: block; color: var(--blue); }
.definition-grid article span { color: var(--body); }
.glossary-grid, .interpretation-grid { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.experiment-list { display: grid; gap: 14px; }
.experiment-head {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 12px;
}
.experiment-head > span {
  flex: 0 0 auto;
  min-width: 48px;
  min-height: 44px;
  display: inline-grid;
  place-items: center;
  color: #fff;
  background: var(--blue);
  border-radius: var(--radius);
  font-weight: 800;
}
.experiment-head h3 { margin: 0; }
.experiment-head p { margin: 2px 0 0; color: var(--teal); font-weight: 800; }
dl { margin: 0; display: grid; gap: 8px; }
dt { margin-top: 4px; }
dd { margin-left: 0; }
.callout {
  max-width: var(--measure);
  margin-top: 16px;
  padding: 16px 18px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.callout strong, .callout span { display: block; }
.callout.teal { color: #134e4a; background: var(--teal-soft); border-color: #99f6e4; }
.callout.amber { color: #713f12; background: var(--amber-soft); border-color: #f0d38b; }
details {
  max-width: var(--measure);
  margin-top: 14px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
summary {
  min-height: 44px;
  cursor: pointer;
  color: var(--blue);
  font-weight: 800;
}
code { font-family: "Sarabun", Tahoma, sans-serif; font-weight: 700; }
.decision-list {
  list-style: none;
  margin: 0 0 12px;
  padding: 0;
  display: grid;
  gap: 10px;
}
.decision-list li {
  display: grid;
  gap: 4px;
  padding: 14px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.decision-list span { color: var(--body); }
.confidence-row { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.confidence-row span {
  padding: 6px 10px;
  color: var(--green);
  background: var(--green-soft);
  border-radius: var(--radius);
  font-weight: 800;
}
.flow {
  margin: 16px 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.flow span {
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  padding: 7px 11px;
  color: var(--blue-strong);
  background: var(--soft-blue);
  border: 1px solid #bfdbfe;
  border-radius: var(--radius);
  font-weight: 800;
}
.privacy-note {
  padding: 14px 16px;
  color: #134e4a;
  background: var(--green-soft);
  border: 1px solid #9fd8ba;
  border-radius: var(--radius);
}
.status-columns ul { margin: 0; padding-left: 20px; }
footer {
  width: min(var(--max), calc(100% - 32px));
  margin: 0 auto;
  padding: 28px 0 44px;
  color: var(--muted);
  font-size: 0.95rem;
}
@media (max-width: 1024px) {
  .book-layout { grid-template-columns: 1fr; }
  .toc { position: static; max-height: none; }
  .toc nav { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
}
@media (max-width: 720px) {
  body { font-size: 16px; line-height: 1.72; }
  .topbar { justify-content: flex-start; }
  h1 { font-size: 2.65rem; line-height: 1.12; }
  h2 { font-size: 1.75rem; }
  .cover, .book-layout, footer { width: min(100% - 24px, var(--max)); }
  .chapter { padding: 20px; }
  .metric-card strong { font-size: 1.35rem; }
}
@media (max-width: 360px) {
  h1 { font-size: 2.35rem; }
  .topbar a { padding: 7px 10px; }
  .cover-grid, .metric-grid, .definition-grid, .glossary-grid, .interpretation-grid, .status-columns {
    grid-template-columns: minmax(0, 1fr);
  }
  .chapter { padding: 16px; }
  .experiment-head { display: grid; }
}
@media print {
  body { background: #fff; color: #000; font-size: 12pt; }
  .topbar, .toc, .cta { display: none; }
  .cover, .book-layout, footer { width: 100%; margin: 0; }
  .book-layout { display: block; }
  .chapter { break-inside: avoid; box-shadow: none; border-color: #ccc; margin-bottom: 14pt; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; }
}
"""


def write_public_data(payload: dict[str, Any]) -> None:
    summary_data = {
        "schema_version": 4,
        "route": "anchor-experiment-summary",
        "purpose": "thai_first_research_book_through_expert_review_launch",
        "expert_review_status": "LAUNCHED_IN_PROGRESS",
        "reviewer_web_app_url": REVIEWER_WEB_APP_URL,
        "e22": {**payload["e22"], "project_ap": payload["e22_ap"]["project_ap"]},
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
        "schema_version": 4,
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
    write_text(SUMMARY_DIR / "styles.css", shared_css())
    write_public_data(payload)


if __name__ == "__main__":
    build()
