# `tools/build_ground_truth_from_markers.py`

Generated content. Do not edit by hand.

- Purpose: Builds preliminary ground-truth labels from verified Blue Markers.
- Source path: `tools/build_ground_truth_from_markers.py`
- Source link: [tools/build_ground_truth_from_markers.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/tools/build_ground_truth_from_markers.py)
- Risk notes: Writes only documented outputs when run; review CLI help before execution.

## Top-Level Classes And Functions

### `ImagePair`

- Kind: `class`
- Signature: `class ImagePair`
- Lines: 78-81
- Docstring: No docstring.

### `PairDiscovery`

- Kind: `class`
- Signature: `class PairDiscovery`
- Lines: 85-89
- Docstring: No docstring.

### `MarkerLabel`

- Kind: `class`
- Signature: `class MarkerLabel`
- Lines: 93-100
- Docstring: No docstring.

### `parse_args`

- Kind: `function`
- Signature: `def parse_args()`
- Lines: 103-116
- Docstring: No docstring.

### `resolve_project_path`

- Kind: `function`
- Signature: `def resolve_project_path(value)`
- Lines: 119-126
- Docstring: No docstring.

### `resolve_output_dir`

- Kind: `function`
- Signature: `def resolve_output_dir(value)`
- Lines: 129-135
- Docstring: No docstring.

### `natural_image_key`

- Kind: `function`
- Signature: `def natural_image_key(path)`
- Lines: 138-140
- Docstring: No docstring.

### `discover_image_pairs`

- Kind: `function`
- Signature: `def discover_image_pairs(raw_dir)`
- Lines: 143-180
- Docstring: No docstring.

### `read_image`

- Kind: `function`
- Signature: `def read_image(path)`
- Lines: 183-184
- Docstring: No docstring.

### `quality_grade`

- Kind: `function`
- Signature: `def quality_grade(spot_count)`
- Lines: 187-194
- Docstring: No docstring.

### `clamp_radius`

- Kind: `function`
- Signature: `def clamp_radius(radius)`
- Lines: 197-198
- Docstring: No docstring.

### `alignment_note_for`

- Kind: `function`
- Signature: `def alignment_note_for(image_id)`
- Lines: 201-204
- Docstring: No docstring.

### `detect_marker_labels`

- Kind: `function`
- Signature: `def detect_marker_labels(marked_image, image_id)`
- Lines: 207-247
- Docstring: No docstring.

### `write_csv`

- Kind: `function`
- Signature: `def write_csv(path, columns, rows)`
- Lines: 250-255
- Docstring: No docstring.

### `preview_relative_path`

- Kind: `function`
- Signature: `def preview_relative_path(output_dir, preview_path)`
- Lines: 258-259
- Docstring: No docstring.

### `make_preview`

- Kind: `function`
- Signature: `def make_preview(original_image, labels, destination, image_id, quality_score, pass_fail_status)`
- Lines: 262-300
- Docstring: No docstring.

### `read_marker_analysis`

- Kind: `function`
- Signature: `def read_marker_analysis(marker_analysis_dir)`
- Lines: 303-307
- Docstring: No docstring.

### `review_priority`

- Kind: `function`
- Signature: `def review_priority(reasons, status)`
- Lines: 310-315
- Docstring: No docstring.

### `add_review_row`

- Kind: `function`
- Signature: `def add_review_row(rows, image_id, reasons, status, source_image, preview_path, notes)`
- Lines: 318-340
- Docstring: No docstring.

### `ground_truth_report`

- Kind: `function`
- Signature: `def ground_truth_report(summary, output_dir)`
- Lines: 343-399
- Docstring: No docstring.

### `build_ground_truth`

- Kind: `function`
- Signature: `def build_ground_truth(raw_dir, output_dir, marker_analysis_dir, review_image_ids, dry_run, no_previews)`
- Lines: 402-575
- Docstring: No docstring.

### `main`

- Kind: `function`
- Signature: `def main()`
- Lines: 578-598
- Docstring: No docstring.
