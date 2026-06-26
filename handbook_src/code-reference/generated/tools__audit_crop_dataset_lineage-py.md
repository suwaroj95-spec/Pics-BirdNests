# `tools/audit_crop_dataset_lineage.py`

Generated content. Do not edit by hand.

- Purpose: Audits crop lineage against source-level split and final ground truth.
- Source path: `tools/audit_crop_dataset_lineage.py`
- Source link: [tools/audit_crop_dataset_lineage.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/tools/audit_crop_dataset_lineage.py)
- Risk notes: Writes only documented outputs when run; review CLI help before execution.

## Top-Level Classes And Functions

### `LineageAuditError`

- Kind: `class`
- Signature: `class LineageAuditError`
- Lines: 54-55
- Docstring: No docstring.

### `parse_args`

- Kind: `function`
- Signature: `def parse_args()`
- Lines: 58-64
- Docstring: No docstring.

### `resolve_project_path`

- Kind: `function`
- Signature: `def resolve_project_path(value)`
- Lines: 67-74
- Docstring: No docstring.

### `resolve_output_dir`

- Kind: `function`
- Signature: `def resolve_output_dir(value)`
- Lines: 77-83
- Docstring: No docstring.

### `ensure_output_empty`

- Kind: `function`
- Signature: `def ensure_output_empty(output_dir)`
- Lines: 86-88
- Docstring: No docstring.

### `read_csv`

- Kind: `function`
- Signature: `def read_csv(path)`
- Lines: 91-94
- Docstring: No docstring.

### `write_csv`

- Kind: `function`
- Signature: `def write_csv(path, columns, rows)`
- Lines: 97-102
- Docstring: No docstring.

### `file_sha256`

- Kind: `function`
- Signature: `def file_sha256(path)`
- Lines: 105-110
- Docstring: No docstring.

### `normalize_image_id`

- Kind: `function`
- Signature: `def normalize_image_id(value)`
- Lines: 113-119
- Docstring: No docstring.

### `required_columns`

- Kind: `function`
- Signature: `def required_columns(columns, required, label)`
- Lines: 122-125
- Docstring: No docstring.

### `load_inputs`

- Kind: `function`
- Signature: `def load_inputs(crops_dir, split_dir, finalization_dir)`
- Lines: 128-164
- Docstring: No docstring.

### `final_spot_lookup`

- Kind: `function`
- Signature: `def final_spot_lookup(final_rows)`
- Lines: 167-168
- Docstring: No docstring.

### `candidate_spot_id`

- Kind: `function`
- Signature: `def candidate_spot_id(image_id, dirty_spot_id)`
- Lines: 171-177
- Docstring: No docstring.

### `build_lineage`

- Kind: `function`
- Signature: `def build_lineage(crop_columns, crop_rows, split_rows, final_rows, final_image_rows, final_split_rows)`
- Lines: 180-314
- Docstring: No docstring.

### `decide_reuse`

- Kind: `function`
- Signature: `def decide_reuse(lineage_rows, leakage_rows, dirty_trace_rows, duplicate_crop_paths)`
- Lines: 317-331
- Docstring: No docstring.

### `report_text`

- Kind: `function`
- Signature: `def report_text(crop_columns, summary, reuse_decision)`
- Lines: 334-404
- Docstring: No docstring.

### `create_outputs`

- Kind: `function`
- Signature: `def create_outputs(output_dir, crop_columns, lineage_rows, split_summary_rows, leakage_rows, dirty_trace_rows, input_hashes, stats)`
- Lines: 407-463
- Docstring: No docstring.

### `audit_crop_lineage`

- Kind: `function`
- Signature: `def audit_crop_lineage(crops_dir, split_dir, finalization_dir, output_dir, enforce_empty_output)`
- Lines: 466-487
- Docstring: No docstring.

### `main`

- Kind: `function`
- Signature: `def main()`
- Lines: 490-506
- Docstring: No docstring.
