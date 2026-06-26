# BirdNests Print Handbook

[TOC]

## Executive Overview

BirdNests เป็น local research pipeline สำหรับเตรียมข้อมูลภาพรังนก ตรวจ crop และจัดลำดับ anomaly review ก่อน model production โครงการยังอยู่ใน data-readiness stage

## Architecture And Data Flow

`RawPics -> crop_clean_patches.py -> Crops/metadata.csv -> select_birdnest_samples.py -> BacktestSelection -> anomaly_detection.py -> AnomalyDetection -> human review`

`project_panel.py` เป็น local panel ที่ bind กับ `127.0.0.1`

## Data Folders

- `RawPics`: original/marked image pairs
- `Crops`: generated crop folders and `metadata.csv`
- `BacktestSelection`: selection run outputs
- `AnomalyDetection`: anomaly review outputs
- `handbook_src`: human-authored documentation source
- `docs/manual`: generated documentation website

## Label Policy And Ground Truth

Blue Marker หรือ จุดสีน้ำเงิน เป็น preliminary label ต้องผ่าน human verification ก่อนใช้เป็น ground truth. ต้องป้องกัน data leakage ด้วย source-level split และ marker leakage audit

## Crop Generation

Safe command:

```powershell
.\.venv\Scripts\python.exe crop_clean_patches.py --raw-dir RawPics --output-dir Crops
```

`--clear-output` เป็น destructive flag สำหรับ generated crop/debug files ใน output directory ที่เลือก

## Sample Selection

`select_birdnest_samples.py` สร้าง `BacktestSelection/run_*` และเปรียบเทียบ 3 selection systems

## Anomaly Detection

`anomaly_detection.py` สร้าง `anomaly_review.csv`, `kept_manifest.csv`, `all_anomaly_scores.csv`, `summary.json`, และ `summary.txt`

## Local Panel

```powershell
.\manage_project_panel.bat check
.\manage_project_panel.bat start
.\manage_project_panel.bat status
.\manage_project_panel.bat stop
```

## Installation And Testing

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\InstallKit\requirements-core.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Results And Evidence

Use filenames and schemas for evidence. Do not copy raw image binaries or full generated CSV rows into manual pages.

## Troubleshooting

Prefer new output folders for experiments. Use `manage_project_panel.bat check` for panel dependency checks.

## Glossary

- Blue Marker / จุดสีน้ำเงิน
- ground truth
- preview_radius
- source-level split
- data leakage
- marker leakage
- anomaly_review.csv
- metadata.csv

## Source References

See [Code Reference](code-reference/index.md) for generated module/function references.
