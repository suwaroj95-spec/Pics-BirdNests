# Sourcewise Crop Robustness Evaluation

## วัตถุประสงค์และขอบเขต
ประเมินความผันผวนแบบ leave-one-source-out ของ crop-level classifier สำหรับ dirty_positive vs clean_negative เท่านั้น ไม่ใช่ quality scoring ทั้งภาพ และไม่ใช่ production model

## ความต่างจาก baseline เดิม
baseline เดิมใช้ train/validation/test split ที่ finalize แล้วหนึ่งครั้ง ส่วน evaluation นี้วน 15 folds โดย hold out source image ทีละภาพ เลือก threshold จาก inner validation source ของ fold นั้นเท่านั้น แล้วประเมิน outer source หนึ่งครั้ง

## Leakage Safeguards
ใช้ feature extraction จาก crop pixels เท่านั้น และ import feature schema จาก baseline script เดิม ไม่ใช้ source ID, crop path, PASS/FAIL, quality score, Blue Marker หรือ annotation metadata เป็น feature

## Nested Threshold Selection
แต่ละ fold ใช้ source ถัดไปในลำดับเป็น validation source และ source ที่เหลือเป็น training source; outer test data ไม่ถูกใช้เลือก threshold

## Per-Source Metrics
| source | threshold | precision | recall | f1 | FN dirty | FP dirty |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 0.20 | 0.55102041 | 0.77884615 | 0.64541833 | 23 | 66 |
| 2 | 0.75 | 1.00000000 | 0.82926829 | 0.90666667 | 28 | 0 |
| 3 | 0.70 | 0.77777778 | 0.95454545 | 0.85714286 | 6 | 36 |
| 4 | 0.25 | 0.32510288 | 0.94047619 | 0.48318043 | 5 | 164 |
| 5 | 0.75 | 1.00000000 | 0.56000000 | 0.71794872 | 44 | 0 |
| 6 | 0.25 | 0.30256410 | 0.86764706 | 0.44866920 | 9 | 136 |
| 7 | 0.65 | 1.00000000 | 0.69444444 | 0.81967213 | 33 | 0 |
| 8 | 0.30 | 0.56074766 | 0.75000000 | 0.64171123 | 20 | 47 |
| 9 | 0.60 | 0.95238095 | 0.38461538 | 0.54794521 | 32 | 1 |
| 10 | 0.45 | 0.71428571 | 0.87500000 | 0.78651685 | 10 | 28 |
| 11 | 0.20 | 0.76282051 | 0.95967742 | 0.85000000 | 5 | 37 |
| 12 | 0.20 | 0.87078652 | 0.99358974 | 0.92814371 | 1 | 23 |
| 13 | 0.55 | 0.92000000 | 0.86250000 | 0.89032258 | 11 | 6 |
| 14 | 0.85 | 0.97058824 | 0.55000000 | 0.70212766 | 27 | 1 |
| 15 | 0.15 | 0.58750000 | 0.97916667 | 0.73437500 | 2 | 66 |

## Distribution
- accuracy: median=0.81990521, mean=0.7598490266666668, min=0.46349206, max=0.9178744, p25=0.664868195, p75=0.870635935
- precision_dirty_positive: median=0.77777778, mean=0.7530383173333334, min=0.3025641, max=1.0, p25=0.57412383, p75=0.9614845949999999
- recall_dirty_positive: median=0.8625, mean=0.7986517860000001, min=0.38461538, max=0.99358974, p25=0.72222222, p75=0.94751082
- f1_dirty_positive: median=0.734375, mean=0.7306560386666666, min=0.4486692, max=0.92814371, p25=0.64356478, p75=0.8535714299999999
- false_negative_dirty_count: median=11.0, mean=17.066666666666666, min=1.0, max=44.0, p25=5.5, p75=27.5
- false_positive_dirty_count: median=28.0, mean=40.733333333333334, min=0.0, max=164.0, p25=1.0, p75=56.5

## Best / Worst
- Best source by F1: 12
- Worst source by F1: 6

## Interpretation
ผลหลักคือ distribution ระดับ source ไม่ใช่ pooled crop accuracy เพราะ crop ใน source เดียวกัน correlated กัน และ source-to-source variation เป็น risk หลักของ pilot นี้

## Limitations
- 15 independent source images remain too few for deployment claims
- each fold uses only one validation source
- results are for pilot robustness assessment only

## Final Decision
BASELINE_UNSTABLE

No source image, crop, label, Ground Truth, or split manifest was modified.
No Blue Marker or annotation metadata was used as a model feature.
Outer test data was never used to select its fold threshold.
This evaluation does not produce bird-nest PASS/FAIL decisions.
