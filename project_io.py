from __future__ import annotations

from pathlib import Path
from typing import Any
import json
from note_model import Note


PROJECT_VERSION = 2


def save_project(
    path: str | Path,
    *,
    audio_path: str | None,
    notes: list[Note],
    settings: dict[str, Any] | None = None,
) -> None:
    data = {
        "version": PROJECT_VERSION,
        "audio_path": audio_path,
        "settings": settings or {},
        "notes": [n.to_dict() for n in sorted(notes, key=lambda x: (x.start, x.midi, x.end))],
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_project(path: str | Path) -> tuple[str | None, list[Note], dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    audio_path = data.get("audio_path")
    notes = [Note.from_dict(x) for x in data.get("notes", [])]
    settings = data.get("settings") or {}
    if not isinstance(settings, dict):
        settings = {}
    return audio_path, notes, settings
