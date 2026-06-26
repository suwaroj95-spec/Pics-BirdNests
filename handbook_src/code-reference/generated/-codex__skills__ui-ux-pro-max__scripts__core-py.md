# `.codex/skills/ui-ux-pro-max/scripts/core.py`

Generated content. Do not edit by hand.

- Purpose: Executable Python source file.
- Source path: `.codex/skills/ui-ux-pro-max/scripts/core.py`
- Source link: [.codex/skills/ui-ux-pro-max/scripts/core.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/.codex/skills/ui-ux-pro-max/scripts/core.py)
- Risk notes: Writes only documented outputs when run; review CLI help before execution.

## Top-Level Classes And Functions

### `BM25`

- Kind: `class`
- Signature: `class BM25`
- Lines: 96-155
- Docstring: BM25 ranking algorithm for text search

### `_load_csv`

- Kind: `function`
- Signature: `def _load_csv(filepath)`
- Lines: 159-162
- Docstring: Load CSV and return list of dicts

### `_search_csv`

- Kind: `function`
- Signature: `def _search_csv(filepath, search_cols, output_cols, query, max_results)`
- Lines: 165-187
- Docstring: Core search function using BM25

### `detect_domain`

- Kind: `function`
- Signature: `def detect_domain(query)`
- Lines: 190-209
- Docstring: Auto-detect the most relevant domain from query

### `search`

- Kind: `function`
- Signature: `def search(query, domain, max_results)`
- Lines: 212-231
- Docstring: Main search function with auto-domain detection

### `search_stack`

- Kind: `function`
- Signature: `def search_stack(query, stack, max_results)`
- Lines: 234-253
- Docstring: Search stack-specific guidelines
