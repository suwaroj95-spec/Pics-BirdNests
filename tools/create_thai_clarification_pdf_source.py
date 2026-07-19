from __future__ import annotations

import base64
import html
import json
import subprocess
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_HTML = PROJECT_ROOT / "output" / "pdf" / "BirdNests-Model-Prototype-Clarification-TH.source.html"
REPRESENTATIVE_CROP = PROJECT_ROOT / "tmp" / "pdfs" / "representative_contact_sheet_card_MO0125-000005.jpg"


def read_json(path: str) -> dict:
    return json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True).strip()


def representative_card_data_uri() -> str:
    page = PROJECT_ROOT / "docs" / "contact-sheets" / "pages" / "primary" / "primary_0125_page_001.png"
    REPRESENTATIVE_CROP.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(page).convert("RGB") as image:
        card = image.crop((80, 603, 900, 1033))
        card.save(REPRESENTATIVE_CROP, "JPEG", quality=90, optimize=True)
    encoded = base64.b64encode(REPRESENTATIVE_CROP.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def metric(value: object) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def build_html() -> str:
    runtime = read_json("handoff/prototype_v1/prototype_runtime_config.json")
    operating = read_json("handoff/prototype_v1/prototype_operating_points.json")
    manifest = read_json("docs/contact-sheets/contact-sheet-manifest.json")
    checkpoint = read_json("handoff/prototype_v1/checkpoint_release_manifest.json")
    primary = operating["primary_operating_point"]
    comparison = operating["comparison_operating_point"]
    image_uri = representative_card_data_uri()
    head = html.escape(git_head())
    prep_date = "18 กรกฎาคม 2026"

    rows = [
        ("0.125", "941", primary["matched_gt"], "70.99%", primary["merged_predictions"], primary["unverified_extras"], primary["maximum_merged_predictions_per_source"], manifest["sets"]["primary"]["page_count"]),
        ("0.175", "941", comparison["matched_gt"], "39.85%", comparison["merged_predictions"], comparison["unverified_extras"], comparison["maximum_merged_predictions_per_source"], manifest["sets"]["comparison"]["page_count"]),
    ]
    result_rows = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(metric(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
    )

    page_total = 7
    footer = lambda n: f"<footer>BirdNests Faster R-CNN Engineering Prototype - Supplementary clarification - Page {n}/{page_total}</footer>"
    css = """
*{box-sizing:border-box}
@page{size:A4;margin:0}
body{margin:0;background:#e5e7eb;color:#0f172a;font-family:Tahoma,"Noto Sans Thai",sans-serif;line-height:1.48}
.sheet{position:relative;width:210mm;height:297mm;margin:0 auto;padding:15mm 15mm 18mm;background:#fff;page-break-after:always;overflow:hidden}
h1{font-size:24pt;line-height:1.18;margin:0 0 5mm;color:#020617}
h2{font-size:15pt;margin:0 0 3.5mm;color:#0f172a}
h3{font-size:11.5pt;margin:4mm 0 2mm;color:#0f172a}
p,li,td,th{font-size:10pt}
p{margin:0 0 3mm}
ul{margin:0 0 4mm 5mm;padding-left:5mm}
li{margin:0 0 1.7mm}
.kicker{font-size:9pt;color:#0369a1;font-weight:700;letter-spacing:.02em;text-transform:uppercase;margin-bottom:2mm}
.lead{font-size:12pt;color:#334155}
.note{border-left:3px solid #0f766e;background:#f0fdfa;padding:3mm 4mm;margin:3mm 0;border-radius:3mm}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:4mm}
.box{border:1px solid #cbd5e1;border-radius:3mm;padding:3.5mm;background:#f8fafc}
.metric{font-size:19pt;font-weight:700;color:#0369a1;display:block}
table{border-collapse:collapse;width:100%;margin:2mm 0 4mm;table-layout:fixed}
th{background:#e0f2fe;color:#0f172a;text-align:left}
th,td{border:1px solid #cbd5e1;padding:2mm;vertical-align:top;overflow-wrap:anywhere;word-break:normal}
.small, .small li, .small td, .small th{font-size:7.8pt}
.results th:nth-child(1),.results td:nth-child(1){width:11%}
.results th:nth-child(2),.results td:nth-child(2){width:12%}
.results th:nth-child(3),.results td:nth-child(3){width:10%}
.results th:nth-child(4),.results td:nth-child(4){width:9%}
.results th:nth-child(5),.results td:nth-child(5){width:12%}
.results th:nth-child(6),.results td:nth-child(6){width:20%}
.results th:nth-child(7),.results td:nth-child(7){width:14%}
.results th:nth-child(8),.results td:nth-child(8){width:12%}
.refs li{font-size:8.8pt;margin-bottom:1.2mm}
figure{margin:3mm 0 0}
figure img{width:100%;border:1px solid #cbd5e1;border-radius:2mm;display:block}
figcaption{font-size:8.8pt;color:#475569;margin-top:2mm}
footer{position:absolute;left:15mm;right:15mm;bottom:7mm;border-top:1px solid #cbd5e1;padding-top:2mm;color:#64748b;font-size:8pt}
.tag{display:inline-block;border:1px solid #bae6fd;background:#f0f9ff;color:#075985;border-radius:999px;padding:.5mm 2mm;font-size:8.6pt;font-weight:700}
.tight li{margin-bottom:1mm}
"""

    return f"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>เอกสารชี้แจงเพิ่มเติมหลังการนำเสนอ BirdNests Faster R-CNN Engineering Prototype</title>
<style>{css}</style>
</head>
<body>
<section class="sheet">
  <div class="kicker">Supplementary clarification</div>
  <h1>เอกสารชี้แจงเพิ่มเติมหลังการนำเสนอ<br>BirdNests Faster R-CNN Engineering Prototype</h1>
  <p class="lead">เอกสารนี้เป็น addendum ภาษาไทยสำหรับอธิบาย Prototype หลังการนำเสนอ web infographic เดิม ไม่ใช่รายงานทดลองใหม่ และไม่ได้แทนที่ infographic ที่ได้นำเสนอไปแล้ว</p>
  <div class="note">ไม่มีการ retraining, inference run, threshold selection, NMS/merge ใหม่, matching ใหม่ หรือ metric recalculation เพื่อสร้างเอกสารนี้ นอกจากการ reconcile ค่าตัวเลขจากไฟล์ canonical ใน repository และการแก้ renderer ของ Contact Sheet ตาม frozen inputs</div>
  <h2>1. วัตถุประสงค์และความสัมพันธ์กับงานนำเสนอเดิม</h2>
  <p>เอกสารนี้ทำหน้าที่อธิบายความหมายเชิงวิศวกรรมของตัวเลข, threshold, สถานะ <b>MODEL_ONLY_MARKER_ABSENT</b>, และวิธีอ่าน Contact Sheet รุ่นปรับปรุง เพื่อใช้คุยต่อกับผู้จัดการหรือผู้เกี่ยวข้องหลัง presentation</p>
  <p>web infographic เดิมยังคงเป็น artifact ที่นำเสนอไปแล้ว และไม่ได้ถูกแก้ไขในงานนี้</p>
  <h2>2. Executive Summary</h2>
  <ul>
    <li>Prototype ใช้ Faster R-CNN เพื่อเสนอ candidate location ของ dirty_spot_candidate ในภาพรังนก เพื่อช่วยจัดลำดับงานตรวจด้วยคน</li>
    <li>Prototype ไม่ได้ claim ว่าเป็น production model, expert-confirmed quality decision, หรือระบบรับรองความปลอดภัย/คุณภาพ</li>
    <li>Contact Sheet human review ยังจำเป็น เพราะ candidate ที่โมเดลเสนออาจเป็นตำแหน่งที่ marker เดิมไม่ครอบคลุม, อาจเป็นข้อผิดพลาดของโมเดล, หรืออาจต้องพิจารณาตามบริบทภาพจริง</li>
  </ul>
  {footer(1)}
</section>

<section class="sheet">
  <h2>3. Dataset and Evaluation Scope</h2>
  <div class="grid">
    <div class="box"><span class="metric">240</span>approved raw/marker pairs เป็นขอบเขต dataset ของ Prototype แต่ไม่ควรเรียกทั้งหมดว่า training images</div>
    <div class="box"><span class="metric">{runtime["tile_settings"]["validation_sources"]}</span>validation sources ที่ใช้ประเมิน operating points</div>
    <div class="box"><span class="metric">{runtime["tile_settings"]["validation_model_input_tiles"]}</span>actual model-input tiles ใน validation</div>
    <div class="box"><span class="metric">941</span>marker-derived Ground Truth denominator</div>
  </div>
  <h2>4. Model and Configuration</h2>
  <ul>
    <li>Model family: Faster R-CNN</li>
    <li>Architecture: {html.escape(runtime["model"]["architecture"])}</li>
    <li>Classes: background และ dirty_spot_candidate</li>
    <li>Maturity: engineering Prototype, not production-final</li>
    <li>Checkpoint SHA256: <span class="tag">{html.escape(checkpoint["SHA256"][:16])}...</span></li>
  </ul>
  <p>ค่าประเภท training loss หรือ epoch count ไม่ถูกนำมาอธิบายเป็น accuracy หรือ production performance ในเอกสารนี้ เพราะเอกสารนี้ยึดหลักฐาน evaluation/handoff ปัจจุบัน และไม่ได้ re-evaluate model</p>
  <h2>5. Threshold Explanation</h2>
  <ul>
    <li>Threshold 0.125 คือ primary operating point ที่ prioritize Recall เพื่อให้รายการที่ควรตรวจต่อหลุดน้อยลง</li>
    <li>Threshold 0.175 คือ comparison point ที่ลด workload สำหรับเทียบผล</li>
    <li>Threshold ไม่ใช่ model accuracy ค่า threshold ที่ต่ำลงจะเพิ่มจำนวน candidates ให้มนุษย์ตรวจ</li>
  </ul>
  {footer(2)}
</section>

<section class="sheet">
  <h2>6. Validation Results</h2>
  <table class="small results">
    <thead><tr><th>Threshold</th><th>GT denom.</th><th>Matched GT</th><th>Recall</th><th>Merged preds</th><th>Model-only count</th><th>Max preds/source</th><th>Pages</th></tr></thead>
    <tbody>{result_rows}</tbody>
  </table>
  <p>Model-only count ในตารางนี้หมายถึงจำนวนรายการ <b>MODEL_ONLY_MARKER_ABSENT</b>. Actual page counts มาจาก public Contact Sheet manifest ปัจจุบัน ไม่ใช่ฟิลด์ planning estimate ใน operating-point files</p>
  <h2>7. Definitions and Evaluation Rules</h2>
  <ul>
    <li><b>Recall</b>: สัดส่วน marker-derived GT ที่มี prediction จับคู่ได้ภายใต้ frozen matching rule</li>
    <li><b>Marker-derived Ground Truth</b>: จุดอ้างอิงจาก marker image เดิม ไม่ใช่ expert review ใหม่ในงานนี้</li>
    <li><b>MODEL_ONLY_MARKER_ABSENT</b>: merged prediction ที่ไม่ match แบบ one-to-one กับ original marker-derived GT ณ threshold ที่กำหนด</li>
    <li>Matching rule ที่ verified: prediction center distance to GT point <= max(12.0, raw_radius), one-to-one candidates sorted by distance, spot ID, prediction ID; ไม่ใช่ score-prioritized assignment</li>
    <li>Precision และ false-positive rate ยังไม่ควรสรุป เพราะยังไม่มี expert-confirmed review outcomes สำหรับ candidates เหล่านี้</li>
  </ul>
  {footer(3)}
</section>

<section class="sheet">
  <h2>8. Candidate-limit and Saturation</h2>
  <p>runtime config ระบุ candidate_limit = {runtime["detector_settings"]["candidate_limit"]}, internal_score_threshold = {runtime["detector_settings"]["internal_score_threshold"]}, ROI-head NMS threshold = {runtime["detector_settings"]["roi_head_nms_threshold"]}, และ cross-tile merge NMS IoU = {runtime["merge_settings"]["cross_tile_merge_nms_iou"]}</p>
  <div class="grid">
    <div class="box"><b>Primary 0.125</b><br>threshold-relevant capped tiles = {primary["threshold_relevant_capped_tiles"]}</div>
    <div class="box"><b>Comparison 0.175</b><br>threshold-relevant capped tiles = {comparison["threshold_relevant_capped_tiles"]}</div>
  </div>
  <p>เมื่อ threshold-relevant saturation เป็นศูนย์ในทั้งสอง operating points จึงไม่มีหลักฐานจากไฟล์ canonical ว่าค่าที่รายงานถูกจำกัดด้วย candidate cap ณ thresholds เหล่านี้</p>
  <p>จำนวน candidate ที่มากไม่ได้เป็น proof ว่าจุดนั้นเป็น defect และไม่ใช่เหตุผลเพียงพอสำหรับสรุปว่าต้อง retrain model ทันที ควรใช้ expert Contact Sheet review เป็นขั้นถัดไป</p>
  <h2>9. How to Read the Revised Contact Sheet</h2>
  <ul>
    <li>Left panel: <b>RAW IMAGE (NO OVERLAY)</b> เป็น genuine raw crop สำหรับดูภาพจริงโดยไม่มี model box, red marker, mask, heatmap หรือ annotation</li>
    <li>Right panel: <b>ORIGINAL MARKER IMAGE + MODEL LOCATION GUIDE</b> เป็น marker-image crop เดิมที่ยังเห็น red circles จาก source image และมี cyan guide แสดงตำแหน่งที่โมเดลเสนอ</li>
    <li>ให้ reviewer ดู left image ก่อน แล้วจึงใช้ right image เพื่อเทียบ model-proposed location กับ marker references เดิมใกล้เคียง</li>
  </ul>
  {footer(4)}
</section>

<section class="sheet">
  <h2>10. Representative Revised Contact Sheet Card</h2>
  <p>ตัวอย่าง deterministic QA case: <b>MO0125-000005</b>, Source 22, score 0.1719, threshold 0.125, page 001 position 05. ภาพนี้เป็น crop จาก sanitized public Contact Sheet page หลัง regeneration ไม่ได้ embed raw master image แยกต่างหาก</p>
  <figure>
    <img src="{image_uri}" alt="Representative revised Contact Sheet card MO0125-000005">
    <figcaption>Left panel has no synthetic overlay. Right panel preserves original marker circles and adds only the cyan model-location guide.</figcaption>
  </figure>
  {footer(5)}
</section>

<section class="sheet">
  <h2>11. Artifact and Download Explanation</h2>
  <ul>
    <li>Source repository: suwaroj95-spec/Pics-BirdNests</li>
    <li>Checkpoint is distributed separately as GitHub Release asset: final_checkpoint.pt</li>
    <li>Checkpoint checksum: {html.escape(checkpoint["SHA256"])}</li>
    <li>Handoff/source materials are under handoff/prototype_v1/ and public docs; raw and marker master datasets remain private</li>
  </ul>
  <h2>12. Limitations</h2>
  <ul>
    <li>Prototype ยังไม่ production-ready และไม่ใช่ expert-confirmed quality decision</li>
    <li>CUDA performance และ memory envelope ต้อง validate บน target machine ก่อน production planning</li>
    <li>MODEL_ONLY_MARKER_ABSENT ไม่ใช่ false positive โดยอัตโนมัติ และไม่ใช่ final quality label</li>
    <li>marker incompleteness เป็น possible limitation แต่ห้าม assume สำหรับแต่ละจุดโดยไม่มี review evidence</li>
    <li>raw และ marker master datasets ยังคงเป็น private data</li>
  </ul>
  <h2>13. Recommended Next Steps</h2>
  <ul>
    <li>ให้ domain expert review Contact Sheet candidates</li>
    <li>บันทึก reviewer outcomes ใน schema ที่ตรวจสอบย้อนกลับได้</li>
    <li>คำนวณ precision หรือ false-positive-related metrics หลังมี expert-confirmed outcomes เท่านั้น</li>
    <li>validate target-machine runtime ก่อนใช้วางแผน production</li>
  </ul>
  {footer(6)}
</section>

<section class="sheet">
  <h2>14. Version, Preparation Date, Commit and Sources</h2>
  <table>
    <tbody>
      <tr><th>Preparation date</th><td>{prep_date}</td></tr>
      <tr><th>Repository commit</th><td>{head}</td></tr>
      <tr><th>Document type</th><td>Supplementary clarification addendum after presentation</td></tr>
      <tr><th>Contact Sheet layout</th><td>{html.escape(manifest["layout_version"])}</td></tr>
    </tbody>
  </table>
  <h3>Source References Reviewed</h3>
  <ul class="refs">
    <li>docs/contact-sheets/contact-sheet-manifest.json</li>
    <li>handoff/prototype_v1/MODEL_CARD.md</li>
    <li>handoff/prototype_v1/EVALUATION_POLICY.md and prototype_evaluation_policy.json</li>
    <li>handoff/prototype_v1/prototype_runtime_config.json</li>
    <li>handoff/prototype_v1/prototype_operating_points.json</li>
    <li>handoff/prototype_v1/checkpoint_identity.json and checkpoint_release_manifest.json</li>
    <li>handoff/prototype_v1/PUBLICATION_AUTHORIZATION.md, KNOWN_LIMITATIONS.md, ARTIFACT_INDEX.md, README_HANDOFF.md</li>
    <li>controlled_20260711_fasterrcnn_model_only_contact_sheet_002 frozen CSV inputs</li>
    <li>controlled_20260711_validation_raw_marker_mapping_001 mapping provenance</li>
  </ul>
  <p class="note">Historical note: docs/model_readiness_report.md is a foundation-phase document dated 2026-06-24 and is not used here as the current final Prototype status.</p>
  {footer(7)}
</section>
</body>
</html>
"""


def main() -> int:
    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(build_html(), encoding="utf-8")
    print(OUTPUT_HTML)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
