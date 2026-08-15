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

## Python import rules

Implementation code imports modules directly from their package. Examples:

```python
from core.audio_player import AudioPlayer
from core.note_model import Note
from exporters.adofai import export_adofai
from importers.midi import import_midi
from tools.quick_hz import CalculateHzInfo
from desktop.editor_view import EditorView
from web.editing import EditingMixin
```

Historical root-level compatibility modules have been removed. Do not reintroduce imports such as `from audio_player import ...`, `from export_adofai import ...`, or `from web_backend_editing import ...`.

The Web UI CI scans Python imports and rejects references to the removed module names, so new code should use the package paths above.
