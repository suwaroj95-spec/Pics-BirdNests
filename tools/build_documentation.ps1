param(
    [switch]$InstallDocsDependencies,
    [string]$Python = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$PythonPath = Resolve-Path -LiteralPath $Python -ErrorAction SilentlyContinue
if (-not $PythonPath) {
    throw "Python not found: $Python. Create .venv first or pass -Python."
}

if ($InstallDocsDependencies) {
    & $Python -m pip install -r .\InstallKit\requirements-docs.txt
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& $Python -c "import importlib.util, sys; missing=[name for name in ('mkdocs','material') if importlib.util.find_spec(name) is None]; print('OK documentation dependencies' if not missing else 'Missing documentation dependencies: ' + ', '.join(missing)); sys.exit(1 if missing else 0)"
if ($LASTEXITCODE -ne 0) {
    throw "Documentation dependencies missing. Run .\tools\build_documentation.ps1 -InstallDocsDependencies"
}

& $Python .\tools\generate_code_reference.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python .\tools\verify_documentation_coverage.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m mkdocs build --strict
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Documentation built at docs\manual"
