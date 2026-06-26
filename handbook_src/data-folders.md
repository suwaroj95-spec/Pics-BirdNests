# Data Folders And Generated-Output Boundaries

## Raw Inputs

`RawPics` มี original/marked JPEG pairs เช่น `1.jpg`, `1m.jpg` ถึง `15.jpg`, `15m.jpg`

Manual นี้ไม่ inspect หรือ embed raw image pixels

## Generated Outputs

- `Crops`: crop images, debug masks, `metadata.csv`
- `BacktestSelection`: selected manifests, comparison summaries, copied selected samples
- `AnomalyDetection`: anomaly scores, review queues, kept manifests, previews
- `AnomalyDetectionTest`, `AnomalyDetectionPanelTest`: test-like anomaly output folders
- `tmp`: local temporary outputs, PID/log files, documentation build intermediates if any

## Documentation Boundary

Code reference covers executable source files only:

- Python: `*.py`
- PowerShell: `*.ps1`
- Batch: `*.bat`
- Requirements: `requirements*.txt`

Excluded from function-level documentation:

- raw images
- crop images
- generated previews
- full CSV rows
- `.venv`, `venv`, cache folders
- generated run artifacts
