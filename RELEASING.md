# Releasing AdopyHzEditor

The distributable application is the current React / TypeScript + pywebview UI (`web_ui.py`), not the legacy PySide6 entry point (`main.py`).

## Local release build

From the repository root on Windows:

```powershell
.\scripts\build_release.ps1 -Clean
```

The script:

1. uses `uv` when available (with a pip fallback),
2. installs `requirements-webui.txt`,
3. builds `frontend/` with Vite,
4. packages `web_ui.py` with PyInstaller,
5. bundles `frontend/dist` and `locales`, and
6. creates a ZIP.

Outputs:

```text
dist\AdopyHzEditor\AdopyHzEditor.exe
releases\AdopyHzEditor_Windows_vX.Y.Z.zip
```

Use `-NoZip` to skip ZIP creation or `-SkipInstall` when all Python and Node dependencies are already installed.

## Publish a GitHub Release

After release-related changes are merged, start from an up-to-date, clean `main` branch:

```powershell
git switch main
git pull --ff-only
.\scripts\release.ps1 -Version 0.8.0
```

`release.ps1` verifies that local `main` exactly matches `origin/main`, updates the shared version in `app_metadata.py`, performs a clean local Web UI release build, commits the version bump, creates an annotated `v0.8.0` tag, and pushes the commit and tag.

Pushing the tag triggers `.github/workflows/release.yml`. GitHub Actions rebuilds the Windows package from the tagged commit and publishes `AdopyHzEditor_Windows_v0.8.0.zip` as a GitHub Release asset with generated release notes.

To prepare the commit and tag without pushing them:

```powershell
.\scripts\release.ps1 -Version 0.8.0 -NoPush
```

## Version source

`app_metadata.py` is the single source of truth for `APP_VERSION` and GitHub repository metadata. Both desktop and Web UI code import from it. Do not add a second hard-coded application version elsewhere.
