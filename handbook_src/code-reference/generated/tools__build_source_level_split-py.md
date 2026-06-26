# `tools/build_source_level_split.py`

Generated content. Do not edit by hand.

- Purpose: Builds deterministic train/validation/test split manifests by source image.
- Source path: `tools/build_source_level_split.py`
- Source link: [tools/build_source_level_split.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/tools/build_source_level_split.py)
- Risk notes: Writes only documented outputs when run; review CLI help before execution.

## Top-Level Classes And Functions

### `SplitError`

- Kind: `class`
- Signature: `class SplitError`
- Lines: 71-72
- Docstring: No docstring.

### `SourceRecord`

- Kind: `class`
- Signature: `class SourceRecord`
- Lines: 76-83
- Docstring: No docstring.

### `parse_args`

- Kind: `function`
- Signature: `def parse_args()`
- Lines: 86-93
- Docstring: No docstring.

### `resolve_project_path`

- Kind: `function`
- Signature: `def resolve_project_path(value)`
- Lines: 96-103
- Docstring: No docstring.

### `resolve_output_dir`

- Kind: `function`
- Signature: `def resolve_output_dir(value)`
- Lines: 106-112
- Docstring: No docstring.

### `ensure_output_empty`

- Kind: `function`
- Signature: `def ensure_output_empty(output_dir)`
- Lines: 115-117
- Docstring: No docstring.

### `read_csv`

- Kind: `function`
- Signature: `def read_csv(path)`
- Lines: 120-123
- Docstring: No docstring.

### `write_csv`

- Kind: `function`
- Signature: `def write_csv(path, columns, rows)`
- Lines: 126-131
- Docstring: No docstring.

### `file_sha256`

- Kind: `function`
- Signature: `def file_sha256(path)`
- Lines: 134-139
- Docstring: No docstring.

### `ensure_columns`

- Kind: `function`
- Signature: `def ensure_columns(columns, required, label)`
- Lines: 142-145
- Docstring: No docstring.

### `image_sort_key`

- Kind: `function`
- Signature: `def image_sort_key(image_id)`
- Lines: 148-149
- Docstring: No docstring.

### `load_inputs`

- Kind: `function`
- Signature: `def load_inputs(finalization_dir)`
- Lines: 152-170
- Docstring: No docstring.

### `validate_final_ground_truth`

- Kind: `function`
- Signature: `def validate_final_ground_truth(manifest_columns, manifest_rows, image_rows, finalization_summary)`
- Lines: 173-239
- Docstring: No docstring.

### `build_assignments`

- Kind: `function`
- Signature: `def build_assignments(records, seed)`
- Lines: 242-265
- Docstring: No docstring.

### `split_report`

- Kind: `function`
- Signature: `def split_report(summary, assignments)`
- Lines: 268-327
- Docstring: No docstring.

### `create_outputs`

- Kind: `function`
- Signature: `def create_outputs(output_dir, manifest_columns, manifest_rows, records, assignments, seed, input_hashes)`
- Lines: 330-439
- Docstring: No docstring.

### `build_source_level_split`

- Kind: `function`
- Signature: `def build_source_level_split(finalization_dir, output_dir, seed, enforce_empty_output)`
- Lines: 442-448
- Docstring: No docstring.

### `main`

- Kind: `function`
- Signature: `def main()`
- Lines: 451-468
- Docstring: No docstring.
