# Label Policy And Ground Truth Terminology

## Core Terms

- `clean`: ภาพหรือ crop ที่ไม่พบจุดสกปรกตาม policy
- `dirty`: ภาพหรือ crop ที่พบ dirty spot อย่างน้อย 1 จุด
- `uncertain`: ยังตัดสินไม่ได้ ต้อง human review
- `unreviewable`: คุณภาพภาพไม่พอสำหรับ train/evaluate หลัก
- `ground truth`: label ที่ผ่านการตรวจยืนยันแล้ว
- `preliminary label`: label ชั่วคราว เช่น Blue Marker ก่อน final review

## Blue Marker

Blue Marker หรือ จุดสีน้ำเงิน ใน marked image ใช้เป็นตำแหน่ง dirty spot เบื้องต้น แต่ก่อนใช้เป็น final metrics ต้องบันทึกผล human verification ใน manifest

## Data Policy

- source image เดียวกันต้องอยู่ split เดียวเท่านั้น
- ห้ามให้ crop จาก source เดียวกันหลุดไปทั้ง train และ test
- `marker leakage` ต้องตรวจว่า crop ไม่มี marker annotation ปนเข้า model input
- `preview_radius` เป็นค่าช่วย preview ไม่ใช่หลักฐาน performance ของ model
