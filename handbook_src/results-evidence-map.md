# Results And Evidence Map

## Existing Evidence Files

- `Crops/metadata.csv`: crop manifest and traceability fields
- `BacktestSelection/run_*/comparison_summary.csv`: selection system comparison
- `BacktestSelection/run_*/system_*/selected_manifest.csv`: selected crops per system
- `AnomalyDetection/run_*/summary.json`: anomaly run configuration and totals
- `AnomalyDetection/run_*/anomaly_review.csv`: human review queue
- `AnomalyDetection/run_*/kept_manifest.csv`: rows kept after anomaly ranking

## Documentation Position

Manual pages may mention real output filenames and run folders, but should avoid copying raw images, generated image binaries, or large row-level CSV content.

## Model Readiness

Verified documentation states the project is not yet a production classification model with final metrics.
