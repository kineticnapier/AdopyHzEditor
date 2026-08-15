# Project structure

AdopyHzEditor has two UI entry points that share the same editor/domain code.

## Entry points

- `main.py` — legacy PySide6 desktop application entry point.
- `web_ui.py` — React / TypeScript + pywebview application entry point and current distributable UI.

## Python packages

- `core/` — notes, audio playback/analysis, and project serialization shared by both UIs.
- `exporters/` — ADOFAI/MIDI exporters and ADOFAI angle helpers.
- `importers/` — file import logic such as MIDI parsing/cleanup.
- `tools/` — reusable editor utilities such as Quick Hz.
- `desktop/` — PySide6-specific editor widgets, dialogs, styling helpers, and updater UI.
- `web/` — pywebview backend bridge and Web-only editing/preset/tool APIs.

## Frontend

`frontend/src/` is split by role:

- `api/` — TypeScript bridge contracts.
- `components/` — top-level reusable UI components.
- `dialogs/` — modal dialogs and tool dialogs.
- `editor/` — canvas, timeline, and editor shortcuts.
- `settings/` — settings and note-preset panels.
- `App.tsx` / `main.tsx` — React composition and entry point.

## Imports

Python application code imports implementation modules through their package paths, for example:

- `core.audio_player`
- `exporters.adofai`
- `importers.midi`
- `tools.quick_hz`
- `desktop.editor_view`
- `web.editing`

The historical root-level compatibility modules were removed. Do not recreate aliases such as `audio_player.py`, `export_adofai.py`, or `editor_view.py` at the repository root, and do not add imports that depend on those old names.

## Application metadata

`app_metadata.py` is the side-effect-free source of truth for application name, version, and GitHub repository metadata. Both UI stacks should import metadata from there rather than defining their own version constants.

## Builds and releases

The release package targets `web_ui.py` and bundles the built React frontend. See `RELEASING.md` for the local build and tagged GitHub Release workflow.
