# Final Ground Truth Finalization Report

## 1. Purpose

รอบนี้ finalize preliminary ground-truth labels ที่ผู้ใช้ตรวจ preview แล้ว ให้เป็น final dataset version สำหรับใช้ใน Ground Truth ระยะถัดไป

## 2. Final Policy Used

- 1 Blue Marker = 1 dirty spot
- 1 dirty cluster = 1 label
- Minimum blue-component area = 20 px
- Automatic marker merge = disabled
- Quality policy: 0-9 = 95/PASS, 10-20 = 90/PASS, 21-30 = 80/PASS, 31+ = 70/FAIL, unreadable = REVIEW

## 3. Radius Policy

Final Ground Truth radius ใช้ raw `enclosing_circle_radius` จาก Blue Marker เป็น authoritative radius ทุกแถว

`preview_radius = clamp(final radius, 16, 50)` ใช้สำหรับ preview/UI เท่านั้น ไม่ใช่ segmentation mask และไม่แทนค่า final radius

## 4. Record Counts

- Input manifest rows: 372
- Final manifest rows: 372
- Input image count: 15
- Final image count: 15
- Total dirty spots: 372

## 5. PASS / FAIL / REVIEW Summary

- PASS images: 11
- FAIL images: 4
- REVIEW images: 0
- Final confirmed images: 15
- Labels final confirmed: 372

## 6. Image 1 and 2 Provenance

ภาพ 1 และ 2 ถูกบันทึก alignment note ว่า `non-identical frame; visually verified marker-to-defect correspondence`

## 7. Radius Migration Summary

- Raw-radius labels: 372
- Preview radii clamped low: 3
- Preview radii clamped high: 85
- Labels whose final radius differs from preliminary preview radius: 88

## 8. Validation Results

- Required manifest columns validated
- `(image_id, spot_id)` uniqueness validated
- Numeric x/y and raw radius validated
- Quality score and PASS/FAIL mapping validated
- Input row count preserved exactly
- Automatic merge disabled validated

## 9. Explicit Statements

- Final Ground Truth labels were created from human-verified preliminary labels.
- No Blue Marker detection was rerun.
- No original or marked image was modified.
- No model was trained.
