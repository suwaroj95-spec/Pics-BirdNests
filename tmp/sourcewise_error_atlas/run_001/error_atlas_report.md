# Source-wise Error Atlas

## Objective and Scope
วิเคราะห์ error แบบ crop-level จาก sourcewise robustness output เดิมเท่านั้น ไม่มีการ train/retrain model และไม่เปลี่ยน threshold หรือ feature

## Preflight
marker leakage decision = SAFE_TO_TRAIN, marker_like_count = 0; crop paths และ fold/source mapping ผ่าน preflight

## Error Totals
- true_positive: 1232
- true_negative: 1370
- false_positive: 611
- false_negative: 256

## Rankings
- Under-detection top 5: 9, 14, 5, 7, 8
- Over-flagging top 5: 4, 15, 1, 6, 11
- Overall business-risk top 5: 9, 6, 1, 4, 8

Business risk score = 0.50 * false_negative_rate + 0.25 * false_positive_rate + 0.25 * (1 - f1_dirty_positive)

## Threshold Variability
selected threshold range = 0.15 to 0.85; variability นี้ชี้ว่า threshold transfer ระหว่าง source ยังไม่นิ่ง

## Error-confidence Margin
ใช้ margin เพื่อจัดลำดับตัวอย่าง review เท่านั้น: false_positive ใช้ probability - threshold และ false_negative ใช้ threshold - probability

## Image-only Descriptive Statistics
คำนวณ grayscale, HSV saturation/value, Laplacian variance และ edge fraction จาก crop pixels เท่านั้น เพื่อใช้ตั้งสมมติฐานเรื่อง lighting/background/edge/context ไม่ใช่ feature training ใหม่

## Contact Sheets
สร้างเฉพาะ source ที่ถูกเลือกจาก top 5 ของ business risk, under-detection และ over-flagging; path อยู่ใน contact_sheets/

## Observed Facts
- วิเคราะห์ predictions ทั้งหมด 3469 rows
- source ที่มี business risk สูงสุด: 9
- มีทั้ง false_positive และ false_negative ในหลาย source จึงไม่ใช่ pattern เดี่ยวที่อธิบายได้ง่าย

## Evidence-supported Hypotheses
- Possible threshold-transfer issue จาก threshold range ที่กว้าง
- Possible visual/domain-shift issue ใน source ที่ over-flagging สูง
- Possible crop-policy or label-boundary issue ใน source ที่ under-detection สูงและมี high-margin false negative

## Unresolved Questions
- ต้องดู contact sheets ด้วยคนเพื่อแยกว่า error เกิดจาก lighting/background, crop context, หรือ label-boundary
- ยังไม่ควรสรุปเป็น whole-image quality หรือ PASS/FAIL decision

## Final Diagnosis
MIXED_OR_INCONCLUSIVE

## Exact Next Recommendation
A. Collect more independent source images
B. Review crop-policy and label-boundary cases
C. Standardize capture/lighting/background conditions
D. Design a later feature/model experiment after error review

No source image, crop, label, Ground Truth, or split manifest was modified.
No model was trained or retrained.
No Blue Marker or annotation metadata was used as a model feature.
This analysis does not produce bird-nest PASS/FAIL decisions.
