$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (!(Test-Path $VenvPython)) {
    throw "Virtual environment Python not found: $VenvPython"
}

$MatplotlibConfigDir = Join-Path $ProjectRoot ".venv\mplconfig"
New-Item -ItemType Directory -Force -Path $MatplotlibConfigDir | Out-Null
$env:MPLCONFIGDIR = $MatplotlibConfigDir

Write-Host "Clearing Python cache folders..."
Get-ChildItem -Path $ProjectRoot -Directory -Filter "__pycache__" -Recurse -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

$OldPanels = @()
try {
    $OldPanels = Get-CimInstance Win32_Process -ErrorAction Stop |
        Where-Object { $_.Name -like "python*" -and $_.CommandLine -like "*project_panel.py*" }

    if ($OldPanels) {
        Write-Host "Stopping old project_panel.py processes..."
        foreach ($Process in $OldPanels) {
            Stop-Process -Id $Process.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
} catch {
    Write-Host "Skipping old panel process cleanup: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "Starting Bird Nest Pipeline Panel"
Write-Host "URL: http://127.0.0.1:8769/"
Write-Host "Press Ctrl+C in this terminal to stop the panel."
Write-Host ""

& $VenvPython project_panel.py --open
