from __future__ import annotations

import csv
import io
import json
import shutil
import webbrowser
from pathlib import Path
from typing import Any

import webview

from exporters.adofai import (
    build_adofai_debug_rows,
    build_adofai_level,
    build_tile_preview_points,
)
from i18n import tr


ADOF_FILE_TYPES = ("ADOFAI Level (*.adofai)", "All files (*.*)")
APP_VERSION = "0.7.2"
GITHUB_RELEASES_URL = "https://github.com/kineticnapier/AdopyHzEditor/releases"

_HELP_SECTIONS: list[tuple[str, str, str]] = [
    ("quick_start", "help.quick_start.title", "help.quick_start.body"),
    ("controls", "help.controls.title", "help.controls.body"),
    ("adofai_export", "help.adofai_export.title", "help.adofai_export.body"),
    ("pitch_export", "help.pitch_export.title", "help.pitch_export.body"),
    ("curve_glide", "help.curve_glide.title", "help.curve_glide.body"),
    ("troubleshooting", "help.troubleshooting.title", "help.troubleshooting.body"),
    ("about", "help.about.title", "help.about.body"),
]


def _as_float(value: Any, default: float, lo: float | None = None, hi: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float(default)
    if lo is not None:
        result = max(float(lo), result)
    if hi is not None:
        result = min(float(hi), result)
    return result


def _as_int(value: Any, default: int, lo: int | None = None, hi: int | None = None) -> int:
    try:
        result = int(round(float(value)))
    except (TypeError, ValueError):
        result = int(default)
    if lo is not None:
        result = max(int(lo), result)
    if hi is not None:
        result = min(int(hi), result)
    return result


def _choice(value: Any, allowed: set[str], default: str) -> str:
    text = str(value)
    return text if text in allowed else default


class AdoFAIMixin:
    """Advanced ADOFAI export and help APIs used by the web UI."""

    def get_adofai_export_defaults(self, selected_indices: list[int] | None = None) -> dict[str, Any]:
        with self._lock:
            selected = self._valid_export_indices(selected_indices)
            first_source = [self.notes[i].normalized() for i in selected] if selected else [n.normalized() for n in self.notes]
            auto_offset = min((n.start for n in first_source), default=0.0) * 1000.0
            bpm = float(self.settings.get("bpm", 175.0))
            has_song = bool(self.audio_path)
        return {
            "method": "rabbit_zip",
            "baseBpm": bpm,
            "angleOnlyBpm": max(1000.0, bpm * 10.0),
            "harmonyMode": "fifth +7",
            "harmonyCustomSemitone": 7.0,
            "harmonyEpsilonMs": 0.001,
            "harmonyTuning": "equal temperament",
            "harmonyRootMode": "minimax cents",
            "harmonyTimingMode": "angle-only",
            "harmonyVisualMode": "round 45°",
            "harmonyVisualStep": 45.0,
            "harmonyPolyCycleAngle": 720.0,
            "harmonyPolyMaxDenominator": 24,
            "harmonyPolyRatioOctaveMode": "octave-folded",
            "xMode": "floor",
            "fixedX": 8.0,
            "targetBpm": max(1000.0, bpm * 10.0),
            "maxTiles": 200000,
            "maxTilesPerNote": 5000,
            "trackVisual": "normal",
            "visualPathMode": "raw",
            "visualPathAngle": 90.0,
            "visualPositionMode": "off",
            "visualPositionX": 0.0,
            "visualPositionY": 0.0,
            "finalAngleMode": "scaled",
            "finalCustomAngle": 180.0,
            "finalCardinalStep": 90.0,
            "useProjectSong": has_song,
            "copyProjectSong": has_song,
            "songOffsetAuto": True,
            "songOffsetMs": round(auto_offset, 3),
            "selectedOnly": bool(selected),
        }

    def _valid_export_indices(self, indices: list[int] | None) -> list[int]:
        if not indices:
            return []
        out: list[int] = []
        seen: set[int] = set()
        for raw in indices:
            try:
                index = int(raw)
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(self.notes) and index not in seen:
                out.append(index)
                seen.add(index)
        return sorted(out)

    def _prepare_adofai_export(
        self,
        raw_options: dict[str, Any] | None,
        selected_indices: list[int] | None,
    ) -> tuple[list[Any], dict[str, Any], dict[str, Any]]:
        raw = dict(raw_options or {})
        with self._lock:
            selected = self._valid_export_indices(selected_indices)
            selected_only = bool(raw.get("selectedOnly", False)) and bool(selected)
            source = [self.notes[i] for i in selected] if selected_only else list(self.notes)
            semitones = int(self.settings.get("exportOctave", 0)) * 12 + int(self.settings.get("exportSemitone", 0))
            notes = [n.with_pitch_offset(semitones) for n in source]
            audio_path = self.audio_path
            default_bpm = float(self.settings.get("bpm", 175.0))

        if not notes:
            raise ValueError("No notes to export")

        auto_offset_ms = min((n.normalized().start for n in source), default=0.0) * 1000.0
        use_song = bool(raw.get("useProjectSong", bool(audio_path))) and bool(audio_path)
        copy_song = bool(raw.get("copyProjectSong", True)) and use_song
        auto_song_offset = bool(raw.get("songOffsetAuto", True))
        song_offset_ms = auto_offset_ms if auto_song_offset else _as_float(raw.get("songOffsetMs"), auto_offset_ms, -3600000.0, 3600000.0)

        opts = {
            "method": _choice(raw.get("method"), {"rabbit_zip", "angle_only", "harmony"}, "rabbit_zip"),
            "base_bpm": _as_float(raw.get("baseBpm"), default_bpm, 1.0, 999999.0),
            "angle_only_bpm": _as_float(raw.get("angleOnlyBpm"), max(1000.0, default_bpm * 10.0), 1.0, 999999.0),
            "harmony_mode": _choice(raw.get("harmonyMode"), {"off", "octave +12", "fifth +7", "major third +4", "minor third +3", "lower octave -12", "major triad", "minor triad", "sus4", "dominant 7", "custom"}, "fifth +7"),
            "harmony_custom_semitone": _as_float(raw.get("harmonyCustomSemitone"), 7.0, -48.0, 48.0),
            "harmony_epsilon_ms": _as_float(raw.get("harmonyEpsilonMs"), 0.001, 0.000001, 10.0),
            "harmony_tuning": _choice(raw.get("harmonyTuning"), {"equal temperament", "just intonation"}, "equal temperament"),
            "harmony_root_mode": _choice(raw.get("harmonyRootMode"), {"fixed root", "least squares Hz", "least squares cents", "minimax cents"}, "minimax cents"),
            "harmony_timing_mode": _choice(raw.get("harmonyTimingMode"), {"setspeed", "angle-only", "ratio-polyrhythm"}, "angle-only"),
            "harmony_visual_mode": _choice(raw.get("harmonyVisualMode"), {"raw", "round 45°", "round 90°", "custom step"}, "round 45°"),
            "harmony_visual_step": _as_float(raw.get("harmonyVisualStep"), 45.0, 1.0, 180.0),
            "harmony_poly_cycle_angle": _as_float(raw.get("harmonyPolyCycleAngle"), 720.0, 1.0, 100000.0),
            "harmony_poly_pseudo_angle": 30.0,
            "harmony_poly_max_denominator": _as_int(raw.get("harmonyPolyMaxDenominator"), 24, 1, 256),
            "harmony_poly_ratio_octave_mode": _choice(raw.get("harmonyPolyRatioOctaveMode"), {"octave-folded", "absolute"}, "octave-folded"),
            "rabbit_x_mode": _choice(raw.get("xMode"), {"floor", "lowest_floor", "round", "ceil", "fixed", "target_bpm"}, "floor"),
            "rabbit_fixed_x": _as_float(raw.get("fixedX"), 8.0, 0.000001, 100000.0),
            "rabbit_target_bpm": _as_float(raw.get("targetBpm"), max(1000.0, default_bpm * 10.0), 1.0, 999999.0),
            "max_tiles": _as_int(raw.get("maxTiles"), 200000, 0, 10000000),
            "max_tiles_per_note": _as_int(raw.get("maxTilesPerNote"), 5000, 0, 1000000),
            "track_visual": _choice(raw.get("trackVisual"), {"normal", "faint", "very faint", "hidden"}, "normal"),
            "visual_path_mode": _choice(raw.get("visualPathMode"), {"raw", "upward", "upward avoid", "twirl upward"}, "raw"),
            "visual_path_angle": _as_float(raw.get("visualPathAngle"), 90.0, 0.0, 359.999),
            "visual_position_mode": _choice(raw.get("visualPositionMode"), {"off", "note step"}, "off"),
            "visual_position_x": _as_float(raw.get("visualPositionX"), 0.0, -100000.0, 100000.0),
            "visual_position_y": _as_float(raw.get("visualPositionY"), 0.0, -100000.0, 100000.0),
            "phase_continuous_glide": True,
            "final_angle_mode": _choice(raw.get("finalAngleMode"), {"scaled", "cardinal", "horizontal", "custom"}, "scaled"),
            "final_custom_angle": _as_float(raw.get("finalCustomAngle"), 180.0, 0.001, 359.999),
            "final_cardinal_step": _as_float(raw.get("finalCardinalStep"), 90.0, 1.0, 180.0),
            "song_filename": Path(audio_path).name if use_song and audio_path else None,
            "song_offset_ms": float(song_offset_ms) if use_song else None,
        }
        workflow = {
            "copySong": copy_song,
            "songSourcePath": audio_path if use_song else None,
            "songOffsetAuto": auto_song_offset,
            "selectedOnly": selected_only,
        }
        return notes, opts, workflow

    def preview_adofai_tiles(self, options: dict[str, Any], selected_indices: list[int] | None = None) -> dict[str, Any]:
        notes, build_opts, _workflow = self._prepare_adofai_export(options, selected_indices)
        level, stats = build_adofai_level(notes, **build_opts)
        points = build_tile_preview_points(level.get("angleData", []), max_preview_tiles=5000)
        payload = [{"x": float(x), "y": float(y), "angle": float(angle)} for x, y, angle in points]
        total = int(stats.get("floors_total", max(0, len(payload) - 1)) or 0)
        return {
            "points": payload,
            "stats": stats,
            "shownTiles": max(0, len(payload) - 1),
            "totalTiles": total,
            "limited": total > max(0, len(payload) - 1),
        }

    def preview_adofai_debug(self, options: dict[str, Any], selected_indices: list[int] | None = None) -> dict[str, Any]:
        notes, build_opts, _workflow = self._prepare_adofai_export(options, selected_indices)
        rows = build_adofai_debug_rows(notes, **build_opts)
        total_tiles = sum(int(row.get("tiles_est", 0) or 0) for row in rows)
        summary = {
            "rows": len(rows),
            "estimatedTiles": total_tiles,
            "targetAngleUsed": sum(1 for row in rows if row.get("target_angle_used")),
            "targetAngleIgnored": sum(1 for row in rows if row.get("target_angle_ignored")),
            "finalVisualCorrections": sum(1 for row in rows if row.get("final_visual_used")),
            "warnings": sum(1 for row in rows if row.get("warning")),
        }
        max_rows = 5000
        return {"rows": rows[:max_rows], "summary": summary, "limited": len(rows) > max_rows}

    def export_adofai_advanced(self, options: dict[str, Any], selected_indices: list[int] | None = None) -> dict[str, Any]:
        notes, build_opts, workflow = self._prepare_adofai_export(options, selected_indices)
        path = self._dialog(webview.FileDialog.SAVE, file_types=ADOF_FILE_TYPES, save_filename="level.adofai")
        if not path:
            return {"ok": False, "status": "Cancelled"}
        if Path(path).suffix.lower() != ".adofai":
            path += ".adofai"

        level, stats = build_adofai_level(notes, **build_opts)
        Path(path).write_text(json.dumps(level, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

        copied_song: str | None = None
        source = workflow.get("songSourcePath")
        if workflow.get("copySong") and source:
            source_path = Path(str(source)).resolve()
            target = Path(path).resolve().parent / source_path.name
            if source_path != target:
                shutil.copy2(source_path, target)
            copied_song = str(target)

        with self._lock:
            self._status = f"Exported {Path(path).name} ({stats.get('tiles_total', 0)} tiles)"
        return {
            "ok": True,
            "path": str(path),
            "copiedSong": copied_song,
            "stats": stats,
            "status": self._status,
        }

    def debug_rows_as_text(self, rows: list[dict[str, Any]], fmt: str = "tsv") -> str:
        if not rows:
            return ""
        columns = list(rows[0].keys())
        if fmt == "csv":
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(columns)
            for row in rows:
                writer.writerow([row.get(key, "") for key in columns])
            return buffer.getvalue()
        lines = ["\t".join(columns)]
        lines.extend("\t".join(str(row.get(key, "")) for key in columns) for row in rows)
        return "\n".join(lines)

    def get_help_sections(self) -> dict[str, Any]:
        sections = []
        for section_id, title_key, body_key in _HELP_SECTIONS:
            sections.append({
                "id": section_id,
                "title": tr(title_key),
                "body": tr(body_key, version=APP_VERSION, releases_url=GITHUB_RELEASES_URL),
            })
        return {"header": tr("help.header"), "sections": sections, "releasesUrl": GITHUB_RELEASES_URL}

    def open_releases_page(self) -> dict[str, Any]:
        ok = bool(webbrowser.open(GITHUB_RELEASES_URL))
        return {"ok": ok, "url": GITHUB_RELEASES_URL}
