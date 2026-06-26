# Troubleshooting And Recovery

## Dependency Problems

Run:

```powershell
.\manage_project_panel.bat check
```

For docs:

```powershell
.\tools\build_documentation.ps1 -InstallDocsDependencies
```

## Port Conflict

The panel uses `127.0.0.1:8769`. Use:

```powershell
.\manage_project_panel.bat status
```

## Unsafe Output Risk

Avoid running `--clear-output` on important folders unless they are backed up.

## Recovery Principle

Use a new output directory for experiments, for example `Crops_Test`, rather than overwriting `Crops`.
