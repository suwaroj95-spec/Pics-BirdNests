from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "handbook_src" / "code-reference" / "documentation_coverage.json"

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


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def should_skip(path: Path) -> bool:
    return bool(set(path.relative_to(PROJECT_ROOT).parts) & EXCLUDED_PARTS)


def discover_executable_files() -> set[str]:
    found: set[str] = set()
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file() or should_skip(path):
            continue
        name = path.name.lower()
        if path.suffix == ".py" or path.suffix in {".ps1", ".bat"} or name.startswith("requirements") and path.suffix == ".txt":
            found.add(rel(path))
    return found


def main() -> int:
    if not MANIFEST_PATH.exists():
        print(f"Documentation coverage manifest missing: {MANIFEST_PATH}")
        print("Run: python tools/generate_code_reference.py")
        return 2

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    documented = {entry["path"] for entry in manifest.get("files", []) if entry.get("included")}
    discovered = discover_executable_files()

    missing = sorted(discovered - documented)
    stale = sorted(documented - discovered)

    if missing or stale:
        print("Documentation coverage verification failed.")
        if missing:
            print("")
            print("Missing executable documentation mapping:")
            for item in missing:
                print(f"  - {item}")
        if stale:
            print("")
            print("Stale documentation mapping:")
            for item in stale:
                print(f"  - {item}")
        print("")
        print("Generated outputs, binary assets, raw images, virtual environments, caches, and run artifacts are intentionally excluded.")
        return 1

    print(f"Documentation coverage verified for {len(discovered)} executable files.")
    print("Excluded generated outputs and binary data by documented rules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
