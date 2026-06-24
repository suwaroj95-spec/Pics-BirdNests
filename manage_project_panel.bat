@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command "$root='%~dp0'; $body=(Get-Content -Raw -LiteralPath '%~f0') -split '(?m)^# POWERSHELL #\r?$',2; & ([scriptblock]::Create($body[1])) -Root $root @args" %*
exit /b %ERRORLEVEL%

# POWERSHELL #
param(
    [Parameter(Mandatory = $true)]
    [string]$Root,
    [string]$Command
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath $Root).Path.TrimEnd("\")
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Panel = Join-Path $ProjectRoot "project_panel.py"
$TmpDir = Join-Path $ProjectRoot "tmp"
$PidFile = Join-Path $TmpDir "project_panel.pid"
$LogFile = Join-Path $TmpDir "project_panel.log"
$ErrLogFile = Join-Path $TmpDir "project_panel.err.log"
$HostName = "127.0.0.1"
$Port = 8769
$StatusUrl = "http://${HostName}:${Port}/api/status"
$HomeUrl = "http://${HostName}:${Port}/"

function Write-Title([string]$Text) {
    Write-Host ""
    Write-Host "== $Text =="
}

function Test-Endpoint {
    param([string]$Url = $StatusUrl)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    } catch {
        return $false
    }
}

function Get-ManagedProcess {
    if (-not (Test-Path -LiteralPath $PidFile)) {
        return $null
    }
    $rawPid = (Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    $pidValue = 0
    if (-not [int]::TryParse(($rawPid -as [string]).Trim(), [ref]$pidValue)) {
        return $null
    }
    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return $null
    }
    $allowedPython = @(
        (Resolve-Path -LiteralPath $Python).Path,
        (Resolve-Path -LiteralPath (Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe") -ErrorAction SilentlyContinue).Path
    ) | Where-Object { $_ }
    $processPath = [string]$process.Path
    if ($allowedPython -notcontains $processPath) {
        return $null
    }
    return $process
}

function Get-PortOwner {
    $lines = netstat -ano | Select-String -Pattern (":$Port\s+.*LISTENING\s+(\d+)")
    if (-not $lines) {
        return $null
    }
    $pidValue = [int]$lines[0].Matches[0].Groups[1].Value
    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return $null
    }
    return $process
}

function Invoke-Check {
    Write-Title "Dependency check"
    $failed = $false

    if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
        Write-Host "FAIL project folder missing: $ProjectRoot"
        return 1
    }
    Write-Host "OK project folder: $ProjectRoot"

    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        Write-Host "FAIL missing virtualenv Python: $Python"
        return 1
    }
    Write-Host "OK Python executable: $Python"

    if (-not (Test-Path -LiteralPath $Panel -PathType Leaf)) {
        Write-Host "FAIL missing panel script: $Panel"
        return 1
    }
    Write-Host "OK panel script: $Panel"

    & $Python --version | Out-Host
    if ($LASTEXITCODE -ne 0) { $failed = $true }

    & $Python -m pip check | Out-Host
    if ($LASTEXITCODE -ne 0) { $failed = $true }

    & $Python -m py_compile $Panel | Out-Host
    if ($LASTEXITCODE -ne 0) { $failed = $true } else { Write-Host "OK project_panel.py compiles" }

    & $Python -c "import argparse,json,subprocess,sys,threading,time,webbrowser; from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer; from pathlib import Path; from urllib.parse import urlparse; print('OK panel imports')" | Out-Host
    if ($LASTEXITCODE -ne 0) { $failed = $true }

    & $Python $Panel --help | Out-Host
    if ($LASTEXITCODE -ne 0) { $failed = $true } else { Write-Host "OK project_panel.py --help" }

    & $Python -c "import cv2, numpy; print('OK optional workflow imports: cv2,numpy')" | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARN optional workflow dependencies are not ready. The panel can open, but crop/anomaly workflows may fail."
    }

    if ($failed) { return 1 }
    return 0
}

function Invoke-Start {
    $checkCode = Invoke-Check
    if ($checkCode -ne 0) {
        return $checkCode
    }

    if (-not (Test-Path -LiteralPath $TmpDir -PathType Container)) {
        New-Item -ItemType Directory -Path $TmpDir | Out-Null
    }

    $managed = Get-ManagedProcess
    if ($null -ne $managed) {
        Write-Host "RUNNING managed panel PID $($managed.Id)"
        Write-Host "URL: $HomeUrl"
        Write-Host "Log: $LogFile"
        return 0
    }

    $owner = Get-PortOwner
    if ($null -ne $owner) {
        $cmd = [string]$owner.CommandLine
        Write-Host "PORT CONFLICT: ${HostName}:${Port} is already used by PID $($owner.Id)"
        Write-Host "Owner path: $([string]$owner.Path)"
        Write-Host "No process was stopped."
        return 2
    }

    "Starting project_panel.py at $(Get-Date -Format s)" | Set-Content -LiteralPath $LogFile -Encoding UTF8
    "" | Set-Content -LiteralPath $ErrLogFile -Encoding UTF8
    $process = Start-Process -FilePath $Python `
        -ArgumentList @($Panel, "--host", $HostName, "--port", [string]$Port) `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -LiteralPath $PidFile -Value ([string]$process.Id) -Encoding ASCII

    $ready = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 250
        if (Test-Endpoint $StatusUrl -or Test-Endpoint $HomeUrl) {
            $ready = $true
            break
        }
    }

    Write-Host "Started panel on $HomeUrl"
    Write-Host "PID: $($process.Id)"
    Write-Host "PID file: $PidFile"
    Write-Host "Log: $LogFile"
    Write-Host "Error log: $ErrLogFile"
    Write-Host "Stop with: manage_project_panel.bat stop"
    if (-not $ready) {
        Write-Host "WARN endpoint did not respond yet. Check the log files above."
        return 3
    }
    return 0
}

function Invoke-Status {
    Write-Title "Panel status"
    $managed = Get-ManagedProcess
    $endpoint = Test-Endpoint $StatusUrl
    $owner = Get-PortOwner

    if ($null -ne $managed) {
        if ($endpoint) {
            Write-Host "RUNNING"
        } else {
            Write-Host "UNKNOWN: managed process exists but endpoint is not responding"
        }
        Write-Host "PID: $($managed.Id)"
        Write-Host "URL: $HomeUrl"
        Write-Host "Log: $LogFile"
        return 0
    }

    if (Test-Path -LiteralPath $PidFile) {
        Remove-Item -LiteralPath $PidFile -Force
        Write-Host "STALE PID FILE removed: $PidFile"
    }

    if ($null -ne $owner) {
        Write-Host "PORT CONFLICT: ${HostName}:${Port} is used by PID $($owner.Id)"
        Write-Host "Owner path: $([string]$owner.Path)"
        return 2
    }

    if ($endpoint) {
        Write-Host "UNKNOWN: endpoint responds but no managed PID was found"
        return 3
    }

    Write-Host "STOPPED"
    return 0
}

function Invoke-Stop {
    Write-Title "Stop panel"
    $managed = Get-ManagedProcess
    if ($null -eq $managed) {
        if (Test-Path -LiteralPath $PidFile) {
            Remove-Item -LiteralPath $PidFile -Force
            Write-Host "STALE PID FILE removed: $PidFile"
        }
        Write-Host "STOPPED: no managed project_panel.py process found"
        return 0
    }

    Write-Host "Stopping managed panel PID $($managed.Id)"
    Stop-Process -Id $managed.Id -Force
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 250
        $stillRunning = Get-Process -Id $managed.Id -ErrorAction SilentlyContinue
        if ($null -eq $stillRunning -and -not (Test-Endpoint $StatusUrl)) {
            break
        }
    }

    $stillThere = Get-Process -Id $managed.Id -ErrorAction SilentlyContinue
    if ($null -ne $stillThere) {
        Write-Host "FAIL process did not stop: PID $($managed.Id)"
        return 1
    }
    if (Test-Path -LiteralPath $PidFile) {
        Remove-Item -LiteralPath $PidFile -Force
    }
    Write-Host "STOPPED"
    return 0
}

function Show-Menu {
    while ($true) {
        Write-Host ""
        Write-Host "Bird Nest Pipeline Panel Manager"
        Write-Host "[1] Check dependencies"
        Write-Host "[2] Start Control Panel"
        Write-Host "[3] Panel status"
        Write-Host "[4] Terminate Control Panel"
        Write-Host "[0] Exit"
        $choice = Read-Host "Select"
        switch ($choice) {
            "1" { [void](Invoke-Check) }
            "2" { [void](Invoke-Start) }
            "3" { [void](Invoke-Status) }
            "4" { [void](Invoke-Stop) }
            "0" { return 0 }
            default { Write-Host "Unknown selection." }
        }
    }
}

switch (($Command -as [string]).ToLowerInvariant()) {
    "" { exit (Show-Menu) }
    "check" { exit (Invoke-Check) }
    "start" { exit (Invoke-Start) }
    "status" { exit (Invoke-Status) }
    "stop" { exit (Invoke-Stop) }
    default {
        Write-Host "Usage: manage_project_panel.bat [check|start|status|stop]"
        exit 64
    }
}
