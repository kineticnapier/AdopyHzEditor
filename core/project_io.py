from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os
from note_model import Note


PROJECT_VERSION = 3


def _safe_relative_path(target: Path, base_dir: Path) -> str | None:
    try:
        return os.path.relpath(str(target.resolve()), str(base_dir.resolve())).replace("\\", "/")
    except Exception:
        return None


def _resolve_audio_path(project_path: Path, data: dict[str, Any]) -> str | None:
    """
    Resolve project audio in a portable-friendly order.

    Prefer the file next to/relative to the project over an old absolute path,
    so a copied project folder keeps working on another machine.
    """
    project_dir = project_path.resolve().parent

    raw_audio = data.get("audio_path")
    rel_audio = data.get("audio_path_relative")
    audio_filename = data.get("audio_filename")

    candidates: list[Path] = []

    def add_candidate(value: object, *, relative_to_project: bool) -> None:
        if value is None:
            return
        text = str(value).strip()
        if not text:
            return
        p = Path(text)
        if relative_to_project or not p.is_absolute():
            candidates.append(project_dir / p)
        else:
            candidates.append(p)

    # Portable local copy first.
    add_candidate(rel_audio, relative_to_project=True)

    # Old projects may have stored a relative audio_path directly.
    if raw_audio and not Path(str(raw_audio)).is_absolute():
        add_candidate(raw_audio, relative_to_project=True)

    # Original absolute path is useful on the same PC, but should not beat a
    # portable project-relative copy.
    if raw_audio and Path(str(raw_audio)).is_absolute():
        add_candidate(raw_audio, relative_to_project=False)

    # Last-resort: same folder as project using original basename.
    if audio_filename:
        add_candidate(audio_filename, relative_to_project=True)
    elif raw_audio:
        name = Path(str(raw_audio)).name
        if name:
            add_candidate(name, relative_to_project=True)

    seen: set[str] = set()
    for c in candidates:
        key = str(c)
        if key in seen:
            continue
        seen.add(key)
        try:
            if c.exists():
                return str(c.resolve())
        except Exception:
            pass

    # Return something user-facing for the missing-audio dialog.
    if raw_audio:
        return str(raw_audio)
    if rel_audio:
        return str(project_dir / str(rel_audio))
    return None


def save_project(
    path: str | Path,
    *,
    audio_path: str | None,
    notes: list[Note],
    settings: dict[str, Any] | None = None,
) -> None:
    project_path = Path(path)
    project_dir = project_path.resolve().parent
    audio_path_text = str(audio_path) if audio_path else None
    audio_relative: str | None = None
    audio_filename: str | None = None

    if audio_path_text:
        audio_file = Path(audio_path_text)
        audio_filename = audio_file.name
        try:
            audio_relative = _safe_relative_path(audio_file, project_dir)
        except Exception:
            audio_relative = None

    data = {
        "version": PROJECT_VERSION,
        # Keep the old field for compatibility with older builds.
        "audio_path": audio_path_text,
        # New portable fields.
        "audio_path_relative": audio_relative,
        "audio_filename": audio_filename,
        "settings": settings or {},
        "notes": [n.to_dict() for n in sorted(notes, key=lambda x: (x.start, x.midi, x.end))],
    }
    project_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_project(path: str | Path) -> tuple[str | None, list[Note], dict[str, Any]]:
    project_path = Path(path)
    data = json.loads(project_path.read_text(encoding="utf-8-sig"))
    audio_path = _resolve_audio_path(project_path, data)
    notes = [Note.from_dict(x) for x in data.get("notes", [])]
    settings = data.get("settings") or {}
    if not isinstance(settings, dict):
        settings = {}
    return audio_path, notes, settings
