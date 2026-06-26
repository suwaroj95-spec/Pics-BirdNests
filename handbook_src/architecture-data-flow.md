# Architecture And Data Flow

## Data Flow

1. `RawPics` เก็บ source image และ marked image pairs เช่น `1.jpg` และ `1m.jpg`
2. `crop_clean_patches.py` สร้าง crop และ `Crops/metadata.csv`
3. `select_birdnest_samples.py` เลือก sample ด้วย 3 systems และเขียน `BacktestSelection/run_*`
4. `anomaly_detection.py` ให้คะแนน anomaly และเขียน `anomaly_review.csv`, `kept_manifest.csv`, `all_anomaly_scores.csv`
5. Tools ใต้ `tools/` สร้าง marker analysis, ground truth, source-level split, lineage audit, marker leakage audit, baseline experiment, robustness และ error atlas
6. `project_panel.py` เป็น local panel สำหรับ run workflow บน `127.0.0.1`

## Important Boundaries

- Pipeline source code อยู่ที่ root และ `tools/`
- Tests อยู่ที่ `tests/`
- Human-authored manual source อยู่ที่ `handbook_src/`
- Generated manual website อยู่ที่ `docs/manual/`
- Existing infographic อยู่ที่ `docs/birdnests-workflow-infographic.html` และต้อง preserve
