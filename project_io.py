from __future__ import annotations

from pathlib import Path
import json
from note_model import Note


def save_project(path: str | Path, *, audio_path: str | None, notes: list[Note]) -> None:
    data = {
        "version": 1,
        "audio_path": audio_path,
        "notes": [n.to_dict() for n in sorted(notes, key=lambda x: (x.start, x.midi, x.end))],
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_project(path: str | Path) -> tuple[str | None, list[Note]]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return data.get("audio_path"), [Note.from_dict(x) for x in data.get("notes", [])]
