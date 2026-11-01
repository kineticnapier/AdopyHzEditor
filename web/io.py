from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import webview

from exporters.adofai import build_adofai_level
from exporters.midi import export_midi
from importers.midi import import_midi
from core.note_model import Note
from core.project_io import load_project, save_project

AUDIO_FILE_TYPES = ("音声ファイル (*.wav;*.mp3;*.ogg;*.flac;*.m4a;*.aac)", "すべてのファイル (*.*)")
PROJECT_FILE_TYPES = ("AdopyHzEditorプロジェクト (*.adopyhz;*.ahe.json)", "JSON (*.json)", "すべてのファイル (*.*)")
MIDI_FILE_TYPES = ("MIDIファイル (*.mid;*.midi)", "すべてのファイル (*.*)")
ADOF_FILE_TYPES = ("ADOFAI譜面 (*.adofai)", "すべてのファイル (*.*)")


# One canonical settings baseline is used both for a fresh Bridge and when
# restoring an older project that omits newer keys. Missing project fields must
# never inherit values from the previously-open document.
DEFAULT_EDITOR_SETTINGS: dict[str, Any] = {
    "volume": 85,
    "speed": 1.0,
    "notePreview": True,
    "previewVolume": 20,
    "previewOctave": 0,
    "previewSound": "sine",
    "exportOctave": 0,
    "exportSemitone": 0,
    "gridEnabled": False,
    "metronomeEnabled": False,
    "bpm": 175.0,
    "offsetMs": 0.0,
    "metronomeVolume": 35,
    "snapEnabled": False,
    "snapDiv": 1,
    "contrast": 115,
    "gamma": 75,
    "enhance": True,
    "displayMode": "wavetone",
    "harmonics": "off",
    "colormap": "wavetone",
    "analysisProfile": "Normal",
    "cqtResolution": "profile default",
    "analysisSource": "cqt",
    "spectrumThreshold": 2.0,
    "spectrumOpacity": 70,
    "spectrumLayerMode": "both",
    "curveShape": "ease",
    "curveInterpolation": "bezier_pitch",
    "targetAngle": 165.0,
}


# Keep the on-disk key, Web UI setting key, and saved value type together so
# adding a setting cannot update the save path without also updating restore.
PROJECT_SETTING_FIELDS: tuple[tuple[str, str, type], ...] = (
    ("grid_bpm", "bpm", float),
    ("grid_offset_ms", "offsetMs", float),
    ("grid_enabled", "gridEnabled", bool),
    ("metronome_enabled", "metronomeEnabled", bool),
    ("metronome_volume", "metronomeVolume", int),
    ("snap_enabled", "snapEnabled", bool),
    ("snap_div", "snapDiv", int),
    ("preview_octave", "previewOctave", int),
    ("export_octave", "exportOctave", int),
    ("export_semitone", "exportSemitone", int),
    ("note_volume", "previewVolume", int),
    ("note_sound_enabled", "notePreview", bool),
    ("note_instrument", "previewSound", str),
    ("song_volume", "volume", int),
    ("playback_speed", "speed", float),
    ("analysis_profile", "analysisProfile", str),
    ("cqt_resolution", "cqtResolution", str),
    ("analysis_source", "analysisSource", str),
    ("spectrum_threshold", "spectrumThreshold", float),
    ("spectrum_opacity", "spectrumOpacity", int),
    ("spectrum_layer_mode", "spectrumLayerMode", str),
    ("display_mode", "displayMode", str),
    ("cmap", "colormap", str),
    ("contrast", "contrast", int),
    ("gamma", "gamma", int),
    ("enhance", "enhance", bool),
    ("harmonics", "harmonics", str),
    ("curve_shape", "curveShape", str),
    ("curve_interpolation", "curveInterpolation", str),
    ("target_angle", "targetAngle", float),
)

# Older desktop projects used this name before preview_octave was introduced.
PROJECT_SETTING_ALIASES = {"note_octave": "previewOctave"}


class IOMixin:
    def _normalized_project_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        settings = dict(DEFAULT_EDITOR_SETTINGS)
        for project_key, setting_key, _value_type in PROJECT_SETTING_FIELDS:
            if project_key in data and setting_key in settings:
                settings[setting_key] = self._normalize_setting(setting_key, data[project_key])
        canonical_keys_present = {
            setting_key
            for project_key, setting_key, _value_type in PROJECT_SETTING_FIELDS
            if project_key in data
        }
        for project_key, setting_key in PROJECT_SETTING_ALIASES.items():
            # A legacy alias fills a missing setting; it must not override a
            # newer canonical field when both occur in the same project.
            if project_key in data and setting_key in settings and setting_key not in canonical_keys_present:
                settings[setting_key] = self._normalize_setting(setting_key, data[project_key])
        return settings

    def _project_settings(self) -> dict[str, Any]:
        s = self.settings
        saved = {project_key: value_type(s[setting_key]) for project_key, setting_key, value_type in PROJECT_SETTING_FIELDS}
        saved["web_ui"] = True
        # Workspace bounds are document metadata rather than user preferences.
        # Keeping them in the existing settings object preserves project-format
        # compatibility while allowing blank workspaces to round-trip exactly.
        saved["workspace_duration"] = float(self.duration)
        saved["workspace_midi_min"] = int(self.midi_min)
        saved["workspace_midi_max"] = int(self.midi_max)
        return saved

    def _apply_project_settings(self, data: dict[str, Any]) -> None:
        self.settings = self._normalized_project_settings(data)
        self._apply_player_settings()

    def _save_project_path(self, path: str) -> dict[str, Any]:
        if not Path(path).suffix:path+=".adopyhz"
        with self._lock:
            # Keep an unresolved project audio reference until the user relinks
            # or explicitly creates a derived audio-less workspace.
            audio_reference = self.audio_path or self.project_audio_reference
            save_project(path,audio_path=audio_reference,notes=self.notes,settings=self._project_settings());self.project_path=str(Path(path).resolve());self._saved_checkpoint=self._document_checkpoint();self._dirty=False;self._status=f"{Path(path).name} を保存しました";return self._state_dict()

    def save_project_dialog(self) -> dict[str, Any]:
        """Save in place when possible; ask for a path only for new projects."""
        with self._lock:
            path = self.project_path
        if path:
            return self._save_project_path(path)
        return self.save_project_as_dialog()

    def save_project_as_dialog(self) -> dict[str, Any]:
        with self._lock:
            filename = Path(self.project_path).name if self.project_path else "project.adopyhz"
        path=self._dialog(webview.FileDialog.SAVE,file_types=PROJECT_FILE_TYPES,save_filename=filename)
        if not path:return self.get_state()
        return self._save_project_path(path)

    def load_project_dialog(self) -> dict[str, Any]:
        path=self._dialog(webview.FileDialog.OPEN,file_types=PROJECT_FILE_TYPES)
        if not path:return self.get_state()
        audio_path,notes,settings=load_project(path)
        prepared_notes=[n.normalized() for n in notes]
        prepared_settings=self._normalized_project_settings(settings)
        prepared_audio=None
        source_request=self._reserve_source_request()
        if audio_path and Path(audio_path).exists():
            with self._lock:self._busy=True
            try:
                # Respect the project's requested analysis source while keeping
                # project replacement transactional. Supported Direct sources
                # are restored as explicit-analysis pending rather than silently
                # building CQT; unsupported sources alone fall back to CQT.
                prepared_audio=self._prepare_requested_audio_path(
                    audio_path,
                    settings=prepared_settings,
                )
            finally:
                with self._lock:self._busy=False

        with self._lock:
            if source_request != self._source_generation:
                return self._state_dict()
            self.notes=prepared_notes
            self._undo_stack.clear();self._redo_stack.clear()
            self.settings=prepared_settings
            self.project_path=str(Path(path).resolve())
            self.project_audio_reference=str(audio_path) if audio_path else None
            self._dirty=False
            self._status=f"{Path(path).name} を読み込みました"
            if prepared_audio is not None and audio_path:
                decoded,spec,analysis_stats,analysis_kind=prepared_audio
                self._commit_prepared_audio(
                    audio_path,
                    decoded,
                    spec,
                    source_generation=source_request,
                    analysis_stats=analysis_stats,
                    direct_pending=analysis_kind=="direct_pending",
                )
                self._apply_player_settings()
                self._sync_notes_to_player()
                if analysis_kind=="direct_pending":
                    self._status=f"{Path(path).name} と音声を読み込みました（Vorbis Direct解析待ち）"
                elif analysis_kind=="fallback":
                    self._status=f"{Path(path).name} と音声を読み込みました（Vorbis Direct非対応のためCQT）"
                else:
                    self._status=f"{Path(path).name} と音声を読み込みました"
            else:
                self._detach_active_audio()
                note_end=max((n.end for n in self.notes),default=0.0)
                saved_duration=settings.get("workspace_duration")
                saved_midi_min=settings.get("workspace_midi_min")
                saved_midi_max=settings.get("workspace_midi_max")
                if saved_duration is None:
                    self.duration=max(60.0,note_end)
                else:
                    self.duration=max(1.0,float(saved_duration),note_end)
                if saved_midi_min is None or saved_midi_max is None:
                    self.midi_min=12;self.midi_max=120
                else:
                    self.midi_min=max(0,min(127,int(saved_midi_min)))
                    self.midi_max=max(0,min(127,int(saved_midi_max)))
                    if self.midi_max <= self.midi_min:
                        self.midi_max=min(127,self.midi_min+1)
                        if self.midi_max <= self.midi_min:
                            self.midi_min=max(0,self.midi_max-1)
                self.pitch_step=1.0;self.player.clear_audio();self._apply_player_settings();self._sync_notes_to_player()
                if audio_path:
                    self._status=f"{Path(path).name} の音源が見つかりません。ファイル → プロジェクト音源を再指定… から選び直せます"
                else:
                    self._status=f"{Path(path).name} のノートを読み込みました"
            self._saved_checkpoint=self._document_checkpoint();self._dirty=False
        return self.get_state()

    def relink_project_audio_dialog(self) -> dict[str, Any]:
        with self._lock:
            if not self.project_path:
                self._status="先にプロジェクトを読み込んでください"
                return self._state_dict()

        path=self._dialog(webview.FileDialog.OPEN,file_types=AUDIO_FILE_TYPES)
        if not path:return self.get_state()
        source=str(Path(path).resolve())

        with self._lock:self._busy=True
        try:
            self._load_audio_path(source,analyze=True)
            with self._lock:
                # Rebuild preview notes because the audio sample rate may have changed.
                self._sync_notes_to_player();self._dirty=True
                suffix = (
                    "（Vorbis Direct解析待ち）"
                    if bool(self.analysis_stats.get("pending"))
                    else ""
                )
                self._status=f"プロジェクト音源を {Path(source).name} に再指定しました{suffix}"
        finally:
            with self._lock:self._busy=False
        return self.get_state()

    def _shifted_export_notes(self) -> list[Note]:
        semitones=int(self.settings["exportOctave"])*12+int(self.settings["exportSemitone"]);return[n.with_pitch_offset(semitones) for n in self.notes]

    def import_midi_dialog(self) -> dict[str, Any]:
        path=self._dialog(webview.FileDialog.OPEN,file_types=MIDI_FILE_TYPES)
        if not path:return self.get_state()
        result=import_midi(path);imported=result.notes
        with self._lock:
            self._push_undo();self.notes.extend(imported);self.notes.sort(key=lambda n:(n.start,n.midi,n.end))
            if imported:self.duration=max(self.duration,max(n.end for n in imported))
            self._dirty=True;self._sync_notes_to_player();self._status=f"MIDIから{len(imported)}個のノートを読み込みました";return self._state_dict()

    def export_midi_dialog(self) -> dict[str, Any]:
        path=self._dialog(webview.FileDialog.SAVE,file_types=MIDI_FILE_TYPES,save_filename="notes.mid")
        if not path:return {"ok":False,"status":"キャンセルしました"}
        if Path(path).suffix.lower() not in {".mid",".midi"}:path+=".mid"
        with self._lock:notes=self._shifted_export_notes();bpm=float(self.settings["bpm"])
        export_midi(notes,path,bpm=bpm)
        with self._lock:self._status=f"{Path(path).name} をMIDI出力しました"
        return {"ok":True,"path":str(path),"status":self._status}

    def export_adofai_dialog(self) -> dict[str, Any]:
        path=self._dialog(webview.FileDialog.SAVE,file_types=ADOF_FILE_TYPES,save_filename="level.adofai")
        if not path:return {"ok":False,"status":"キャンセルしました"}
        if Path(path).suffix.lower()!=".adofai":path+=".adofai"
        with self._lock:notes=self._shifted_export_notes();song_filename=Path(self.audio_path).name if self.audio_path else None;offset_ms=float(self.settings["offsetMs"])
        level,stats=build_adofai_level(notes,method="rabbit_zip",song_filename=song_filename,song_offset_ms=offset_ms)
        Path(path).write_text(json.dumps(level,ensure_ascii=False,indent=2),encoding="utf-8")
        with self._lock:self._status=f"{Path(path).name} をADOFAI出力しました（{stats.get('tiles_total',0)}タイル）"
        return {"ok":True,"path":str(path),"stats":stats,"status":self._status}
