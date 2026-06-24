param(
    [string]$Python = "python",
    [switch]$WithAnnotation,
    [switch]$WithTracking,
    [switch]$FromWheelhouse,
    [string]$Wheelhouse = ".\wheelhouse"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CoreReq = Join-Path $ScriptDir "requirements-core.txt"
$AnnotationReq = Join-Path $ScriptDir "requirements-optional-annotation.txt"
$TrackingReq = Join-Path $ScriptDir "requirements-optional-tracking.txt"
$VenvDir = Join-Path (Split-Path -Parent $ScriptDir) ".venv"

Write-Host "Bird Nest Research Project - tool installer"
Write-Host "Python command: $Python"

if (!(Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment: $VenvDir"
    & $Python -m venv $VenvDir
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (!(Test-Path $VenvPython)) {
    throw "Virtual environment Python not found: $VenvPython"
}

& $VenvPython -m pip install --upgrade pip setuptools wheel

function Install-Requirements {
    param(
        [string]$RequirementFile
    )

    if ($FromWheelhouse) {
        $ResolvedWheelhouse = Resolve-Path $Wheelhouse
        Write-Host "Installing from wheelhouse: $ResolvedWheelhouse"
        & $VenvPython -m pip install --no-index --find-links "$ResolvedWheelhouse" -r $RequirementFile
    } else {
        & $VenvPython -m pip install -r $RequirementFile
    }
}

Install-Requirements $CoreReq

if ($WithAnnotation) {
    Install-Requirements $AnnotationReq
}

if ($WithTracking) {
    Install-Requirements $TrackingReq
}

Write-Host ""
Write-Host "Done."
Write-Host "Run the panel with:"
Write-Host "  .\.venv\Scripts\python.exe project_panel.py --open"
