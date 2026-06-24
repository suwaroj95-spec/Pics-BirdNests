# Roadmap งานวิจัยระบบคัดแยกรังนกสะอาด / สกปรก 70%, 80%, 90%

## สถานะปัจจุบัน

- มี pipeline สำหรับสร้าง crop จากภาพต้นฉบับ
- มีระบบเลือกตัวอย่างภาพด้วย 3 วิธี ได้แก่ OpenCV content/contour, edge-texture-sharpness, และ NumPy frequency/variance
- มีระบบ anomaly detection แบบ feature-based เพื่อคัดภาพที่น่าสงสัยให้คนตรวจ
- ยังไม่พบไฟล์โมเดลที่ train แล้ว เช่น `.pt`, `.onnx`, `.pkl`, `.joblib`, `.h5`
- สรุป: ตอนนี้มีระบบเตรียมข้อมูลและตรวจคุณภาพข้อมูลแล้ว แต่ยังไม่มี production classification model

## Phase 1: Data Readiness

เป้าหมายคือทำให้ชุดข้อมูลสะอาดพอสำหรับ train model

1. รัน `project_panel.py` เพื่อสร้าง crop, backtest selection, และ anomaly review
2. เปิด `AnomalyDetection/<run>/anomaly_review.csv` และ preview เพื่อตรวจภาพผิดปกติ
3. แยกผล review เป็นกลุ่ม:
   - ใช้ได้
   - crop ผิดตำแหน่ง
   - แสง/เบลอ/พื้นหลังมากเกินไป
   - marker หรือ mask ผิด
4. ใช้ `kept_manifest.csv` เป็นฐานข้อมูลภาพที่ผ่านการคัดกรอง

เกณฑ์ผ่าน phase นี้: มีภาพที่เชื่อถือได้อย่างน้อยหลายร้อยภาพต่อ class และมี record ว่าภาพไหนถูกตัดออกเพราะอะไร

## Phase 2: Label Definition

เป้าหมายคือกำหนดนิยาม label ให้ชัดก่อน train

Class ที่แนะนำ:

- `clean`
- `dirty_70`
- `dirty_80`
- `dirty_90`
- `reject_or_uncertain`

ต้องเขียนเกณฑ์ให้คน label ตรงกัน เช่น dirty 70%, 80%, 90% หมายถึงระดับความสกปรกจากพื้นที่คราบ, ความเข้มสี, หรือมาตรฐานของผู้เชี่ยวชาญ หากยังไม่มีนิยามเชิงตัวเลข ให้เริ่มจาก expert label ก่อน แล้วค่อย calibrate ด้วย feature ภาพภายหลัง

เกณฑ์ผ่าน phase นี้: คน label 2 คนให้ผลตรงกันสูงพอ และมีตัวอย่าง reference image ของแต่ละระดับ

## Phase 3: Baseline Model

เป้าหมายคือสร้างโมเดลแรกที่เบา อธิบายได้ และรันบนเครื่องทั่วไปได้

เครื่องมือที่แนะนำ:

- OpenCV + NumPy สำหรับ feature extraction
- scikit-learn สำหรับ Logistic Regression, Random Forest, SVM, หรือ Gradient Boosting
- pandas + matplotlib สำหรับวิเคราะห์ผล

ผลลัพธ์ที่ต้องมี:

- train/validation/test split แยกตาม source image เพื่อกันภาพใกล้เคียงหลุดข้ามชุด
- confusion matrix ของ `clean`, `dirty_70`, `dirty_80`, `dirty_90`
- precision/recall/F1 โดยเน้น recall ของ dirty
- บันทึกโมเดลเป็น `.joblib`

เกณฑ์ผ่าน phase นี้: ได้ baseline model ที่วัดผลซ้ำได้ และรู้ว่าพลาดกับ class ไหนมากที่สุด

## Phase 4: Deep Learning Candidate

ทำเมื่อมี label เพียงพอและ baseline เริ่มตัน

ทางเลือก:

- EfficientNet/MobileNet/ResNet ขนาดเล็กสำหรับ classification
- Anomalib/PatchCore สำหรับตรวจสิ่งผิดปกติหากข้อมูล dirty มีน้อย
- ONNX export เพื่อ deploy ง่าย

ยังไม่ควรเริ่ม phase นี้ก่อน label พร้อม เพราะโมเดลลึกจะดูแม่นบนข้อมูลเล็กได้ง่าย แต่ใช้งานจริงอาจไม่เสถียร

เกณฑ์ผ่าน phase นี้: deep model ชนะ baseline บน test set ที่แยก source จริง และ latency ยังรับได้กับเครื่องเป้าหมาย

## Phase 5: Decision Policy

เป้าหมายคือแปลงผลโมเดลเป็นการตัดสินใจใช้งานจริง

ตัวอย่าง policy:

- `clean`: ปล่อยผ่าน
- `dirty_70`: ส่งตรวจซ้ำหรือจัดเกรดต่ำ
- `dirty_80`: reject หรือส่งทำความสะอาด
- `dirty_90`: reject ทันที
- confidence ต่ำ: ส่ง human review

ต้องกำหนด threshold จาก validation set ไม่ใช่เลือกด้วยความรู้สึก

## Phase 6: Deployment And Monitoring

เป้าหมายคือทำให้ระบบใช้ซ้ำได้และตรวจสอบย้อนหลังได้

สิ่งที่ควรมี:

- script inference แบบ command line
- dashboard ตรวจภาพและผลทำนาย
- log input, prediction, confidence, model version
- periodic review ทุกครั้งที่มีภาพจากกล้องหรือ lot ใหม่
- retraining schedule เมื่อข้อมูลใหม่สะสมพอ

## Roadmap แบบย่อ

| ช่วง | งานหลัก | ผลลัพธ์ |
| --- | --- | --- |
| สัปดาห์ 1 | review anomaly และนิยาม label | dataset ที่เชื่อถือได้ |
| สัปดาห์ 2 | label clean/dirty_70/80/90 | labeled manifest |
| สัปดาห์ 3 | train baseline scikit-learn | `.joblib` model + metrics |
| สัปดาห์ 4 | ปรับ threshold และทำ dashboard | policy สำหรับคัดแยก |
| เดือน 2 | ทดลอง deep learning ถ้าข้อมูลพอ | model candidate เทียบ baseline |
| เดือน 3 | deploy ทดลองกับ workflow จริง | inference log + monitoring |
