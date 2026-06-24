# BirdNests Model Readiness Report

วันที่จัดทำ: 2026-06-24
สถานะ: Foundation phase ก่อนเทรนโมเดล

## 1. ตำแหน่ง Workflow ปัจจุบัน

Workflow ที่ตรวจยืนยันล่าสุดคือ:

`RawPics -> crop_clean_patches.py -> Crops/metadata.csv -> select_birdnest_samples.py -> BacktestSelection -> anomaly_detection.py -> AnomalyDetection -> human review`

`anomaly_detection.py` เป็น data-review/anomaly-ranking tool สำหรับช่วยคัดภาพหรือ crop ที่น่าสงสัย ไม่ใช่ production classifier สำหรับ clean/dirty หรือ pass/fail

## 2. Findings จาก Data Readiness Audit

ตรวจแบบ read-only จากโฟลเดอร์โปรเจกต์:

- พบ source original images: 15 ภาพ
- พบคู่ original + marked: 15 คู่
- ไม่พบ original ที่ขาด marked pair จากชื่อไฟล์
- ทุกคู่ที่อ่านได้มี dimensions ตรงกันที่ 1108 x 1476 pixels
- `Crops/metadata.csv` มี 3,469 rows
- label ใน metadata:
  - `clean_negative`: 1,981 rows
  - `dirty_positive`: 1,488 rows
- generation method:
  - `sliding_window_clean`: 1,981 rows
  - `centered_positive`: 372 rows
  - `jittered_positive`: 1,116 rows
- latest inspected `BacktestSelection/run_20260617_231439` มี comparison summary และ selected manifest
- latest inspected `AnomalyDetection/run_20260617_231517` มี `anomaly_review.csv`, `kept_manifest.csv`, และ `all_anomaly_scores.csv`

ตาม policy ผู้ใช้ Blue marker สามารถใช้เป็น preliminary label ได้ เพราะระบุว่าเป็นตำแหน่งจุดสกปรกจริงและ 1 marker = 1 จุดสกปรก อย่างไรก็ตาม ยังต้องมี ground-truth manifest ที่ reviewer ยืนยันก่อนใช้ train/evaluate ขั้นสุดท้าย

## 3. ความพร้อมของ Label

### Image-level classification

สถานะ: ยังไม่พร้อมสำหรับ final training/evaluation

เหตุผล:

- มีคู่ภาพเพียง 15 คู่ ซึ่งน้อยมากสำหรับ train/validation/test
- ยังไม่มี manifest กลางที่ระบุ `image_class`, `dirty_spot_count`, `cleanliness_score`, และ `pass_fail_status` หลัง review
- เกณฑ์ fail ยังขัดกับ mapping ปัจจุบัน เพราะ mapping ต่ำสุดคือ 70% แต่ fail ระบุว่าต่ำกว่า 70%

### Point / object detection

สถานะ: พร้อมระดับ preliminary data preparation แต่ยังไม่พร้อม final metrics

เหตุผล:

- มี Blue marker และ `dirty_spot_id` จาก pipeline ซึ่งช่วยเริ่มสร้าง point label ได้
- ต้องยืนยันพิกัดระดับ source image และ tolerance สำหรับถือว่า detect ถูก
- ถ้าต้องการ bounding box ต้องสร้าง/ยืนยัน `width` และ `height`

### Segmentation

สถานะ: ยังไม่พร้อม

เหตุผล:

- ยังไม่มี mask ground truth ที่ตรวจทานแล้วในระดับ pixel/area
- mask จาก crop pipeline หรือ marker image ยังไม่ควรถือเป็น segmentation ground truth ขั้นสุดท้าย

## 4. Blockers ก่อน Train โมเดล

- ต้องกรอก ground-truth manifest จาก template
- ต้องยืนยันขนาดขั้นต่ำของจุดสกปรก
- ต้องกำหนด merge rule เชิงตัวเลขสำหรับจุด/คราบที่อยู่ใกล้กัน
- ต้องแก้ policy pass/fail ให้ไม่คลุมเครือ โดยเฉพาะ `31 จุดขึ้นไป = 70%` แต่ fail ระบุว่าต่ำกว่า 70%
- ต้องกำหนดรูปแบบตำแหน่งที่ต้องการวัดผล: center point, circle, bounding box, หรือ mask
- ต้องเพิ่มจำนวน source images เพื่อให้ metrics เชื่อถือได้

## 5. Metrics Plan

### Confusion Matrix

สำหรับ image-level classification ให้เริ่มด้วย matrix ของ class:

| Actual \\ Predicted | clean/pass | dirty/fail | review |
| --- | ---: | ---: | ---: |
| clean/pass | TP pass | False Reject หรือ review | review |
| dirty/fail | False Accept | TP fail | review |
| review/unreviewable | misrouted | misrouted | correct review |

ถ้าใช้ multi-class cleanliness grade ให้ใช้ class:

- `clean_95`
- `dirty_90`
- `dirty_80`
- `dirty_70`
- `review`

แต่ KPI ทางธุรกิจควรสรุปซ้ำเป็น pass/fail/review เพื่อคำนวณ False Accept และ False Reject

### Accuracy

`Accuracy = จำนวนภาพที่ทำนายถูก / จำนวนภาพทั้งหมดที่นำมาวัดผล`

ไม่ควรรวมภาพ `unreviewable` ใน accuracy ของ clean/dirty ยกเว้นกำลังวัดความสามารถในการส่งภาพเข้าคิว review

### Precision

สำหรับ class สกปรก/ไม่ผ่าน:

`Precision_dirty = TP_dirty / (TP_dirty + FP_dirty)`

หมายถึง ในภาพที่ระบบบอกว่าสกปรก/ไม่ผ่าน มีสัดส่วนที่สกปรกจริงเท่าไร

### Recall

สำหรับ class สกปรก/ไม่ผ่าน:

`Recall_dirty = TP_dirty / (TP_dirty + FN_dirty)`

หมายถึง ในภาพที่สกปรก/ไม่ผ่านจริง ระบบจับได้กี่ภาพ

### F1-score

`F1 = 2 * Precision * Recall / (Precision + Recall)`

ใช้ดูสมดุลระหว่าง precision และ recall โดยเฉพาะ class สกปรก/ไม่ผ่าน

### False Reject

`False Reject Rate = จำนวนภาพของดีที่ระบบ reject / จำนวนภาพของดีจริง`

นิยามธุรกิจ: ของดีแต่ระบบบอกเสีย หรือภาพที่ควรผ่านแต่ระบบทำนายว่าไม่ผ่าน

### False Accept

`False Accept Rate = จำนวนภาพของเสียที่ระบบปล่อยผ่าน / จำนวนภาพของเสียจริง`

นิยามธุรกิจ: ของเสียแต่ระบบบอกผ่าน ความเสี่ยงนี้สำคัญที่สุดเพราะรังนกเป็นของรับประทาน

### Review Rate

`Review Rate = จำนวนภาพที่ส่งให้คนตรวจซ้ำ / จำนวนภาพทั้งหมด`

เป้าหมายไม่เกิน 8% แต่ต้องไม่ลด review rate จนทำให้ False Accept สูงขึ้น

## 6. Image-level vs Spot-level Metrics

### Image-level

วัดจากผลต่อภาพ:

- cleanliness score
- pass/fail/review
- confusion matrix
- accuracy, precision, recall, F1
- false reject, false accept

### Spot-level detection

วัดจากตำแหน่งจุดสกปรก:

- จำนวนจุดที่ detect ถูก
- จำนวนจุดที่ miss
- จำนวนจุดที่ detect เกิน
- precision/recall ของจุด
- mean center distance หรือ matching tolerance
- IoU เฉพาะกรณีมี bounding box/mask

ยังไม่ควรรายงาน spot-level metric จริงจนกว่าจะมีตำแหน่ง ground truth ที่ reviewer ยืนยันครบ

## 7. การประเมิน Threshold Pass/Fail

ใช้ mapping:

- 0-9 จุด -> 95%
- 10-20 จุด -> 90%
- 21-30 จุด -> 80%
- 31 จุดขึ้นไป -> 70%

policy ปัจจุบันระบุว่าผ่านเมื่อ 80% ขึ้นไป และไม่ผ่านเมื่อต่ำกว่า 70% จึงต้องตัดสินเพิ่มว่า 70% เป็น `ไม่ผ่าน`, `ต้องตรวจซ้ำ`, หรือ `ผ่านแบบต่ำสุด`

ข้อเสนอสำหรับ validation phase:

- `>= 80%`: pass
- `70%`: review หรือ fail ตามความเสี่ยงธุรกิจ
- ภาพไม่ชัด: review

ถ้าเน้นลด False Accept แนะนำให้กำหนด 70% เป็น `fail` หรืออย่างน้อย `review` ไม่ควรปล่อยผ่านอัตโนมัติ

## 8. Model Approach Recommendation

### Stage 1: OpenCV + rule-based dirty spot visualizer

เหมาะสมที่สุดสำหรับเฟสถัดไป เพราะ:

- ข้อมูลมีเพียง 15 source pairs
- Blue marker ช่วยสร้าง preliminary point labels
- อธิบายง่าย ดูผลวงจุดได้เร็ว
- ใช้เป็น baseline สำหรับนับจุดและสร้าง preview

ผลลัพธ์ที่ควรได้:

- ภาพ preview ที่วงจุดสกปรก
- จำนวนจุด
- cleanliness score ตาม policy
- CSV report

### Stage 2: Feature-based + scikit-learn image-level classifier

ทำได้เมื่อ manifest มี image-level label ที่ reviewer ยืนยันแล้ว

เหมาะสำหรับ:

- baseline clean/dirty/pass/fail
- confusion matrix และ KPI image-level
- model ที่เบาและ maintain ง่าย

ยังไม่ควร claim performance สูงจนกว่าจะมีข้อมูลมากกว่า 15 source pairs

### Stage 3: Object detection

ทำเมื่อมี bounding box หรือ circle/point label ที่ตรวจทานแล้วมากพอ

เหมาะสำหรับ:

- วงกรอบหรือวงกลมรอบจุดสกปรก
- นับจำนวนจุดจากตำแหน่งที่ detect

### Stage 4: Segmentation

ทำเมื่อมี mask label ที่ตรวจทานแล้ว

เหมาะสำหรับ:

- mask ระบายบริเวณสกปรก
- คำนวณพื้นที่สกปรก
- heatmap หรือ segmentation overlay

ยังไม่ใช่ตัวเลือกแรกในข้อมูลปัจจุบัน เพราะ mask ground truth ยังไม่พร้อม

## 9. Ready / Not Ready Decision

สถานะ: Not Ready for Model Training

เหตุผล:

- ยังไม่มี ground-truth manifest ที่ reviewer ยืนยันครบ
- จำนวน source image pairs ยังน้อย
- pass/fail threshold ยังมีจุดคลุมเครือที่ 70%
- segmentation/object detection labels ยังไม่ครบตามรูปแบบที่ต้องวัดผล

สถานะที่พร้อมแล้ว:

- พร้อมสร้าง label policy
- พร้อมสร้าง dataset manifest template
- พร้อมสร้าง review queue
- พร้อมเริ่ม ground-truth readiness audit และ manual review
- พร้อมออกแบบ baseline evaluation pipeline หลัง manifest ถูกกรอก

## 10. ความเสี่ยง

- False Accept เป็นความเสี่ยงสูงสุด ต้องให้ priority เหนือ accuracy รวม
- Dataset ขนาดเล็กอาจทำให้ model overfit และ metrics แกว่งมาก
- Crop-level leakage จะทำให้ test score สูงเกินจริงถ้าไม่ split ตาม source image
- Blue marker อาจไม่เท่ากับ segmentation mask จริง ต้องระวังถ้าต้องวัด mask/heatmap
- ภาพที่มืด/เบลออาจทำให้ระบบปล่อยผ่านผิด หากไม่มี class `unreviewable`
