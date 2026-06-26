# Sample Selection Workflow

## Executable

`select_birdnest_samples.py`

## Purpose

Backtest crop selection systems เพื่อเลือก clean/dirty samples สำหรับ review และ anomaly detection

## Systems

- `system_1_opencv_content_contour`
- `system_2_edge_texture_sharpness`
- `system_3_numpy_frequency_balance`

## Main Outputs

- `BacktestSelection/run_*/comparison_summary.csv`
- `BacktestSelection/run_*/comparison_summary.json`
- `BacktestSelection/run_*/all_candidate_scores.csv`
- `BacktestSelection/run_*/system_*/selected_manifest.csv`

## Notes

ถ้าไม่ต้องการ copy selected image files ให้ใช้ `--no-copy`
