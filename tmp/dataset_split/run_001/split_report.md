# Source-level Dataset Split Report

## 1. Purpose

รอบนี้สร้าง source-level split manifests จาก final Ground Truth dataset โดยให้ทุก label จาก `image_id` เดียวกันอยู่ split เดียวกันเสมอ

## 2. Split Policy

- Split policy version: `source_level_80_10_10_v1`
- Deterministic seed: `20260624`
- TRAIN = 9 PASS + 3 FAIL = 12 source images
- VALIDATION = 1 PASS + 0 FAIL = 1 source image
- TEST = 1 PASS + 1 FAIL = 2 source images

## 3. Counts Per Split

- Train sources: 12, labels: 308
- Validation sources: 1, labels: 13
- Test sources: 2, labels: 51

## 4. PASS / FAIL Distribution

- Train: PASS 9, FAIL 3
- Validation: PASS 1, FAIL 0
- Test: PASS 1, FAIL 1

## 5. Source IDs

- Train: 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 15
- Validation: 9
- Test: 11, 13

## 6. Leakage Validation

Leakage detected: False

ทุก source image มี `distinct_split_count = 1` ใน audit

## 7. Why Validation Has No FAIL Image

ชุดข้อมูลนี้มีเพียง 15 source images และ user-approved 80/10/10 split ทำให้ validation มีได้เพียง 1 source image จึงไม่สามารถแทนทั้ง PASS และ FAIL ได้พร้อมกัน โดย policy เลือกให้ FAIL ส่วนใหญ่ไป train และให้ test มีทั้ง PASS และ FAIL

## 8. Limitations

- 15 source images are not enough for reliable model-performance claims
- 1 validation source and 2 test sources are only suitable for pilot development
- future data collection should add more independent source images before any deployment decision

## 9. Explicit Statements

- No image pixels were read or modified.
- No labels were altered.
- No model was trained.
- All labels from one source image remain in one split.
