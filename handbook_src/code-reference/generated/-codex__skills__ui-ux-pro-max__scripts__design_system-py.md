# `.codex/skills/ui-ux-pro-max/scripts/design_system.py`

Generated content. Do not edit by hand.

- Purpose: Executable Python source file.
- Source path: `.codex/skills/ui-ux-pro-max/scripts/design_system.py`
- Source link: [.codex/skills/ui-ux-pro-max/scripts/design_system.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/.codex/skills/ui-ux-pro-max/scripts/design_system.py)
- Risk notes: Writes only documented outputs when run; review CLI help before execution.

## Top-Level Classes And Functions

### `DesignSystemGenerator`

- Kind: `class`
- Signature: `class DesignSystemGenerator`
- Lines: 37-236
- Docstring: Generates design system recommendations from aggregated searches.

### `format_ascii_box`

- Kind: `function`
- Signature: `def format_ascii_box(design_system)`
- Lines: 242-364
- Docstring: Format design system as ASCII box with emojis (MCP-style).

### `format_markdown`

- Kind: `function`
- Signature: `def format_markdown(design_system)`
- Lines: 367-458
- Docstring: Format design system as markdown.

### `generate_design_system`

- Kind: `function`
- Signature: `def generate_design_system(query, project_name, output_format, persist, page, output_dir)`
- Lines: 462-487
- Docstring: Main entry point for design system generation.

Args:
    query: Search query (e.g., "SaaS dashboard", "e-commerce luxury")
    project_name: Optional project name for output header
    output_format: "ascii" (default) or "markdown"
    persist: If True, save design system to design-system/ folder
    page: Optional page name for page-specific override file
    output_dir: Optional output directory (defaults to current working directory)

Returns:
    Formatted design system string

### `persist_design_system`

- Kind: `function`
- Signature: `def persist_design_system(design_system, page, output_dir, page_query)`
- Lines: 491-539
- Docstring: Persist design system to design-system/<project>/ folder using Master + Overrides pattern.

Args:
    design_system: The generated design system dictionary
    page: Optional page name for page-specific override file
    output_dir: Optional output directory (defaults to current working directory)
    page_query: Optional query string for intelligent page override generation

Returns:
    dict with created file paths and status

### `format_master_md`

- Kind: `function`
- Signature: `def format_master_md(design_system)`
- Lines: 542-802
- Docstring: Format design system as MASTER.md with hierarchical override logic.

### `format_page_override_md`

- Kind: `function`
- Signature: `def format_page_override_md(design_system, page_name, page_query)`
- Lines: 805-911
- Docstring: Format a page-specific override file with intelligent AI-generated content.

### `_generate_intelligent_overrides`

- Kind: `function`
- Signature: `def _generate_intelligent_overrides(page_name, page_query, design_system)`
- Lines: 914-1017
- Docstring: Generate intelligent overrides based on page type using layered search.

Uses the existing search infrastructure to find relevant style, UX, and layout
data instead of hardcoded page types.

### `_detect_page_type`

- Kind: `function`
- Signature: `def _detect_page_type(context, style_results)`
- Lines: 1020-1052
- Docstring: Detect page type from context and search results.
