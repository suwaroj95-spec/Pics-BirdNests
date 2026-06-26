# Local Project Panel And Safe Run Instructions

## Executable

`project_panel.py`

## Run

```powershell
.\.venv\Scripts\python.exe project_panel.py
```

Open:

```text
http://127.0.0.1:8769/
```

## Managed Run

```powershell
.\manage_project_panel.bat check
.\manage_project_panel.bat start
.\manage_project_panel.bat status
.\manage_project_panel.bat stop
```

## Safety Notes

- The panel binds to localhost by default
- The panel validates project paths and rejects path escape cases
- `manage_project_panel.bat stop` stops the managed panel process
- `run_project_panel.ps1` clears `__pycache__` folders and may stop old `project_panel.py` processes
