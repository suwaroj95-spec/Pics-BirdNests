# `select_birdnest_samples.py`

Generated content. Do not edit by hand.

- Purpose: Backtests crop-selection systems and writes selected manifests.
- Source path: `select_birdnest_samples.py`
- Source link: [select_birdnest_samples.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/select_birdnest_samples.py)
- Risk notes: Writes only documented outputs when run; review CLI help before execution.

## Top-Level Classes And Functions

### `Candidate`

- Kind: `class`
- Signature: `class Candidate`
- Lines: 31-42
- Docstring: No docstring.

### `parse_args`

- Kind: `function`
- Signature: `def parse_args()`
- Lines: 73-100
- Docstring: No docstring.

### `safe_float`

- Kind: `function`
- Signature: `def safe_float(value, default)`
- Lines: 103-109
- Docstring: No docstring.

### `read_image`

- Kind: `function`
- Signature: `def read_image(path)`
- Lines: 112-113
- Docstring: No docstring.

### `detect_blue_annotation`

- Kind: `function`
- Signature: `def detect_blue_annotation(image)`
- Lines: 116-125
- Docstring: No docstring.

### `normalized_hist_entropy`

- Kind: `function`
- Signature: `def normalized_hist_entropy(gray)`
- Lines: 128-136
- Docstring: No docstring.

### `local_std_mean`

- Kind: `function`
- Signature: `def local_std_mean(gray)`
- Lines: 139-141
- Docstring: No docstring.

### `local_std_image`

- Kind: `function`
- Signature: `def local_std_image(gray, kernel_size)`
- Lines: 144-149
- Docstring: No docstring.

### `foreground_mask`

- Kind: `function`
- Signature: `def foreground_mask(image, gray)`
- Lines: 152-170
- Docstring: No docstring.

### `material_texture_mask`

- Kind: `function`
- Signature: `def material_texture_mask(image, gray)`
- Lines: 173-193
- Docstring: No docstring.

### `largest_flat_background_ratio`

- Kind: `function`
- Signature: `def largest_flat_background_ratio(image, gray)`
- Lines: 196-208
- Docstring: No docstring.

### `connected_component_ratio`

- Kind: `function`
- Signature: `def connected_component_ratio(mask)`
- Lines: 211-218
- Docstring: No docstring.

### `border_ratio`

- Kind: `function`
- Signature: `def border_ratio(mask, border)`
- Lines: 221-227
- Docstring: No docstring.

### `center_ratio`

- Kind: `function`
- Signature: `def center_ratio(mask)`
- Lines: 230-235
- Docstring: No docstring.

### `high_frequency_energy`

- Kind: `function`
- Signature: `def high_frequency_energy(gray)`
- Lines: 238-251
- Docstring: No docstring.

### `mask_metrics`

- Kind: `function`
- Signature: `def mask_metrics(mask_path)`
- Lines: 254-286
- Docstring: No docstring.

### `analyze_image`

- Kind: `function`
- Signature: `def analyze_image(path, mask_path)`
- Lines: 289-349
- Docstring: No docstring.

### `load_candidates`

- Kind: `function`
- Signature: `def load_candidates(crops_dir)`
- Lines: 352-386
- Docstring: No docstring.

### `percentile_normalize`

- Kind: `function`
- Signature: `def percentile_normalize(values)`
- Lines: 389-398
- Docstring: No docstring.

### `add_normalized_scores`

- Kind: `function`
- Signature: `def add_normalized_scores(candidates)`
- Lines: 401-433
- Docstring: No docstring.

### `dirty_mask_bonus`

- Kind: `function`
- Signature: `def dirty_mask_bonus(candidate)`
- Lines: 436-443
- Docstring: No docstring.

### `compute_system_scores`

- Kind: `function`
- Signature: `def compute_system_scores(candidates)`
- Lines: 446-503
- Docstring: No docstring.

### `sorted_candidates`

- Kind: `function`
- Signature: `def sorted_candidates(candidates, system_key, label)`
- Lines: 506-523
- Docstring: No docstring.

### `select_with_source_diversity`

- Kind: `function`
- Signature: `def select_with_source_diversity(candidates, system_key, label, target, use_diversity)`
- Lines: 526-566
- Docstring: No docstring.

### `ensure_label_dirs`

- Kind: `function`
- Signature: `def ensure_label_dirs(system_dir)`
- Lines: 569-574
- Docstring: No docstring.

### `copy_selected`

- Kind: `function`
- Signature: `def copy_selected(selected, system_dir)`
- Lines: 577-587
- Docstring: No docstring.

### `numeric_summary`

- Kind: `function`
- Signature: `def numeric_summary(selected, system_key)`
- Lines: 590-612
- Docstring: No docstring.

### `mean`

- Kind: `function`
- Signature: `def mean(values)`
- Lines: 615-618
- Docstring: No docstring.

### `write_manifest`

- Kind: `function`
- Signature: `def write_manifest(path, selected, system_key)`
- Lines: 621-661
- Docstring: No docstring.

### `write_all_scores`

- Kind: `function`
- Signature: `def write_all_scores(path, candidates)`
- Lines: 664-707
- Docstring: No docstring.

### `source_distribution`

- Kind: `function`
- Signature: `def source_distribution(selected)`
- Lines: 710-714
- Docstring: No docstring.

### `write_summary_text`

- Kind: `function`
- Signature: `def write_summary_text(path, summary)`
- Lines: 717-743
- Docstring: No docstring.

### `run_system`

- Kind: `function`
- Signature: `def run_system(system, candidates, run_dir, clean_target, dirty_pair_target, copy_files, use_diversity)`
- Lines: 746-801
- Docstring: No docstring.

### `compare_systems`

- Kind: `function`
- Signature: `def compare_systems(run_dir, summaries, candidates)`
- Lines: 804-864
- Docstring: No docstring.

### `main`

- Kind: `function`
- Signature: `def main()`
- Lines: 867-942
- Docstring: No docstring.
