from __future__ import annotations

from pathlib import Path
import threading
import numpy as np


def midi_to_hz(note: float) -> float:
    return 440.0 * (2.0 ** ((note - 69.0) / 12.0))


def decode_audio_file(path: str | Path, *, sr: int = 44100) -> tuple[np.ndarray, int]:
    """
    Decode audio without touching AudioPlayer state.

    This is intentionally separated from AudioPlayer.load so decoding can run
    in a background thread without freezing the Qt UI.
    """
    import librosa

    y, actual_sr = librosa.load(str(path), sr=sr, mono=True)
    y = np.asarray(y, dtype=np.float32)
    if y.ndim == 1:
        y = y[:, None]
    return y, int(actual_sr)


class AudioPlayer:
    """
    QMediaPlayerを使わない簡易プレイヤー。
    sounddeviceが無い/失敗した場合は利用不可になる。
    """
    def __init__(self) -> None:
        self.available = False
        self.error: str | None = None
        self.audio: np.ndarray | None = None
        self.sr = 44100
        self.pos = 0
        self.stream = None
        self.lock = threading.RLock()
        self.playing = False

        # Main audio
        self.volume = 0.85
        self.playback_speed = 1.0
        self._pos_float = 0.0

        # Metronome
        self.metronome_enabled = False
        self.metronome_bpm = 175.0
        self.metronome_offset_sec = 0.0
        self.metronome_volume = 0.35
        self._click_wave_cache: dict[tuple[int, float], np.ndarray] = {}

        # Note preview synth
        self.note_sound_enabled = True
        self.note_volume = 0.20
        self.note_octave_shift = 0
        self.preview_notes: list[tuple[int, int, float]] = []  # start_sample, end_sample, midi

        try:
            import sounddevice as sd  # noqa
            self.sd = sd
            self.available = True
        except Exception as e:
            self.sd = None
            self.error = repr(e)

    def load(self, path: str | Path, *, sr: int = 44100) -> None:
        if not self.available:
            return
        y, actual_sr = decode_audio_file(path, sr=sr)
        self.set_audio(y, actual_sr)

    def set_audio(self, audio: np.ndarray, sr: int) -> None:
        """
        Set already-decoded audio. Safe to call from the Qt/main thread after a
        background decoder worker finishes.
        """
        y = np.asarray(audio, dtype=np.float32)
        if y.ndim == 1:
            y = y[:, None]
        with self.lock:
            self.stop()
            self.audio = y
            self.sr = int(sr)
            self.pos = 0
            self._pos_float = 0.0
            # srが確定したので、ノートサンプル位置は再設定が必要。
            # main側の sync_notes_to_player が後で呼ばれる。

    def clear_audio(self) -> None:
        """
        Unload the currently decoded audio and close the stream.
        Preview/metronome settings are kept, but playback becomes silent because
        there is no main audio buffer/stream.
        """
        with self.lock:
            self.stop()
            self.audio = None
            self.pos = 0
            self._pos_float = 0.0
            self.preview_notes = []

    @property
    def duration(self) -> float:
        if self.audio is None or self.sr <= 0:
            return 0.0
        return float(len(self.audio) / self.sr)

    @property
    def time(self) -> float:
        with self.lock:
            return float(self.pos / self.sr) if self.sr else 0.0

    def set_volume(self, volume: float) -> None:
        with self.lock:
            self.volume = max(0.0, min(1.5, float(volume)))

    def set_playback_speed(self, speed: float) -> None:
        with self.lock:
            self.playback_speed = max(0.10, min(4.0, float(speed)))
            self._pos_float = float(self.pos)

    def set_note_sound(self, *, enabled: bool, volume: float, octave_shift: int = 0) -> None:
        with self.lock:
            self.note_sound_enabled = bool(enabled)
            self.note_volume = max(0.0, min(1.5, float(volume)))
            self.note_octave_shift = int(octave_shift)

    def set_preview_notes(self, notes) -> None:
        """
        notes: objects with start, end, midi or tuples (start, end, midi)
        Curve notes are sampled into short fixed-pitch preview notes.
        """
        prepared: list[tuple[int, int, float]] = []
        sr = max(1, int(self.sr))

        for n in notes:
            try:
                segments = n.sample_fixed_segments(max_seconds=0.020, max_pitch_step=0.20)
            except AttributeError:
                segments = [n]

            for seg in segments:
                try:
                    start = float(seg.start)
                    end = float(seg.end)
                    midi = float(seg.midi)
                except AttributeError:
                    start, end, midi = float(seg[0]), float(seg[1]), float(seg[2])

                if end <= start:
                    continue
                prepared.append((max(0, int(start * sr)), max(1, int(end * sr)), float(midi)))

        prepared.sort(key=lambda x: x[0])
        with self.lock:
            self.preview_notes = prepared

    def set_metronome(self, *, enabled: bool, bpm: float, offset_sec: float, volume: float = 0.35) -> None:
        with self.lock:
            self.metronome_enabled = bool(enabled)
            self.metronome_bpm = max(1e-6, float(bpm))
            self.metronome_offset_sec = float(offset_sec)
            self.metronome_volume = max(0.0, min(1.5, float(volume)))

    def seek(self, seconds: float) -> None:
        with self.lock:
            if self.audio is None:
                self.pos = 0
                self._pos_float = 0.0
            else:
                self.pos = max(0, min(len(self.audio) - 1, int(seconds * self.sr)))
                self._pos_float = float(self.pos)

    def _click_wave(self, length: int = 1200, freq: float = 1800.0) -> np.ndarray:
        key = (int(length), float(freq))
        cached = self._click_wave_cache.get(key)
        if cached is not None:
            return cached
        n = np.arange(length, dtype=np.float32)
        env = np.exp(-n / max(1.0, length * 0.18)).astype(np.float32)
        wave = (np.sin(2.0 * np.pi * freq * n / max(1, self.sr)) * env).astype(np.float32)
        self._click_wave_cache[key] = wave[:, None]
        return self._click_wave_cache[key]

    def _mix_metronome(self, outdata, start_sample: int, frames: int) -> None:
        if not self.metronome_enabled or self.metronome_bpm <= 0 or self.metronome_volume <= 0:
            return

        beat_samples = self.sr * 60.0 / self.metronome_bpm
        if beat_samples <= 1:
            return

        offset_sample = self.metronome_offset_sec * self.sr
        click = self._click_wave(max(80, int(self.sr * 0.025)))
        click_len = len(click)

        block_start = start_sample
        block_end = start_sample + frames

        k0 = int(np.floor((block_start - offset_sample - click_len) / beat_samples))
        k1 = int(np.ceil((block_end - offset_sample) / beat_samples))

        for k in range(k0, k1 + 1):
            beat = int(round(offset_sample + k * beat_samples))
            if beat + click_len < block_start or beat >= block_end:
                continue
            out_s = max(0, beat - block_start)
            clk_s = max(0, block_start - beat)
            count = min(frames - out_s, click_len - clk_s)
            if count > 0:
                outdata[out_s:out_s + count, :] += click[clk_s:clk_s + count, :] * self.metronome_volume

    def _mix_preview_notes(self, outdata, start_sample: int, frames: int) -> None:
        if not self.note_sound_enabled or self.note_volume <= 0 or not self.preview_notes:
            return

        block_start = start_sample
        block_end = start_sample + frames
        sr = max(1, self.sr)

        # コールバックごとの短いブロックなので単純走査で十分。
        # ノート数がかなり多い場合でも、編集用途なら現実的。
        octave_shift = int(self.note_octave_shift)

        for ns, ne, midi in self.preview_notes:
            if ne <= block_start:
                continue
            if ns >= block_end:
                break

            out_s = max(0, ns - block_start)
            out_e = min(frames, ne - block_start)
            if out_e <= out_s:
                continue

            freq = midi_to_hz(float(midi) + octave_shift * 12)
            sample_index = np.arange(block_start + out_s, block_start + out_e, dtype=np.float32)
            # 絶対サンプル時刻から生成するのでブロック境界で位相が飛びにくい
            wave = np.sin(2.0 * np.pi * freq * sample_index / sr).astype(np.float32)

            # ノートの頭/尻だけ軽くフェード
            local = sample_index - ns
            note_len = max(1, ne - ns)
            fade = min(int(sr * 0.006), max(1, note_len // 4))
            env = np.ones_like(wave)
            env = np.minimum(env, np.clip(local / fade, 0.0, 1.0))
            env = np.minimum(env, np.clip((ne - sample_index) / fade, 0.0, 1.0))

            outdata[out_s:out_e, 0] += wave * env * self.note_volume

    def play(self) -> None:
        if not self.available or self.audio is None:
            return
        with self.lock:
            if self.stream is None:
                self.stream = self.sd.OutputStream(
                    samplerate=self.sr,
                    channels=1,
                    dtype="float32",
                    callback=self._callback,
                    blocksize=1024,
                )
            self.playing = True
            self.stream.start()

    def pause(self) -> None:
        with self.lock:
            self.playing = False
            if self.stream is not None:
                try:
                    self.stream.stop()
                except Exception:
                    pass

    def stop(self) -> None:
        with self.lock:
            self.playing = False
            self.pos = 0
            self._pos_float = 0.0
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None

    def toggle(self) -> None:
        if self.playing:
            self.pause()
        else:
            self.play()

    def _read_audio_block_speed(self, start_pos: float, frames: int, speed: float):
        assert self.audio is not None
        n = len(self.audio)
        if n <= 0:
            return np.zeros((0, 1), dtype=np.float32)

        if abs(speed - 1.0) < 1e-6:
            s = int(start_pos)
            e = min(n, s + frames)
            return self.audio[s:e]

        positions = start_pos + np.arange(frames, dtype=np.float32) * float(speed)
        valid = positions < (n - 1)
        if not np.any(valid):
            return np.zeros((0, 1), dtype=np.float32)

        positions = positions[valid]
        i0 = np.floor(positions).astype(np.int64)
        frac = (positions - i0).astype(np.float32)[:, None]
        i1 = np.minimum(i0 + 1, n - 1)
        return (self.audio[i0] * (1.0 - frac) + self.audio[i1] * frac).astype(np.float32, copy=False)

    def _callback(self, outdata, frames, time, status) -> None:
        with self.lock:
            if self.audio is None or not self.playing:
                outdata.fill(0)
                return

            speed = max(0.10, min(4.0, float(getattr(self, "playback_speed", 1.0))))
            start_pos_float = float(getattr(self, "_pos_float", float(self.pos)))
            start_pos = int(start_pos_float)
            chunk = self._read_audio_block_speed(start_pos_float, frames, speed)

            outdata.fill(0)
            if len(chunk) > 0:
                outdata[:len(chunk), :] = chunk * self.volume

            self._mix_preview_notes(outdata, start_pos, frames)
            self._mix_metronome(outdata, start_pos, frames)
            np.clip(outdata, -1.0, 1.0, out=outdata)

            if len(chunk) < frames:
                self.pos = len(self.audio)
                self._pos_float = float(self.pos)
                self.playing = False
                raise self.sd.CallbackStop

            self._pos_float = start_pos_float + frames * speed
            self.pos = min(len(self.audio) - 1, int(self._pos_float))
