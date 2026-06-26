# Bird Nest Image Pipeline

Local research pipeline for preparing and reviewing bird-nest image crops. The current project focuses on data readiness, crop selection, and anomaly review before building a baseline classification model.

## 1. Create And Activate `.venv`

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run the project commands with the explicit interpreter path instead:

```powershell
.\.venv\Scripts\python.exe --version
```

## 2. Install Requirements

Install the core tools:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\InstallKit\requirements-core.txt
```

The installer wrapper can also create/update the environment, but it may use the network and modify `.venv`:

```powershell
.\InstallKit\install_project_tools.ps1
```

Optional tools are intentionally separate:

```powershell
.\InstallKit\install_project_tools.ps1 -WithAnnotation
.\InstallKit\install_project_tools.ps1 -WithTracking
```

## 3. Run The Panel

The local panel binds to `127.0.0.1` by default:

```powershell
.\.venv\Scripts\python.exe project_panel.py
```

Then open:

```text
http://127.0.0.1:8769/
```

To open the browser automatically:

```powershell
.\.venv\Scripts\python.exe project_panel.py --open
```

## 4. Run Crop Safely

The safe default keeps existing generated files:

```powershell
.\.venv\Scripts\python.exe crop_clean_patches.py --raw-dir RawPics --output-dir Crops
```

For a test run, prefer a new output directory:

```powershell
.\.venv\Scripts\python.exe crop_clean_patches.py --raw-dir RawPics --output-dir Crops_Test
```

## 5. Default vs `--keep-existing` vs `--clear-output`

- Default: keeps existing crop/debug files and writes/updates output files in the selected output directory.
- `--keep-existing`: explicit form of the default safe behavior.
- `--clear-output`: deletes previous generated `.jpg` files in `clean_negative` and `dirty_positive`, plus `.png`/`.jpg` files in `debug_masks`, under the selected output directory before writing new output.

Use `--clear-output` only after confirming the selected output directory is disposable or backed up.

## 6. Run Tests

Run the automated safety and smoke tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Compile-check the main scripts:

```powershell
.\.venv\Scripts\python.exe -m py_compile project_panel.py crop_clean_patches.py select_birdnest_samples.py anomaly_detection.py tests\test_smoke_and_safety.py
```

## 7. Output And Backup Cautions

Do not point experimental runs at important output folders unless they are backed up.

The main generated folders are:

- `Crops`
- `BacktestSelection`
- `AnomalyDetection`
- `AnomalyDetectionTest`
- `AnomalyDetectionPanelTest`

Before a destructive rerun, copy the current run folder or use a new output directory. The project is still in data-readiness and review mode; it does not yet contain a production baseline model with final metrics.

## 8. Documentation

Install documentation tools only when you need to build the manual:

```powershell
.\tools\build_documentation.ps1 -InstallDocsDependencies
```

Build the searchable manual under `docs/manual`:

```powershell
.\tools\build_documentation.ps1
```

Preview locally:

```powershell
.\.venv\Scripts\python.exe -m mkdocs serve
```

Verify executable documentation coverage:

```powershell
.\.venv\Scripts\python.exe tools\verify_documentation_coverage.py
```

Export the print handbook from `docs/manual/print-handbook.html` using Microsoft Edge `Save as PDF`; see `docs/HOW_TO_EXPORT_PDF.md`.

After adding or renaming executable source files, rerun the documentation build so the generated code reference and coverage manifest stay current.
