from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from core.note_model import Note


class PresetMixin:
    """Persistent single-note presets for the web editor.

    Presets live outside project files so names such as "Zaag" or "キック"
    can be reused across songs. A preset stores one normalized note with its
    start shifted to zero, preserving duration, pitch, curve shape,
    interpolation and target angle.
    """

    @staticmethod
    def _note_preset_path() -> Path:
        appdata = os.environ.get("APPDATA", "").strip()
        if appdata:
            base = Path(appdata) / "AdopyHzEditor"
        else:
            base = Path.home() / ".adopyhzeditor"
        base.mkdir(parents=True, exist_ok=True)
        return base / "note-presets.json"

    def _load_note_preset_map(self) -> dict[str, dict[str, Any]]:
        path = self._note_preset_path()
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(raw, dict):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for raw_name, raw_note in raw.items():
            name = str(raw_name).strip()
            if not name or not isinstance(raw_note, dict):
                continue
            try:
                note = Note.from_dict(dict(raw_note)).normalized()
            except Exception:
                continue
            out[name] = note.with_time_offset(-note.start).to_dict()
        return out

    def _save_note_preset_map(self, presets: dict[str, dict[str, Any]]) -> None:
        path = self._note_preset_path()
        path.write_text(
            json.dumps(presets, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_note_presets(self) -> list[dict[str, Any]]:
        presets = self._load_note_preset_map()
        result: list[dict[str, Any]] = []
        for name in sorted(presets, key=lambda x: x.casefold()):
            note = Note.from_dict(presets[name]).normalized()
            result.append({
                "name": name,
                "note": note.to_dict(),
                "duration": note.duration,
                "kind": "curve" if note.is_curve else "note",
            })
        return result

    def save_note_preset(self, name: str, index: int) -> dict[str, Any]:
        preset_name = str(name).strip()
        if not preset_name:
            raise ValueError("プリセット名を入力してください")
        if len(preset_name) > 80:
            raise ValueError("プリセット名が長すぎます")
        with self._lock:
            i = int(index)
            if i < 0 or i >= len(self.notes):
                raise ValueError("1個のノートを選択してください")
            note = self.notes[i].normalized().with_time_offset(-self.notes[i].normalized().start)
        presets = self._load_note_preset_map()
        presets[preset_name] = note.to_dict()
        self._save_note_preset_map(presets)
        self._status = f"プリセット「{preset_name}」を保存しました"
        return {"presets": self.get_note_presets(), "status": self._status}

    def delete_note_preset(self, name: str) -> dict[str, Any]:
        preset_name = str(name).strip()
        presets = self._load_note_preset_map()
        if preset_name not in presets:
            return {"presets": self.get_note_presets(), "status": "プリセットが見つかりません"}
        del presets[preset_name]
        self._save_note_preset_map(presets)
        self._status = f"プリセット「{preset_name}」を削除しました"
        return {"presets": self.get_note_presets(), "status": self._status}

    def insert_note_preset(self, name: str, at_time: float) -> dict[str, Any]:
        preset_name = str(name).strip()
        presets = self._load_note_preset_map()
        raw = presets.get(preset_name)
        if raw is None:
            raise ValueError("プリセットが見つかりません")
        template = Note.from_dict(raw).normalized()
        with self._lock:
            start = self._snap_time(float(at_time))
            max_start = max(0.0, float(self.duration) - max(0.001, template.duration))
            start = min(start, max_start)
            note = template.with_time_offset(start - template.start).normalized()
            if note.end > self.duration:
                note = self._with_times(note, note.start, self.duration)
            self._push_undo()
            self.notes.append(note)
            index = len(self.notes) - 1
            self._dirty = True
            self._sync_notes_to_player()
            self._status = f"プリセット「{preset_name}」を挿入しました"
            return {
                "notes": self._note_dicts(),
                "index": index,
                "indices": [index],
                "status": self._status,
            }
