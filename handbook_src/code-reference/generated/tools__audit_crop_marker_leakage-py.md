# `tools/audit_crop_marker_leakage.py`

Generated content. Do not edit by hand.

- Purpose: Audits crop images for marker-like blue annotation leakage.
- Source path: `tools/audit_crop_marker_leakage.py`
- Source link: [tools/audit_crop_marker_leakage.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/tools/audit_crop_marker_leakage.py)
- Risk notes: Writes only documented outputs when run; review CLI help before execution.

## Top-Level Classes And Functions

### `AuditError`

- Kind: `class`
- Signature: `class AuditError`
- Lines: 83-84
- Docstring: No docstring.

### `read_csv`

- Kind: `function`
- Signature: `def read_csv(path)`
- Lines: 87-90
- Docstring: No docstring.

### `write_csv`

- Kind: `function`
- Signature: `def write_csv(path, columns, rows)`
- Lines: 93-98
- Docstring: No docstring.

### `file_sha256`

- Kind: `function`
- Signature: `def file_sha256(path)`
- Lines: 101-106
- Docstring: No docstring.

### `ensure_output_empty`

- Kind: `function`
- Signature: `def ensure_output_empty(output_dir)`
- Lines: 109-111
- Docstring: No docstring.

### `require_columns`

- Kind: `function`
- Signature: `def require_columns(columns, required, source_name)`
- Lines: 114-117
- Docstring: No docstring.

### `safe_crop_path`

- Kind: `function`
- Signature: `def safe_crop_path(crops_dir, crop_path_text)`
- Lines: 120-129
- Docstring: No docstring.

### `detect_blue_mask`

- Kind: `function`
- Signature: `def detect_blue_mask(image)`
- Lines: 132-143
- Docstring: No docstring.

### `analyze_blue_components`

- Kind: `function`
- Signature: `def analyze_blue_components(image)`
- Lines: 146-186
- Docstring: No docstring.

### `preflight_and_analyze`

- Kind: `function`
- Signature: `def preflight_and_analyze(crops_dir, lineage_manifest)`
- Lines: 189-242
- Docstring: No docstring.

### `build_summary_rows`

- Kind: `function`
- Signature: `def build_summary_rows(rows)`
- Lines: 245-269
- Docstring: No docstring.

### `draw_review_sample`

- Kind: `function`
- Signature: `def draw_review_sample(row, output_path)`
- Lines: 272-299
- Docstring: No docstring.

### `build_candidates`

- Kind: `function`
- Signature: `def build_candidates(rows, review_dir, sample_limit_per_group)`
- Lines: 302-336
- Docstring: No docstring.

### `report_text`

- Kind: `function`
- Signature: `def report_text(summary, summary_rows)`
- Lines: 339-409
- Docstring: No docstring.

### `create_outputs`

- Kind: `function`
- Signature: `def create_outputs(output_dir, lineage_columns, rows, input_hashes, sample_limit_per_group)`
- Lines: 412-473
- Docstring: No docstring.

### `audit_crop_marker_leakage`

- Kind: `function`
- Signature: `def audit_crop_marker_leakage(crops_dir, lineage_manifest, output_dir, sample_limit_per_group, enforce_empty_output)`
- Lines: 476-486
- Docstring: No docstring.

### `parse_args`

- Kind: `function`
- Signature: `def parse_args()`
- Lines: 489-495
- Docstring: No docstring.

### `main`

- Kind: `function`
- Signature: `def main()`
- Lines: 498-525
- Docstring: No docstring.
