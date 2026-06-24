@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0run_project_panel.ps1"
