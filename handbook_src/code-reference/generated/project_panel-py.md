# `project_panel.py`

Generated content. Do not edit by hand.

- Purpose: Serves the local workflow panel and safely launches pipeline subprocesses.
- Source path: `project_panel.py`
- Source link: [project_panel.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/project_panel.py)
- Risk notes: Writes only documented outputs when run; review CLI help before execution.

## Top-Level Classes And Functions

### `timestamp`

- Kind: `function`
- Signature: `def timestamp()`
- Lines: 613-614
- Docstring: No docstring.

### `update_state`

- Kind: `function`
- Signature: `def update_state(**changes)`
- Lines: 617-619
- Docstring: No docstring.

### `append_log`

- Kind: `function`
- Signature: `def append_log(line)`
- Lines: 622-627
- Docstring: No docstring.

### `set_output`

- Kind: `function`
- Signature: `def set_output(key, value)`
- Lines: 630-633
- Docstring: No docstring.

### `snapshot_state`

- Kind: `function`
- Signature: `def snapshot_state()`
- Lines: 636-646
- Docstring: No docstring.

### `merged_config`

- Kind: `function`
- Signature: `def merged_config(config)`
- Lines: 649-656
- Docstring: No docstring.

### `ensure_bool`

- Kind: `function`
- Signature: `def ensure_bool(value, field_name)`
- Lines: 659-662
- Docstring: No docstring.

### `ensure_number`

- Kind: `function`
- Signature: `def ensure_number(value, field_name, minimum, maximum, integer)`
- Lines: 665-680
- Docstring: No docstring.

### `ensure_choice`

- Kind: `function`
- Signature: `def ensure_choice(value, field_name, choices)`
- Lines: 683-686
- Docstring: No docstring.

### `ensure_project_path`

- Kind: `function`
- Signature: `def ensure_project_path(value, field_name, allow_empty)`
- Lines: 689-707
- Docstring: No docstring.

### `validate_config`

- Kind: `function`
- Signature: `def validate_config(config)`
- Lines: 710-822
- Docstring: No docstring.

### `parse_run_config`

- Kind: `function`
- Signature: `def parse_run_config(payload, content_length)`
- Lines: 825-833
- Docstring: No docstring.

### `maybe_add_flag`

- Kind: `function`
- Signature: `def maybe_add_flag(command, condition, flag)`
- Lines: 836-838
- Docstring: No docstring.

### `crop_command`

- Kind: `function`
- Signature: `def crop_command(config)`
- Lines: 841-875
- Docstring: No docstring.

### `backtest_command`

- Kind: `function`
- Signature: `def backtest_command(config)`
- Lines: 878-894
- Docstring: No docstring.

### `anomaly_command`

- Kind: `function`
- Signature: `def anomaly_command(config)`
- Lines: 897-943
- Docstring: No docstring.

### `command_for_log`

- Kind: `function`
- Signature: `def command_for_log(command)`
- Lines: 946-947
- Docstring: No docstring.

### `parse_output_line`

- Kind: `function`
- Signature: `def parse_output_line(line)`
- Lines: 950-958
- Docstring: No docstring.

### `run_command`

- Kind: `function`
- Signature: `def run_command(name, command)`
- Lines: 961-983
- Docstring: No docstring.

### `run_pipeline`

- Kind: `function`
- Signature: `def run_pipeline(config)`
- Lines: 986-1020
- Docstring: No docstring.

### `PanelHandler`

- Kind: `class`
- Signature: `class PanelHandler`
- Lines: 1023-1080
- Docstring: No docstring.

### `parse_args`

- Kind: `function`
- Signature: `def parse_args()`
- Lines: 1083-1088
- Docstring: No docstring.

### `main`

- Kind: `function`
- Signature: `def main()`
- Lines: 1091-1098
- Docstring: No docstring.
