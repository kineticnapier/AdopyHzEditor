# React / TypeScript UI prototype

Experimental UI shell for AdopyHzEditor. The existing PySide6 application stays intact; this prototype launches separately.

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

When opened in a normal browser the UI uses local state and shows `Browser preview`. In pywebview it uses `window.pywebview.api` and shows `Python connected`.

Current scope: React/TypeScript shell, settings UI, timeline shell, and a minimal Python bridge. Audio playback, spectrogram rendering, note editing, project I/O, and MIDI/ADOFAI export remain in Python and should be migrated incrementally behind bridge methods.
