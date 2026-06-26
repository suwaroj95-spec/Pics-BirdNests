# `anomaly_detection.py`

Generated content. Do not edit by hand.

- Purpose: Ranks suspicious selected crops using feature-based anomaly scoring.
- Source path: `anomaly_detection.py`
- Source link: [anomaly_detection.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/anomaly_detection.py)
- Risk notes: Writes only documented outputs when run; review CLI help before execution.

## Top-Level Classes And Functions

### `AnomalyConfig`

- Kind: `class`
- Signature: `class AnomalyConfig`
- Lines: 40-56
- Docstring: No docstring.

### `IsolationNode`

- Kind: `class`
- Signature: `class IsolationNode`
- Lines: 60-66
- Docstring: No docstring.

### `FeatureMatrix`

- Kind: `class`
- Signature: `class FeatureMatrix`
- Lines: 70-75
- Docstring: No docstring.

### `parse_args`

- Kind: `function`
- Signature: `def parse_args()`
- Lines: 78-105
- Docstring: No docstring.

### `config_from_args`

- Kind: `function`
- Signature: `def config_from_args(args)`
- Lines: 108-135
- Docstring: No docstring.

### `latest_backtest_run`

- Kind: `function`
- Signature: `def latest_backtest_run(backtest_root)`
- Lines: 138-149
- Docstring: No docstring.

### `resolve_backtest_run`

- Kind: `function`
- Signature: `def resolve_backtest_run(config)`
- Lines: 152-160
- Docstring: No docstring.

### `manifest_paths_from_run`

- Kind: `function`
- Signature: `def manifest_paths_from_run(run_dir)`
- Lines: 163-182
- Docstring: No docstring.

### `resolve_manifest_path`

- Kind: `function`
- Signature: `def resolve_manifest_path(manifest_text, run_dir)`
- Lines: 185-202
- Docstring: No docstring.

### `read_manifest`

- Kind: `function`
- Signature: `def read_manifest(system_key, manifest_path, crops_dir)`
- Lines: 205-214
- Docstring: No docstring.

### `resolve_image_path`

- Kind: `function`
- Signature: `def resolve_image_path(row, system_dir, crops_dir)`
- Lines: 217-227
- Docstring: No docstring.

### `safe_float`

- Kind: `function`
- Signature: `def safe_float(value)`
- Lines: 230-239
- Docstring: No docstring.

### `numeric_feature_columns`

- Kind: `function`
- Signature: `def numeric_feature_columns(rows)`
- Lines: 242-258
- Docstring: No docstring.

### `build_feature_matrix`

- Kind: `function`
- Signature: `def build_feature_matrix(rows)`
- Lines: 261-285
- Docstring: No docstring.

### `percentile_normalize`

- Kind: `function`
- Signature: `def percentile_normalize(scores)`
- Lines: 288-299
- Docstring: No docstring.

### `average_path_length`

- Kind: `function`
- Signature: `def average_path_length(sample_count)`
- Lines: 302-310
- Docstring: No docstring.

### `build_isolation_tree`

- Kind: `function`
- Signature: `def build_isolation_tree(x_train, rng, depth, max_depth)`
- Lines: 313-340
- Docstring: No docstring.

### `path_length`

- Kind: `function`
- Signature: `def path_length(row, node)`
- Lines: 343-353
- Docstring: No docstring.

### `isolation_forest_scores`

- Kind: `function`
- Signature: `def isolation_forest_scores(x, tree_count, subsample_size, seed)`
- Lines: 356-384
- Docstring: No docstring.

### `lof_scores`

- Kind: `function`
- Signature: `def lof_scores(x, neighbor_k)`
- Lines: 387-407
- Docstring: No docstring.

### `pca_reconstruction_scores`

- Kind: `function`
- Signature: `def pca_reconstruction_scores(x, component_count)`
- Lines: 410-426
- Docstring: No docstring.

### `top_fraction_flags`

- Kind: `function`
- Signature: `def top_fraction_flags(scores, contamination)`
- Lines: 429-436
- Docstring: No docstring.

### `rank_descending`

- Kind: `function`
- Signature: `def rank_descending(scores)`
- Lines: 439-443
- Docstring: No docstring.

### `detect_group_anomalies`

- Kind: `function`
- Signature: `def detect_group_anomalies(rows, config, group_seed)`
- Lines: 446-538
- Docstring: No docstring.

### `collect_fieldnames`

- Kind: `function`
- Signature: `def collect_fieldnames(rows)`
- Lines: 541-564
- Docstring: No docstring.

### `write_csv`

- Kind: `function`
- Signature: `def write_csv(path, rows, fieldnames)`
- Lines: 567-574
- Docstring: No docstring.

### `write_summary_text`

- Kind: `function`
- Signature: `def write_summary_text(path, summary)`
- Lines: 577-604
- Docstring: No docstring.

### `short_text`

- Kind: `function`
- Signature: `def short_text(text, limit)`
- Lines: 607-610
- Docstring: No docstring.

### `create_contact_sheet`

- Kind: `function`
- Signature: `def create_contact_sheet(rows, output_path, top_n)`
- Lines: 613-669
- Docstring: No docstring.

### `copy_anomaly_files`

- Kind: `function`
- Signature: `def copy_anomaly_files(rows, output_dir)`
- Lines: 672-685
- Docstring: No docstring.

### `run_anomaly_detection`

- Kind: `function`
- Signature: `def run_anomaly_detection(config)`
- Lines: 688-777
- Docstring: No docstring.

### `main`

- Kind: `function`
- Signature: `def main()`
- Lines: 780-788
- Docstring: No docstring.
