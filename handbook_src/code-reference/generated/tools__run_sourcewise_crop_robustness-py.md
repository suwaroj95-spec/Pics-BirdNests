# `tools/run_sourcewise_crop_robustness.py`

Generated content. Do not edit by hand.

- Purpose: Runs source-wise crop robustness evaluation.
- Source path: `tools/run_sourcewise_crop_robustness.py`
- Source link: [tools/run_sourcewise_crop_robustness.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/tools/run_sourcewise_crop_robustness.py)
- Risk notes: Writes experiment outputs and may create model/report artifacts.

## Top-Level Classes And Functions

### `RobustnessError`

- Kind: `class`
- Signature: `class RobustnessError`
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

### `numeric_source_sort`

- Kind: `function`
- Signature: `def numeric_source_sort(source_id)`
- Lines: 85-86
- Docstring: No docstring.

### `safe_crop_path`

- Kind: `function`
- Signature: `def safe_crop_path(crops_dir, crop_path_text)`
- Lines: 89-96
- Docstring: No docstring.

### `validate_marker_audit`

- Kind: `function`
- Signature: `def validate_marker_audit(marker_audit_dir)`
- Lines: 99-109
- Docstring: No docstring.

### `load_dataset`

- Kind: `function`
- Signature: `def load_dataset(crops_dir, lineage_manifest, marker_audit_dir)`
- Lines: 112-172
- Docstring: No docstring.

### `rows_for_sources`

- Kind: `function`
- Signature: `def rows_for_sources(dataset, source_ids)`
- Lines: 175-177
- Docstring: No docstring.

### `positive_probabilities`

- Kind: `function`
- Signature: `def positive_probabilities(model, X)`
- Lines: 180-182
- Docstring: No docstring.

### `y_to_label`

- Kind: `function`
- Signature: `def y_to_label(value)`
- Lines: 185-186
- Docstring: No docstring.

### `evaluate`

- Kind: `function`
- Signature: `def evaluate(y_true, predictions, probabilities)`
- Lines: 189-205
- Docstring: No docstring.

### `distribution`

- Kind: `function`
- Signature: `def distribution(values)`
- Lines: 208-219
- Docstring: No docstring.

### `decision_from`

- Kind: `function`
- Signature: `def decision_from(metrics_rows)`
- Lines: 222-231
- Docstring: No docstring.

### `run_robustness`

- Kind: `function`
- Signature: `def run_robustness(crops_dir, lineage_manifest, marker_audit_dir, output_dir, seed, enforce_empty_output)`
- Lines: 234-384
- Docstring: No docstring.

### `report_text`

- Kind: `function`
- Signature: `def report_text(summary, metrics_rows)`
- Lines: 387-441
- Docstring: No docstring.

### `parse_args`

- Kind: `function`
- Signature: `def parse_args()`
- Lines: 444-451
- Docstring: No docstring.

### `main`

- Kind: `function`
- Signature: `def main()`
- Lines: 454-463
- Docstring: No docstring.
