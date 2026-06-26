# `tools/analyze_blue_marker_distribution.py`

Generated content. Do not edit by hand.

- Purpose: Analyzes Blue Marker distribution and source/marked alignment.
- Source path: `tools/analyze_blue_marker_distribution.py`
- Source link: [tools/analyze_blue_marker_distribution.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/tools/analyze_blue_marker_distribution.py)
- Risk notes: Writes only documented outputs when run; review CLI help before execution.

## Top-Level Classes And Functions

### `ImagePair`

- Kind: `class`
- Signature: `class ImagePair`
- Lines: 84-87
- Docstring: No docstring.

### `PairDiscovery`

- Kind: `class`
- Signature: `class PairDiscovery`
- Lines: 91-96
- Docstring: No docstring.

### `MarkerInstance`

- Kind: `class`
- Signature: `class MarkerInstance`
- Lines: 100-113
- Docstring: No docstring.

### `parse_args`

- Kind: `function`
- Signature: `def parse_args()`
- Lines: 116-125
- Docstring: No docstring.

### `resolve_project_path`

- Kind: `function`
- Signature: `def resolve_project_path(value)`
- Lines: 128-138
- Docstring: No docstring.

### `resolve_output_dir`

- Kind: `function`
- Signature: `def resolve_output_dir(value)`
- Lines: 141-147
- Docstring: No docstring.

### `natural_image_key`

- Kind: `function`
- Signature: `def natural_image_key(path)`
- Lines: 150-152
- Docstring: No docstring.

### `discover_image_pairs`

- Kind: `function`
- Signature: `def discover_image_pairs(raw_dir)`
- Lines: 155-223
- Docstring: No docstring.

### `read_image`

- Kind: `function`
- Signature: `def read_image(path)`
- Lines: 226-227
- Docstring: No docstring.

### `alignment_status`

- Kind: `function`
- Signature: `def alignment_status(same_dimensions, x_offset, y_offset, confidence)`
- Lines: 230-243
- Docstring: No docstring.

### `estimate_alignment`

- Kind: `function`
- Signature: `def estimate_alignment(original, marked)`
- Lines: 246-291
- Docstring: No docstring.

### `quality_grade`

- Kind: `function`
- Signature: `def quality_grade(spot_count)`
- Lines: 294-301
- Docstring: No docstring.

### `detect_marker_instances`

- Kind: `function`
- Signature: `def detect_marker_instances(marked_image, image_id, source_marked_image)`
- Lines: 304-351
- Docstring: No docstring.

### `with_nearest_neighbor_distances`

- Kind: `function`
- Signature: `def with_nearest_neighbor_distances(instances)`
- Lines: 354-380
- Docstring: No docstring.

### `percentile`

- Kind: `function`
- Signature: `def percentile(values, pct)`
- Lines: 383-386
- Docstring: No docstring.

### `distribution`

- Kind: `function`
- Signature: `def distribution(values)`
- Lines: 389-400
- Docstring: No docstring.

### `write_csv`

- Kind: `function`
- Signature: `def write_csv(path, columns, rows)`
- Lines: 403-408
- Docstring: No docstring.

### `marker_to_row`

- Kind: `function`
- Signature: `def marker_to_row(marker)`
- Lines: 411-428
- Docstring: No docstring.

### `median_or_blank`

- Kind: `function`
- Signature: `def median_or_blank(values)`
- Lines: 431-434
- Docstring: No docstring.

### `min_or_blank`

- Kind: `function`
- Signature: `def min_or_blank(values)`
- Lines: 437-438
- Docstring: No docstring.

### `max_or_blank`

- Kind: `function`
- Signature: `def max_or_blank(values)`
- Lines: 441-442
- Docstring: No docstring.

### `make_preview`

- Kind: `function`
- Signature: `def make_preview(marked_image, markers, destination, image_id, spot_count)`
- Lines: 445-477
- Docstring: No docstring.

### `summarize_outliers`

- Kind: `function`
- Signature: `def summarize_outliers(image_rows, marker_rows)`
- Lines: 480-517
- Docstring: No docstring.

### `policy_proposal_text`

- Kind: `function`
- Signature: `def policy_proposal_text(summary)`
- Lines: 520-583
- Docstring: No docstring.

### `analyze`

- Kind: `function`
- Signature: `def analyze(raw_dir, output_dir)`
- Lines: 586-710
- Docstring: No docstring.

### `main`

- Kind: `function`
- Signature: `def main()`
- Lines: 713-721
- Docstring: No docstring.
