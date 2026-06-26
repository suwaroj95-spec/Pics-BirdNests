# Installation And Testing Instructions

## Core Runtime

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\InstallKit\requirements-core.txt
```

## Optional Runtime

```powershell
.\InstallKit\install_project_tools.ps1 -WithAnnotation
.\InstallKit\install_project_tools.ps1 -WithTracking
```

## Documentation Runtime

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\InstallKit\requirements-docs.txt
```

Documentation dependencies are separate from core pipeline requirements.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Documentation Build

```powershell
.\tools\build_documentation.ps1
```
