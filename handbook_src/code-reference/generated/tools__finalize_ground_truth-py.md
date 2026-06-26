# `tools/finalize_ground_truth.py`

Generated content. Do not edit by hand.

- Purpose: Finalizes human-verified preliminary ground-truth labels.
- Source path: `tools/finalize_ground_truth.py`
- Source link: [tools/finalize_ground_truth.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/tools/finalize_ground_truth.py)
- Risk notes: Writes only documented outputs when run; review CLI help before execution.

## Top-Level Classes And Functions

### `FinalizationError`

- Kind: `class`
- Signature: `class FinalizationError`
- Lines: 69-70
- Docstring: No docstring.

### `parse_args`

- Kind: `function`
- Signature: `def parse_args()`
- Lines: 73-82
- Docstring: No docstring.

### `resolve_project_path`

- Kind: `function`
- Signature: `def resolve_project_path(value)`
- Lines: 85-92
- Docstring: No docstring.

### `resolve_output_dir`

- Kind: `function`
- Signature: `def resolve_output_dir(value)`
- Lines: 95-101
- Docstring: No docstring.

### `read_csv`

- Kind: `function`
- Signature: `def read_csv(path)`
- Lines: 104-107
- Docstring: No docstring.

### `write_csv`

- Kind: `function`
- Signature: `def write_csv(path, columns, rows)`
- Lines: 110-115
- Docstring: No docstring.

### `file_sha256`

- Kind: `function`
- Signature: `def file_sha256(path)`
- Lines: 118-123
- Docstring: No docstring.

### `clamp_preview_radius`

- Kind: `function`
- Signature: `def clamp_preview_radius(radius)`
- Lines: 126-127
- Docstring: No docstring.

### `parse_positive_float`

- Kind: `function`
- Signature: `def parse_positive_float(value, field_name, row_number)`
- Lines: 130-137
- Docstring: No docstring.

### `parse_float`

- Kind: `function`
- Signature: `def parse_float(value, field_name, row_number)`
- Lines: 140-144
- Docstring: No docstring.

### `quality_grade`

- Kind: `function`
- Signature: `def quality_grade(spot_count)`
- Lines: 147-154
- Docstring: No docstring.

### `ensure_columns`

- Kind: `function`
- Signature: `def ensure_columns(columns, required, label)`
- Lines: 157-160
- Docstring: No docstring.

### `alignment_note_for`

- Kind: `function`
- Signature: `def alignment_note_for(image_id, existing)`
- Lines: 163-173
- Docstring: No docstring.

### `validate_inputs`

- Kind: `function`
- Signature: `def validate_inputs(manifest_columns, manifest_rows, image_rows, generation_summary)`
- Lines: 176-231
- Docstring: No docstring.

### `build_final_rows`

- Kind: `function`
- Signature: `def build_final_rows(manifest_columns, manifest_rows, image_columns, image_rows, review_rows, run_id, finalized_at)`
- Lines: 234-316
- Docstring: No docstring.

### `finalization_report`

- Kind: `function`
- Signature: `def finalization_report(summary)`
- Lines: 319-382
- Docstring: No docstring.

### `summarize`

- Kind: `function`
- Signature: `def summarize(final_manifest_rows, final_image_rows, radius_audit_rows, input_hashes, output_hashes, created_at)`
- Lines: 385-422
- Docstring: No docstring.

### `finalize_ground_truth`

- Kind: `function`
- Signature: `def finalize_ground_truth(input_dir, output_dir, confirm_all_previews, run_id)`
- Lines: 425-504
- Docstring: No docstring.

### `main`

- Kind: `function`
- Signature: `def main()`
- Lines: 507-534
- Docstring: No docstring.
