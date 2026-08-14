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
- Project save/load
- MIDI import/export
- Basic ADOFAI export using the existing `rabbit_zip` backend
- Existing keyboard shortcuts for the migrated operations

The Python analysis, audio, MIDI, project and ADOFAI logic is reused behind the pywebview bridge instead of being rewritten in TypeScript.

## Still to migrate

The full legacy ADOFAI export dialog/options, help/update dialogs and a few specialized editor operations are still provided only by the PySide6 application. The current ADOFAI button performs a basic/default export.
