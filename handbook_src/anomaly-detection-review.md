# Anomaly Detection And Review Workflow

## Executable

`anomaly_detection.py`

## Purpose

จัดอันดับ crops ที่น่าสงสัยด้วย feature-based anomaly scoring เพื่อให้ human review ก่อนใช้ข้อมูลต่อ

## Methods

- `isolation_forest`
- `lof`
- `pca`

## Main Outputs

- `all_anomaly_scores.csv`
- `anomaly_review.csv`
- `kept_manifest.csv`
- `summary.json`
- `summary.txt`
- preview contact sheets

## Review Intent

`anomaly_review.csv` เป็น queue สำหรับตรวจภาพที่ผิดปกติ ไม่ใช่ production clean/dirty classifier
