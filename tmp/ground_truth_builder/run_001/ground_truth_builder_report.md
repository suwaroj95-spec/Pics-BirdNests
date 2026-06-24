# Ground Truth Builder Report

## 1. Purpose

รอบนี้สร้าง preliminary ground-truth labels จาก Blue Marker ที่ผู้ใช้ยืนยันแล้วว่า marker สอดคล้องกับจุดสกปรกจริงบนภาพ original โดยไม่ train model และไม่แก้ไขภาพต้นฉบับ

## 2. Policy Values Used

- Minimum blue-component area: 20 px
- Automatic marker merge: disabled
- Radius rule: clamp(enclosing_circle_radius, 16, 50)
- Quality rule: 0-9 = 95/PASS, 10-20 = 90/PASS, 21-30 = 80/PASS, 31+ = 70/FAIL
- Images 1 and 2: non-identical frame; visually verified marker-to-defect correspondence

## 3. Pair Discovery Summary

- Pair count: 15
- Processed images: 15
- Skipped images: 0

## 4. Marker Detection Summary

- Total dirty spots generated: 372
- Minimum component area: 20 px
- Marker source: blue_marker
- Label confidence: preliminary_verified

## 5. Image Score Summary

- PASS images: 11
- FAIL images: 4
- REVIEW images: 0

## 6. Review Queue

- Images with review rows: ['1', '2', '3', '5', '7', '8', '9', '10', '11', '12', '13', '14', '15']
- Images with manual alignment note: 2

## 7. Output Files

- `ground_truth_manifest.csv`: one row per dirty spot
- `image_quality_summary.csv`: one row per original image
- `review_queue.csv`: images needing preview confirmation or attention
- `generation_summary.json`: machine-readable generation summary
- `previews/`: original-image previews with point/circle labels

## 8. Important Limitations

- This run generates preliminary ground-truth labels.
- No model was trained.
- Preview confirmation is required before labels are final.
- Circle radius is for point/circle label visualization only; it is not a segmentation boundary.
- No automatic warp, translation, or coordinate correction was applied.

Output directory: `D:\Pics-BirdNests\tmp\ground_truth_builder\run_001`
