from __future__ import annotations

import ast
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "handbook_src" / "code-reference" / "generated"
INDEX_PATH = PROJECT_ROOT / "handbook_src" / "code-reference" / "index.md"
COVERAGE_MANIFEST = PROJECT_ROOT / "handbook_src" / "code-reference" / "documentation_coverage.json"

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "tmp",
    "RawPics",
    "Crops",
    "BacktestSelection",
    "AnomalyDetection",
    "AnomalyDetectionTest",
    "AnomalyDetectionPanelTest",
    "docs",
}

PYTHON_PURPOSES = {
    "anomaly_detection.py": "Ranks suspicious selected crops using feature-based anomaly scoring.",
    "crop_clean_patches.py": "Generates clean and dirty crop patches plus metadata from raw image pairs.",
    "project_panel.py": "Serves the local workflow panel and safely launches pipeline subprocesses.",
    "select_birdnest_samples.py": "Backtests crop-selection systems and writes selected manifests.",
    "tools/analyze_blue_marker_distribution.py": "Analyzes Blue Marker distribution and source/marked alignment.",
    "tools/audit_crop_dataset_lineage.py": "Audits crop lineage against source-level split and final ground truth.",
    "tools/audit_crop_marker_leakage.py": "Audits crop images for marker-like blue annotation leakage.",
    "tools/build_ground_truth_from_markers.py": "Builds preliminary ground-truth labels from verified Blue Markers.",
    "tools/build_source_level_split.py": "Builds deterministic train/validation/test split manifests by source image.",
    "tools/build_sourcewise_error_atlas.py": "Builds source-wise error profiles, rankings, and review examples.",
    "tools/finalize_ground_truth.py": "Finalizes human-verified preliminary ground-truth labels.",
    "tools/generate_code_reference.py": "Generates this documentation-only code reference from source files.",
    "tools/run_crop_baseline_experiment.py": "Runs a handcrafted crop baseline experiment with safety checks.",
    "tools/run_sourcewise_crop_robustness.py": "Runs source-wise crop robustness evaluation.",
    "tools/verify_documentation_coverage.py": "Verifies every executable file has documentation coverage mapping.",
}

SCRIPT_PURPOSES = {
    "InstallKit/install_project_tools.ps1": "Creates or updates the project virtual environment and installs runtime requirements.",
    "InstallKit/make_wheelhouse.ps1": "Downloads Python wheels for offline installation.",
    "clear_project_cache.ps1": "Removes Python __pycache__ folders under the project root.",
    "run_project_panel.ps1": "Starts the project panel after preparing local runtime state.",
    "run_project_panel.bat": "Batch wrapper for run_project_panel.ps1.",
    "manage_project_panel.bat": "Checks, starts, reports, or stops the managed project panel process.",
    "tools/build_documentation.ps1": "Builds documentation safely without changing pipeline outputs.",
}

REQUIREMENT_PURPOSES = {
    "InstallKit/requirements-core.txt": "Core runtime dependencies for pipeline and panel work.",
    "InstallKit/requirements-docs.txt": "Documentation-only dependencies for MkDocs Material.",
    "InstallKit/requirements-optional-annotation.txt": "Optional annotation dependency list.",
    "InstallKit/requirements-optional-tracking.txt": "Optional experiment tracking dependency list.",
}


@dataclass(frozen=True)
class Symbol:
    kind: str
    name: str
    signature: str
    docstring: str
    start_line: int
    end_line: int


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def should_skip(path: Path) -> bool:
    relative_parts = set(path.relative_to(PROJECT_ROOT).parts)
    return bool(relative_parts & EXCLUDED_PARTS)


def discover_files() -> list[Path]:
    files: list[Path] = []
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        name = path.name.lower()
        if path.suffix == ".py" or path.suffix in {".ps1", ".bat"} or name.startswith("requirements") and path.suffix == ".txt":
            files.append(path)
    return sorted(files, key=lambda item: rel(item).lower())


def source_base_url() -> str:
    try:
        raw = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""
    if raw.endswith(".git"):
        raw = raw[:-4]
    if raw.startswith("git@github.com:"):
        raw = "https://github.com/" + raw.split(":", 1)[1]
    return raw


def signature_for(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> str:
    if isinstance(node, ast.ClassDef):
        return f"class {node.name}"
    args = []
    for arg in node.args.posonlyargs + node.args.args:
        args.append(arg.arg)
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    for arg in node.args.kwonlyargs:
        args.append(arg.arg)
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({', '.join(args)})"


def python_symbols(path: Path) -> list[Symbol]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    symbols: list[Symbol] = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(
                Symbol(
                    kind="class" if isinstance(node, ast.ClassDef) else "function",
                    name=node.name,
                    signature=signature_for(node),
                    docstring=ast.get_docstring(node) or "",
                    start_line=getattr(node, "lineno", 0),
                    end_line=getattr(node, "end_lineno", getattr(node, "lineno", 0)),
                )
            )
    return symbols


def slug_for(path: Path) -> str:
    return rel(path).replace("/", "__").replace("\\", "__").replace(".", "-")


def purpose_for(path: Path) -> str:
    relative = rel(path)
    if path.suffix == ".py" and relative.startswith("tests/"):
        return "Automated test module covering pipeline safety, validation, or documentation-relevant behavior."
    if path.suffix == ".py":
        return PYTHON_PURPOSES.get(relative, "Executable Python source file.")
    if path.suffix in {".ps1", ".bat"}:
        return SCRIPT_PURPOSES.get(relative, "Operational script.")
    return REQUIREMENT_PURPOSES.get(relative, "Requirements file.")


def risk_for(path: Path) -> str:
    relative = rel(path)
    if relative == "crop_clean_patches.py":
        return "`--clear-output` deletes generated crop/debug image files under the selected output directory."
    if relative in {"run_project_panel.ps1", "manage_project_panel.bat"}:
        return "Can stop local panel processes and write PID/log files under `tmp`."
    if relative == "clear_project_cache.ps1":
        return "Deletes `__pycache__` folders under the project root."
    if relative.startswith("InstallKit/"):
        return "May install or download packages and modify `.venv` or `wheelhouse`."
    if relative.startswith("tools/run_") or "baseline" in relative:
        return "Writes experiment outputs and may create model/report artifacts."
    return "Writes only documented outputs when run; review CLI help before execution."


def write_reference(path: Path, base_url: str) -> dict[str, object]:
    relative = rel(path)
    out = OUTPUT_DIR / f"{slug_for(path)}.md"
    source_url = f"{base_url}/blob/main/{relative}" if base_url else ""
    lines = [
        f"# `{relative}`",
        "",
        "Generated content. Do not edit by hand.",
        "",
        f"- Purpose: {purpose_for(path)}",
        f"- Source path: `{relative}`",
        f"- Source link: [{relative}]({source_url})" if source_url else f"- Source link: `{relative}`",
        f"- Risk notes: {risk_for(path)}",
        "",
    ]
    symbol_count = 0
    if path.suffix == ".py":
        symbols = python_symbols(path)
        symbol_count = len(symbols)
        lines.append("## Top-Level Classes And Functions")
        lines.append("")
        if not symbols:
            lines.append("No top-level classes or functions were found.")
        for symbol in symbols:
            doc = symbol.docstring or "No docstring."
            lines.extend(
                [
                    f"### `{symbol.name}`",
                    "",
                    f"- Kind: `{symbol.kind}`",
                    f"- Signature: `{symbol.signature}`",
                    f"- Lines: {symbol.start_line}-{symbol.end_line}",
                    f"- Docstring: {doc}",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "## File-Level Reference",
                "",
                f"- Usage: run or inspect `{relative}` according to project README and operational pages.",
                "- Inputs: local project files and parameters declared in the script or requirements file.",
                "- Outputs: documented installation, lifecycle, or dependency effects.",
                "",
            ]
        )
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {
        "path": relative,
        "reference": rel(out),
        "purpose": purpose_for(path),
        "symbol_count": symbol_count,
        "included": True,
    }


def write_index(records: list[dict[str, object]]) -> None:
    lines = [
        "# Code Reference",
        "",
        "Generated code reference index. Do not edit generated sections by hand.",
        "",
        "Coverage rules exclude generated outputs, binary assets, raw image folders, virtual environments, caches, and full CSV row content.",
        "",
        "## Files",
        "",
    ]
    for record in records:
        title = record["path"]
        href = Path(record["reference"]).relative_to("handbook_src/code-reference").as_posix()
        lines.append(f"- [`{title}`]({href})")
    INDEX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_url = source_base_url()
    files = discover_files()
    records = [write_reference(path, base_url) for path in files]
    write_index(records)
    manifest = {
        "generated_by": "tools/generate_code_reference.py",
        "coverage_scope": "Executable Python, PowerShell, batch, and requirements files only.",
        "excluded": sorted(EXCLUDED_PARTS),
        "files": records,
    }
    COVERAGE_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Generated {len(records)} code reference pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
