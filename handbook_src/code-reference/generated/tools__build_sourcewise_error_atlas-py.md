# `tools/build_sourcewise_error_atlas.py`

Generated content. Do not edit by hand.

- Purpose: Builds source-wise error profiles, rankings, and review examples.
- Source path: `tools/build_sourcewise_error_atlas.py`
- Source link: [tools/build_sourcewise_error_atlas.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/tools/build_sourcewise_error_atlas.py)
- Risk notes: Writes only documented outputs when run; review CLI help before execution.

## Top-Level Classes And Functions

### `AtlasError`

- Kind: `class`
- Signature: `class AtlasError`
- Lines: 38-39
- Docstring: No docstring.

### `read_csv`

- Kind: `function`
- Signature: `def read_csv(path)`
- Lines: 42-45
- Docstring: No docstring.

### `write_csv`

- Kind: `function`
- Signature: `def write_csv(path, columns, rows)`
- Lines: 48-53
- Docstring: No docstring.

### `file_sha256`

- Kind: `function`
- Signature: `def file_sha256(path)`
- Lines: 56-61
- Docstring: No docstring.

### `ensure_output_empty`

- Kind: `function`
- Signature: `def ensure_output_empty(output_dir)`
- Lines: 64-66
- Docstring: No docstring.

### `numeric_sort`

- Kind: `function`
- Signature: `def numeric_sort(value)`
- Lines: 69-70
- Docstring: No docstring.

### `error_type`

- Kind: `function`
- Signature: `def error_type(true_label, prediction)`
- Lines: 73-82
- Docstring: No docstring.

### `threshold_margin`

- Kind: `function`
- Signature: `def threshold_margin(kind, probability, threshold)`
- Lines: 85-90
- Docstring: No docstring.

### `descriptive_stats`

- Kind: `function`
- Signature: `def descriptive_stats(image)`
- Lines: 93-109
- Docstring: No docstring.

### `safe_crop_path`

- Kind: `function`
- Signature: `def safe_crop_path(crops_dir, crop_path_text)`
- Lines: 112-119
- Docstring: No docstring.

### `load_and_validate`

- Kind: `function`
- Signature: `def load_and_validate(crops_dir, robustness_dir, lineage_manifest, marker_audit_dir)`
- Lines: 122-216
- Docstring: No docstring.

### `rate`

- Kind: `function`
- Signature: `def rate(numerator, denominator)`
- Lines: 219-220
- Docstring: No docstring.

### `build_profiles`

- Kind: `function`
- Signature: `def build_profiles(manifest_rows, metric_by_source)`
- Lines: 223-266
- Docstring: No docstring.

### `build_group_stats`

- Kind: `function`
- Signature: `def build_group_stats(manifest_rows)`
- Lines: 269-282
- Docstring: No docstring.

### `contact_sheet`

- Kind: `function`
- Signature: `def contact_sheet(samples, output_path, title)`
- Lines: 285-318
- Docstring: No docstring.

### `select_contact_examples`

- Kind: `function`
- Signature: `def select_contact_examples(manifest_rows, selected_sources, output_dir, limit)`
- Lines: 321-353
- Docstring: No docstring.

### `diagnosis`

- Kind: `function`
- Signature: `def diagnosis(profiles)`
- Lines: 356-366
- Docstring: No docstring.

### `report_text`

- Kind: `function`
- Signature: `def report_text(summary, profiles, group_stats)`
- Lines: 369-435
- Docstring: No docstring.

### `build_atlas`

- Kind: `function`
- Signature: `def build_atlas(crops_dir, robustness_dir, lineage_manifest, marker_audit_dir, output_dir, max_samples_per_error_group, enforce_empty_output)`
- Lines: 450-515
- Docstring: No docstring.

### `parse_args`

- Kind: `function`
- Signature: `def parse_args()`
- Lines: 518-526
- Docstring: No docstring.

### `main`

- Kind: `function`
- Signature: `def main()`
- Lines: 529-538
- Docstring: No docstring.
