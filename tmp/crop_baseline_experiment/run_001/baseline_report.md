# Crop-Level Binary Baseline Experiment

## วัตถุประสงค์และขอบเขต
ทดลอง baseline แบบ crop-level เพื่อแยก dirty_positive กับ clean_negative เท่านั้น ไม่ใช่การให้คะแนนคุณภาพทั้งภาพ ไม่ใช่ PASS/FAIL ของรังนกทั้งใบ และไม่ใช่ production decision

## Dataset และ Leakage Safeguards
ใช้ split จาก crop_lineage_manifest run_002 เท่านั้น ไม่มีการ split ใหม่ และ feature มาจาก pixel ของ crop หลัง resize เพื่อ feature extraction เท่านั้น
Marker leakage preflight: SAFE_TO_TRAIN, marker_like_count=0, low_blue_signal_count=8

## Feature Categories
grayscale intensity/statistics/histogram, Laplacian/Sobel edge texture, และ HSV color statistics/histograms

## Models
DummyClassifier(strategy='most_frequent') และ LogisticRegression pipeline with StandardScaler, class_weight='balanced'

## Threshold Selection
เลือก threshold จาก validation เท่านั้น: 0.35; precision>=0.80; selected highest recall, tie closest to 0.50

## Metrics
### dummy_baseline
- train: acc=0.5548, precision_dirty=0.0000, recall_dirty=0.0000, f1_dirty=0.0000, FN_dirty=1232, FP_dirty=0
- validation: acc=0.8295, precision_dirty=0.0000, recall_dirty=0.0000, f1_dirty=0.0000, FN_dirty=52, FP_dirty=0
- test: acc=0.4861, precision_dirty=0.0000, recall_dirty=0.0000, f1_dirty=0.0000, FN_dirty=204, FP_dirty=0
### logistic_regression
- train: acc=0.8233, precision_dirty=0.7465, recall_dirty=0.9131, f1_dirty=0.8215, FN_dirty=107, FP_dirty=382
- validation: acc=0.8918, precision_dirty=0.8065, recall_dirty=0.4808, f1_dirty=0.6024, FN_dirty=27, FP_dirty=6
- test: acc=0.8866, precision_dirty=0.8768, recall_dirty=0.9069, f1_dirty=0.8916, FN_dirty=19, FP_dirty=26

## Top Feature Coefficients
- gray_min: -3.465686710918 (clean_negative)
- value_hist_06: -1.991681027952 (clean_negative)
- sobel_magnitude_mean: -1.945499438290 (clean_negative)
- edge_pixel_fraction: 1.906292429753 (dirty_positive)
- gray_hist_12: 1.849148838608 (dirty_positive)
- saturation_hist_04: 1.707038392929 (dirty_positive)
- saturation_hist_06: -1.583715109286 (clean_negative)
- gray_p05: 1.542597399524 (dirty_positive)
- sobel_magnitude_std: 1.525472678299 (dirty_positive)
- gray_std: -1.438566136306 (clean_negative)

## Pilot Limitations
- มี independent source images เพียง 15 ภาพ
- validation ใช้ crop จาก source image 1 ภาพ
- test ใช้ crop จาก source images 2 ภาพ
- crop จาก source เดียวกันมี correlation สูง
- ผลนี้ยังไม่รองรับ deployment หรือคำกล่าวอ้างเรื่อง general performance

No source image, crop, label, Ground Truth, or split manifest was modified.
No Blue Marker or annotation metadata was used as a model feature.
Test results were not used to select the threshold.
This baseline does not produce bird-nest PASS/FAIL decisions.
