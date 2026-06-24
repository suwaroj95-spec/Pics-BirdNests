# Crop Marker Leakage Audit

## วัตถุประสงค์
ตรวจว่า crop image ที่มีอยู่มี pixel หรือ component สีฟ้าที่คล้าย Blue Marker annotation หรือไม่ เพื่อป้องกันไม่ให้โมเดล classification ในอนาคตเรียนรู้ artifact จากการ annotate แทนสิ่งสกปรกจริง

## Logic ที่ใช้ตรวจ Blue Marker
ใช้ช่วงสี HSV จาก pipeline เดิม: lower (90, 50, 50), upper (140, 255, 255); mask ผ่าน MORPH_CLOSE ด้วย elliptical kernel 5x5 และนับ component ที่มีพื้นที่ตั้งแต่ 20 px เป็น marker-like candidate

## จำนวนที่ตรวจ
- Crops inspected: 3469
- dirty_positive: 1488
- clean_negative: 1981

## ผลตาม split
- train: crops 2767, marker-like 0
- validation: crops 305, marker-like 0
- test: crops 397, marker-like 0

## ผลตาม class
- dirty_positive marker-like rate: 0.00000000
- clean_negative marker-like rate: 0.00000000
- การกระจุกตัว: ไม่พบ marker-like candidate

## Candidate
- none: 3461
- low_blue_signal: 8
- marker_like: 0
- marker-like rate: 0.00000000

## Decision
SAFE_TO_TRAIN

## Next Action
หาก decision เป็น MANUAL_REVIEW_REQUIRED ให้เปิด review samples และตรวจด้วยสายตาว่าพื้นที่สีฟ้าเป็น marker annotation หรือเป็นสีธรรมชาติของภาพ ก่อนนำ crop เหล่านี้ไปใช้ train model

No crop, source image, label, Ground Truth, or split manifest was modified.
No model was trained.
This audit detects marker-like blue regions; human review is required before treating a candidate as annotation leakage.
