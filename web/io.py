from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import webview
from mido import MidiFile, merge_tracks, tick2second

from exporters.adofai import build_adofai_level
from exporters.midi import export_midi
from core.note_model import Note
from core.project_io import load_project, save_project

AUDIO_FILE_TYPES = ("音声ファイル (*.wav;*.mp3;*.ogg;*.flac;*.m4a;*.aac)", "すべてのファイル (*.*)")
PROJECT_FILE_TYPES = ("AdopyHzEditorプロジェクト (*.adopyhz;*.ahe.json)", "JSON (*.json)", "すべてのファイル (*.*)")
MIDI_FILE_TYPES = ("MIDIファイル (*.mid;*.midi)", "すべてのファイル (*.*)")
ADOF_FILE_TYPES = ("ADOFAI譜面 (*.adofai)", "すべてのファイル (*.*)")


class IOMixin:
    def _project_settings(self) -> dict[str, Any]:
        s = self.settings
        return {
            "grid_bpm": float(s["bpm"]), "grid_offset_ms": float(s["offsetMs"]), "grid_enabled": bool(s["gridEnabled"]),
            "metronome_enabled": bool(s["metronomeEnabled"]), "metronome_volume": int(s["metronomeVolume"]), "snap_enabled": bool(s["snapEnabled"]),
            "snap_div": int(s["snapDiv"]), "preview_octave": int(s["previewOctave"]), "export_octave": int(s["exportOctave"]),
            "export_semitone": int(s["exportSemitone"]), "note_volume": int(s["previewVolume"]), "note_sound_enabled": bool(s["notePreview"]),
            "note_instrument": str(s["previewSound"]), "song_volume": int(s["volume"]), "playback_speed": float(s["speed"]),
            "analysis_profile": str(s["analysisProfile"]), "cqt_resolution": str(s["cqtResolution"]), "display_mode": str(s["displayMode"]),
            "cmap": str(s["colormap"]), "curve_shape": str(s["curveShape"]), "curve_interpolation": str(s["curveInterpolation"]), "web_ui": True,
        }

    def _apply_project_settings(self, data: dict[str, Any]) -> None:
        aliases = {
            "grid_bpm":"bpm","grid_offset_ms":"offsetMs","grid_enabled":"gridEnabled","metronome_enabled":"metronomeEnabled","metronome_volume":"metronomeVolume",
            "snap_enabled":"snapEnabled","snap_div":"snapDiv","preview_octave":"previewOctave","note_octave":"previewOctave","export_octave":"exportOctave",
            "export_semitone":"exportSemitone","note_volume":"previewVolume","note_sound_enabled":"notePreview","note_instrument":"previewSound","song_volume":"volume",
            "playback_speed":"speed","analysis_profile":"analysisProfile","cqt_resolution":"cqtResolution","display_mode":"displayMode","cmap":"colormap",
            "curve_shape":"curveShape","curve_interpolation":"curveInterpolation",
        }
        for source,target in aliases.items():
            if source in data and target in self.settings: self.settings[target]=self._normalize_setting(target,data[source])
        self._apply_player_settings()

    def save_project_dialog(self) -> dict[str, Any]:
        path=self._dialog(webview.FileDialog.SAVE,file_types=PROJECT_FILE_TYPES,save_filename="project.adopyhz")
        if not path:return self.get_state()
        if not Path(path).suffix:path+=".adopyhz"
        with self._lock:
            save_project(path,audio_path=self.audio_path,notes=self.notes,settings=self._project_settings());self.project_path=str(Path(path).resolve());self._dirty=False;self._status=f"{Path(path).name} を保存しました";return self._state_dict()

    def load_project_dialog(self) -> dict[str, Any]:
        path=self._dialog(webview.FileDialog.OPEN,file_types=PROJECT_FILE_TYPES)
        if not path:return self.get_state()
        audio_path,notes,settings=load_project(path)
        with self._lock:
            self.notes=[n.normalized() for n in notes];self._undo_stack.clear();self._redo_stack.clear();self._apply_project_settings(settings);self.project_path=str(Path(path).resolve());self._dirty=False;self._status=f"{Path(path).name} を読み込みました"
        if audio_path and Path(audio_path).exists():
            with self._lock:self._busy=True
            try:self._load_audio_path(audio_path,analyze=True)
            finally:
                with self._lock:self._busy=False
            with self._lock:
                # Audio loading resets the player's sample-rate-dependent state.
                # Rebuild preview notes afterwards so project notes sound immediately.
                self._sync_notes_to_player();self._status=f"{Path(path).name} と音声を読み込みました"
        else:
            with self._lock:
                self.audio_path=None;self.spectrogram=None;self.duration=max(60.0,max((n.end for n in self.notes),default=0.0));self.midi_min=12;self.midi_max=120;self.pitch_step=1.0;self.player.clear_audio();self._sync_notes_to_player()
                if audio_path:
                    self._status=f"{Path(path).name} の音源が見つかりません。ファイル → プロジェクト音源を再指定… から選び直せます"
                else:
                    self._status=f"{Path(path).name} のノートを読み込みました"
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
                self._sync_notes_to_player();self._dirty=True;self._status=f"プロジェクト音源を {Path(source).name} に再指定しました"
        finally:
            with self._lock:self._busy=False
        return self.get_state()

    def _shifted_export_notes(self) -> list[Note]:
        semitones=int(self.settings["exportOctave"])*12+int(self.settings["exportSemitone"]);return[n.with_pitch_offset(semitones) for n in self.notes]

    def import_midi_dialog(self) -> dict[str, Any]:
        path=self._dialog(webview.FileDialog.OPEN,file_types=MIDI_FILE_TYPES)
        if not path:return self.get_state()
        midi=MidiFile(path);tempo=500000;now=0.0;active:dict[tuple[int,int],list[tuple[float,int]]]={};imported:list[Note]=[]
        for msg in merge_tracks(midi.tracks):
            now+=tick2second(msg.time,midi.ticks_per_beat,tempo)
            if msg.type=="set_tempo":tempo=int(msg.tempo);continue
            if msg.type=="note_on" and int(msg.velocity)>0:
                key=(int(getattr(msg,"channel",0)),int(msg.note));active.setdefault(key,[]).append((now,int(msg.velocity)))
            elif msg.type in {"note_off","note_on"}:
                key=(int(getattr(msg,"channel",0)),int(msg.note));stack=active.get(key)
                if stack:
                    start,velocity=stack.pop(0)
                    if now>start:imported.append(Note(start,now,float(msg.note),velocity).normalized())
        imported.sort(key=lambda n:(n.start,n.midi,n.end))
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
