# BirdNests Dataset Manifest Schema

เวอร์ชันเอกสาร: `v0.1-pretraining`
วันที่จัดทำ: 2026-06-24

## 1. หลักการ Split Dataset

ต้องแบ่ง dataset ตาม `source_image` หรือ `image_id` ระดับภาพต้นฉบับเท่านั้น ห้ามแบ่งตาม crop เพียงอย่างเดียว เพราะ crop หลายภาพอาจมาจาก source เดียวกันและมีลักษณะใกล้เคียงกันมาก หาก crop จาก source เดียวกันหลุดไปทั้ง train และ test จะเกิด data leakage และทำให้ metrics ดูดีเกินจริง

สัดส่วนที่ผู้ใช้เลือก:

- Train: 80%
- Validation: 10%
- Test: 10%

ด้วยข้อมูลปัจจุบันที่มี source image pairs 15 คู่ สัดส่วนนี้จะได้ประมาณ:

- Train: 12 source images
- Validation: 1-2 source images
- Test: 1-2 source images

จำนวนนี้ยังเล็กมากสำหรับประเมิน final metrics อย่างมั่นคง จึงควรใช้เป็น pilot split เท่านั้น และควรเพิ่มข้อมูลก่อนสรุป performance จริง

## 2. กฎป้องกัน Data Leakage

- source image เดียวกันต้องอยู่ split เดียวเท่านั้น
- crop ทุก crop ที่มาจาก source เดียวกันต้องตาม split ของ source นั้น
- dirty spot เดียวกันที่ถูก crop หลายครั้งต้องมี `spot_id` เดียวกันหรือ map กลับได้จาก manifest
- ห้ามใช้ anomaly score หรือผลจาก test set เพื่อปรับ threshold หลังปิด split แล้ว
- validation ใช้เลือก threshold/model ส่วน test ใช้วัดผลครั้งสุดท้ายเท่านั้น

## 3. Ground Truth Manifest

ไฟล์ template: `templates/birdnests_ground_truth_manifest.csv`

ใช้เก็บ label ที่ตรวจทานแล้วในระดับภาพและระดับจุดสกปรก โดยหนึ่งภาพอาจมีหลายแถวถ้ามีหลายจุดสกปรก

| Column | ความหมาย |
| --- | --- |
| `image_id` | รหัสภาพระดับ source เช่น `src_001` |
| `source_image` | path หรือชื่อไฟล์ original |
| `marked_image` | path หรือชื่อไฟล์ marked |
| `split` | `train`, `validation`, `test`, หรือว่างไว้ก่อน split |
| `review_status` | `pending`, `reviewed`, `needs_recheck`, `excluded` |
| `reviewer` | ผู้ตรวจหลัก |
| `reviewed_at` | วันที่ตรวจในรูปแบบ ISO เช่น `2026-06-24` |
| `image_class` | `clean`, `dirty`, `uncertain`, `unreviewable` |
| `dirty_spot_count` | จำนวนจุดสกปรกระดับภาพหลัง review |
| `cleanliness_score` | 95, 90, 80, 70 หรือตาม policy รุ่นถัดไป |
| `pass_fail_status` | `pass`, `fail`, `review` |
| `spot_id` | รหัสจุดสกปรกในภาพ เช่น `src_001_spot_001` |
| `x_center` | พิกัด x จุดศูนย์กลางในภาพ source |
| `y_center` | พิกัด y จุดศูนย์กลางในภาพ source |
| `width` | ความกว้าง bounding box ถ้ามี |
| `height` | ความสูง bounding box ถ้ามี |
| `mask_path` | path mask ถ้ามี segmentation label |
| `marker_source` | `blue_marker`, `human_box`, `human_mask`, `model_suggestion`, หรืออื่น ๆ |
| `label_confidence` | `confirmed`, `preliminary`, `uncertain` |
| `notes` | หมายเหตุ |

## 4. Review Queue

ไฟล์ template: `templates/birdnests_review_queue.csv`

ใช้เก็บภาพหรือ crop ที่ควรให้คนตรวจซ้ำ โดยดึงจาก anomaly detection, ความไม่มั่นใจของโมเดล, หรือข้อผิดปกติจาก pipeline

| Column | ความหมาย |
| --- | --- |
| `image_id` | รหัสภาพหรือ crop ที่ต้องตรวจ |
| `source_image` | ภาพต้นทาง |
| `anomaly_run` | run directory หรือ run id ของ anomaly detection |
| `anomaly_score` | คะแนน anomaly ถ้ามี |
| `priority` | `high`, `medium`, `low` |
| `suggested_class` | class ที่ระบบแนะนำ |
| `review_status` | `pending`, `reviewed`, `needs_recheck`, `excluded` |
| `reviewer` | ผู้ตรวจ |
| `reviewed_at` | วันที่ตรวจ |
| `final_class` | class หลังคนตรวจ |
| `dirty_spot_count` | จำนวนจุดหลังคนตรวจ |
| `cleanliness_score` | คะแนนหลังคนตรวจ |
| `notes` | หมายเหตุ |

## 5. การจัดการภาพ Uncertain / Unreviewable

- `uncertain` ใช้เก็บภาพที่ยังตัดสินไม่ได้ ต้องส่งให้ผู้ตรวจยืนยัน
- `unreviewable` ใช้เก็บภาพที่ตรวจไม่ได้เพราะคุณภาพภาพ ไม่ควรใช้ train/evaluate class clean/dirty
- ภาพทั้งสองกลุ่มควรเก็บไว้เพื่อปรับปรุง workflow และสร้าง rule ส่งคนตรวจซ้ำ แต่ห้ามนับใน final metrics ของ clean/dirty จนกว่าจะมีคำตัดสินสุดท้าย

## 6. Reproducibility

ก่อนสร้าง split จริงต้องบันทึก:

- `random_seed` ที่ใช้แบ่งชุดข้อมูล
- วันที่สร้าง split
- version ของ label policy
- source image list ที่ใช้
- กฎ exclude ภาพ uncertain/unreviewable

แนะนำ random seed เริ่มต้น: `42` เพื่อให้สอดคล้องกับ pipeline ปัจจุบัน

## 7. ข้อมูลขั้นต่ำก่อน Generate Split

ต้องมีข้อมูลต่อไปนี้ก่อนสร้าง train/validation/test split จริง:

- คู่ `source_image` และ `marked_image`
- ผลตรวจว่า image pair ขนาดตรงกัน
- `image_class` ระดับภาพ
- `dirty_spot_count` หลัง review
- `cleanliness_score`
- `pass_fail_status`
- reviewer และวันที่ review
- ตำแหน่งจุดสกปรกอย่างน้อยแบบ center point ถ้าต้องประเมินการวงจุด

ถ้าต้องการ segmentation ต้องมี `mask_path` ที่ตรวจทานแล้ว ไม่ใช่เพียง Blue marker หรือ crop mask จาก pipeline
