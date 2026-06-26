# `tools/run_crop_baseline_experiment.py`

Generated content. Do not edit by hand.

- Purpose: Runs a handcrafted crop baseline experiment with safety checks.
- Source path: `tools/run_crop_baseline_experiment.py`
- Source link: [tools/run_crop_baseline_experiment.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/tools/run_crop_baseline_experiment.py)
- Risk notes: Writes experiment outputs and may create model/report artifacts.

## Top-Level Classes And Functions

### `ExperimentError`

- Kind: `class`
- Signature: `class ExperimentError`
- Lines: 54-55
- Docstring: No docstring.

### `read_csv`

- Kind: `function`
- Signature: `def read_csv(path)`
- Lines: 58-61
- Docstring: No docstring.

### `write_csv`

- Kind: `function`
- Signature: `def write_csv(path, columns, rows)`
- Lines: 64-69
- Docstring: No docstring.

### `file_sha256`

- Kind: `function`
- Signature: `def file_sha256(path)`
- Lines: 72-77
- Docstring: No docstring.

### `ensure_output_empty`

- Kind: `function`
- Signature: `def ensure_output_empty(output_dir)`
- Lines: 80-82
- Docstring: No docstring.

### `require_columns`

- Kind: `function`
- Signature: `def require_columns(columns, required, source_name)`
- Lines: 85-88
- Docstring: No docstring.

### `feature_names`

- Kind: `function`
- Signature: `def feature_names()`
- Lines: 91-122
- Docstring: No docstring.

### `extract_features`

- Kind: `function`
- Signature: `def extract_features(image)`
- Lines: 128-179
- Docstring: No docstring.

### `safe_crop_path`

- Kind: `function`
- Signature: `def safe_crop_path(crops_dir, crop_path_text)`
- Lines: 182-189
- Docstring: No docstring.

### `validate_marker_audit`

- Kind: `function`
- Signature: `def validate_marker_audit(marker_audit_dir)`
- Lines: 192-204
- Docstring: No docstring.

### `load_and_validate_dataset`

- Kind: `function`
- Signature: `def load_and_validate_dataset(crops_dir, lineage_manifest, marker_audit_dir)`
- Lines: 207-260
- Docstring: No docstring.

### `split_arrays`

- Kind: `function`
- Signature: `def split_arrays(dataset, split)`
- Lines: 263-265
- Docstring: No docstring.

### `y_to_label`

- Kind: `function`
- Signature: `def y_to_label(value)`
- Lines: 268-269
- Docstring: No docstring.

### `probability_for_positive`

- Kind: `function`
- Signature: `def probability_for_positive(model, X)`
- Lines: 272-275
- Docstring: No docstring.

### `f1_from_precision_recall`

- Kind: `function`
- Signature: `def f1_from_precision_recall(precision, recall)`
- Lines: 278-279
- Docstring: No docstring.

### `select_threshold`

- Kind: `function`
- Signature: `def select_threshold(y_validation, probabilities, candidates)`
- Lines: 282-320
- Docstring: No docstring.

### `evaluate_predictions`

- Kind: `function`
- Signature: `def evaluate_predictions(y_true, predictions, probabilities)`
- Lines: 323-340
- Docstring: No docstring.

### `json_ready`

- Kind: `function`
- Signature: `def json_ready(value)`
- Lines: 343-352
- Docstring: No docstring.

### `run_experiment`

- Kind: `function`
- Signature: `def run_experiment(crops_dir, lineage_manifest, marker_audit_dir, output_dir, seed, enforce_empty_output)`
- Lines: 355-500
- Docstring: No docstring.

### `format_metric`

- Kind: `function`
- Signature: `def format_metric(metrics)`
- Lines: 503-510
- Docstring: No docstring.

### `report_text`

- Kind: `function`
- Signature: `def report_text(training_summary, metrics, coefficient_rows)`
- Lines: 513-563
- Docstring: No docstring.

### `parse_args`

- Kind: `function`
- Signature: `def parse_args()`
- Lines: 566-573
- Docstring: No docstring.

### `main`

- Kind: `function`
- Signature: `def main()`
- Lines: 576-588
- Docstring: No docstring.
