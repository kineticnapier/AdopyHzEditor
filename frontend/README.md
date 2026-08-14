# React / TypeScript UI prototype

Experimental React/TypeScript front end for AdopyHzEditor. The existing PySide6 application stays intact; this version launches separately through `web_ui.py`.

## Build and run

```powershell
cd frontend
npm install
npm run build
cd ..
python -m pip install -r requirements-webui.txt
python web_ui.py
```

## Vite development mode

```powershell
cd frontend
npm run dev
```

In another PowerShell window:

```powershell
$env:ADOPY_WEB_UI_URL = "http://localhost:5173"
python web_ui.py
```

## Migrated so far

- Audio open, playback, stop, seeking and playback speed/volume
- CQT analysis and spectrogram rendering on an HTML canvas
- Fixed notes and curve notes, selection, move, delete, undo/redo, copy/cut/paste
- View navigation, pitch/time zoom and Spec / Notes / Both modes
- Playback, export, grid/snap, view, analysis and curve settings
- Project save/load, notes-only project load and project-note merge
- Blank workspace configuration
- MIDI import/export and selected-note MIDI export
- Advanced ADOFAI export options using the existing Python exporter
- ADOFAI Tile Preview and Debug Preview
- Project-song copy and automatic/manual songOffset export workflow
- Help / Quick Start and Releases/update flow
- Quick Hz Tools, including chart append
- Harmonic Diagram preview and insertion
- Language preference selection
- Existing keyboard shortcuts for the migrated operations
- Compact File / Edit / Analyze / Tools / Options / Help menus

The Python analysis, audio, MIDI, project, Quick Hz and ADOFAI logic is reused behind the pywebview bridge instead of being rewritten in TypeScript.

## Still to migrate / harden

- The richer legacy MIDI import-options dialog and its cleanup choices
- The exact legacy missing-project-audio prompt/locate workflow
- Unsaved-change confirmation when replacing/closing a web-ui document
- Full React-side localization of every hard-coded web label
- A few small legacy confirmation/message-box details

The PySide6 application remains available while these parity details are finished.
