# Crop Dataset Lineage Audit Report

## 1. Purpose

ตรวจสอบว่า crop dataset เดิมใน `Crops/metadata.csv` สามารถ trace กลับไปยัง source image และ source-level split ที่ finalized แล้วได้อย่างปลอดภัยหรือไม่ โดยไม่อ่าน image pixels และไม่แก้ไฟล์ข้อมูลเดิม

## 2. Actual Metadata Columns Found

`source_id, source_image, marked_image, output_file, label, x, y, width, height, patch_size, source_width, source_height, dirty_spot_id, dirty_center_x, dirty_center_y, blue_component_area, generation_method, marked_x, marked_y, original_x, original_y, original_match_score`

## 3. Crop Lineage Findings

- Crop metadata rows: 3469
- Resolved crop rows: 3469
- Unresolved crop rows: 0
- Duplicate crop path count: 0

## 4. Split Assignment Counts

- Train crops: 2767
- Validation crops: 305
- Test crops: 397

## 5. Dirty-positive Traceability Quality

- Dirty-positive crops: 1488
- Exact traceability: 1488
- Source-level only: 0
- Not traceable: 0

## 6. Clean-negative Traceability Quality

Clean-negative crops map safely to source image and split when `source_id/source_image` is present, but this audit does not claim that a clean-negative crop is defect-free unless traceability proves it.

## 7. Leakage Audit Result

Leakage detected: False

## 8. Reuse Decision

`REUSE_AS_IS`

## 9. Exact Blockers

- ไม่พบ blocker สำหรับการ reuse ตาม split manifest ปัจจุบัน

## 10. Recommended Next Action

Use `final_ground_truth_with_split.csv` / `source_split_manifest.csv` as the authority for any future training job, and if crops are reused, join crop rows to `crop_lineage_manifest.csv` so train/validation/test never mix source images.

## 11. Explicit Statements

- No crop or source image was modified.
- No Ground Truth or split manifest was modified.
- No model was trained.
- This audit does not claim that a clean-negative crop is defect-free unless traceability proves it.
