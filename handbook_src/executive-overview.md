# Executive Overview

## Purpose

BirdNests เป็น local research pipeline สำหรับเตรียมข้อมูลภาพรังนก ตรวจ crop ที่สร้างจากภาพต้นฉบับ และจัดลำดับภาพที่น่าสงสัยให้มนุษย์ review ก่อนนำไปสร้าง model

## Current Stage

Verified fact: README ระบุว่าโครงการยังอยู่ในช่วง data-readiness และ review mode ยังไม่มี production baseline model พร้อม final metrics

Workflow หลักคือ:

`RawPics -> crop_clean_patches.py -> Crops/metadata.csv -> select_birdnest_samples.py -> BacktestSelection -> anomaly_detection.py -> AnomalyDetection -> human review`

## Limitations

- ยังไม่ควร claim performance ของ model production
- Blue Marker เป็น preliminary label จนกว่าจะมี human-verified ground truth
- source-level split สำคัญมากเพื่อป้องกัน data leakage
- generated outputs มีข้อมูลจำนวนมากและไม่ควร copy รูปภาพ raw/crop เข้า manual

## Next Decisions

- ยืนยันเกณฑ์ pass/fail/review สำหรับ 70%
- ยืนยันรูปแบบ label สุดท้าย: point, circle, bounding box, mask หรือหลายแบบร่วมกัน
- เพิ่มจำนวน source images ก่อนสรุป final metrics
