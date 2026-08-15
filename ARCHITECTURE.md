# Project structure

AdopyHzEditor has two UI entry points that share the same editor/domain code.

## Entry points

- `main.py` — legacy PySide6 desktop application entry point.
- `web_ui.py` — React / TypeScript + pywebview application entry point.

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

## Compatibility modules

Several small Python files remain at the repository root with historical names such as `audio_player.py`, `export_adofai.py`, or `editor_view.py`. They are compatibility aliases only; new implementation changes should be made in the package listed above instead of in those root aliases.

Do not add new application logic to compatibility aliases. They exist so older imports, scripts, packaging configuration, and external callers continue to work while the project structure is migrated incrementally.
