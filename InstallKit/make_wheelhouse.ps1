param(
    [string]$Python = "python",
    [string]$Output = ".\wheelhouse",
    [switch]$WithAnnotation,
    [switch]$WithTracking
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CoreReq = Join-Path $ScriptDir "requirements-core.txt"
$AnnotationReq = Join-Path $ScriptDir "requirements-optional-annotation.txt"
$TrackingReq = Join-Path $ScriptDir "requirements-optional-tracking.txt"

New-Item -ItemType Directory -Force -Path $Output | Out-Null

Write-Host "Downloading core wheels to: $Output"
& $Python -m pip download --dest $Output -r $CoreReq

if ($WithAnnotation) {
    Write-Host "Downloading optional annotation wheels to: $Output"
    & $Python -m pip download --dest $Output -r $AnnotationReq
}

if ($WithTracking) {
    Write-Host "Downloading optional tracking wheels to: $Output"
    & $Python -m pip download --dest $Output -r $TrackingReq
}

Write-Host ""
Write-Host "Wheelhouse is ready."
Write-Host "Copy this folder with InstallKit, then install later with:"
Write-Host "  .\InstallKit\install_project_tools.ps1 -FromWheelhouse -Wheelhouse .\wheelhouse"
