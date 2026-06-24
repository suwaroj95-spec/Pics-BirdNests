$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "Clearing Python cache folders under:"
Write-Host $ProjectRoot

Get-ChildItem -Path $ProjectRoot -Directory -Filter "__pycache__" -Recurse -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Done."
