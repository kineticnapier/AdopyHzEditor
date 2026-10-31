from __future__ import annotations

from pathlib import Path
from bisect import bisect_right
from dataclasses import dataclass
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


@dataclass(frozen=True)
class PreviewSegment:
    start: int
    end: int
    midi: float
    phase: float = 0.0
    fade_in: bool = True
    fade_out: bool = True

    def __iter__(self):
        # Preserve the historical three-value tuple interface used by callers.
        yield self.start
        yield self.end
        yield self.midi


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
        self._stream_control_lock = threading.Lock()
        self.playing = False

        # Main audio
        self.volume = 0.85
        self.playback_speed = 1.0
        self._pos_float = 0.0
        self.virtual_duration_samples = 0  # Used when no main audio is loaded.

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
        self.note_instrument = "sine"
        self.note_sample: np.ndarray | None = None
        self._note_sample_fft_cache: dict[int, np.ndarray] = {}
        self.preview_notes: list[PreviewSegment | tuple[int, int, float]] = []
        self._preview_ends: list[int] = []
        self._preview_hit_samples = np.empty(0, dtype=np.float64)

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
        with self._stream_control_lock:
            self._stop_stream_controlled(reset_position=True, close=True)
            with self.lock:
                self.audio = y
                self.sr = int(sr)
                self.pos = 0
                self._pos_float = 0.0
                self.virtual_duration_samples = len(self.audio)
                # srが確定したので、ノートサンプル位置は再設定が必要。
                # main側の sync_notes_to_player が後で呼ばれる。

    def clear_audio(self) -> None:
        """
        Unload the currently decoded audio and close the stream.
        Preview/metronome settings are kept, but playback becomes silent because
        there is no main audio buffer/stream.
        """
        with self._stream_control_lock:
            self._stop_stream_controlled(reset_position=True, close=True)
            with self.lock:
                self.audio = None
                self.pos = 0
                self._pos_float = 0.0
                # Keep preview_notes; MainWindow.sync_notes_to_player() will refresh
                # them after project/workspace changes. This allows note-only
                # playback in a blank workspace.

    @property
    def duration(self) -> float:
        if self.sr <= 0:
            return 0.0
        audio_samples = len(self.audio) if self.audio is not None else 0
        return float(max(audio_samples, max(0, int(self.virtual_duration_samples))) / self.sr)

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

    def _normalize_note_instrument(self, instrument: str | None) -> str:
        key = (instrument or "sine").lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "sin": "sine",
            "tone": "sine",
            "piano_like": "piano",
            "soft_piano": "piano",
            "pluck": "piano",
            "organ_like": "organ",
            "square_wave": "square",
            "triangle_wave": "triangle",
            "kick": "adofai_kick",
            "adofai": "adofai_kick",
            "adofai_kick": "adofai_kick",
        }
        key = aliases.get(key, key)
        if key not in {"sine", "piano", "organ", "square", "triangle", "adofai_kick"}:
            key = "sine"
        return key

    def set_note_sound(self, *, enabled: bool, volume: float, octave_shift: int = 0, instrument: str | None = None) -> None:
        with self.lock:
            self.note_sound_enabled = bool(enabled)
            self.note_volume = max(0.0, min(1.5, float(volume)))
            self.note_octave_shift = int(octave_shift)
            if instrument is not None:
                self.note_instrument = self._normalize_note_instrument(str(instrument))

    def set_note_sample(self, audio: np.ndarray | None) -> None:
        sample: np.ndarray | None
        if audio is None:
            sample = None
        else:
            data = np.asarray(audio, dtype=np.float32)
            if data.ndim == 2:
                data = np.mean(data, axis=1, dtype=np.float32)
            elif data.ndim != 1:
                data = np.ravel(data).astype(np.float32, copy=False)
            sample = np.ascontiguousarray(data, dtype=np.float32)
            if len(sample) == 0:
                sample = None
        with self.lock:
            self.note_sample = sample
            self._note_sample_fft_cache.clear()

    def set_preview_notes(self, notes) -> None:
        """
        notes: objects with start, end, midi or tuples (start, end, midi)
        Curve notes are sampled into short fixed-pitch preview notes.
        """
        prepared: list[PreviewSegment] = []
        hit_chunks: list[np.ndarray] = []
        sr = max(1, int(self.sr))
        two_pi = 2.0 * np.pi

        for n in notes:
            try:
                segments = n.sample_fixed_segments(max_seconds=0.020, max_pitch_step=0.20)
            except AttributeError:
                segments = [n]

            phase = 0.0
            for segment_index, seg in enumerate(segments):
                try:
                    start = float(seg.start)
                    end = float(seg.end)
                    midi = float(seg.midi)
                except AttributeError:
                    start, end, midi = float(seg[0]), float(seg[1]), float(seg[2])

                if end <= start:
                    continue
                start_sample = max(0, int(start * sr))
                end_sample = max(start_sample + 1, int(end * sr))
                prepared.append(PreviewSegment(
                    start_sample,
                    end_sample,
                    float(midi),
                    phase,
                    segment_index == 0,
                    segment_index == len(segments) - 1,
                ))

                freq = midi_to_hz(float(midi))
                phase_end = phase + two_pi * freq * (end_sample - start_sample) / sr
                first_cycle = int(np.ceil((phase - 1e-12) / two_pi))
                last_cycle = int(np.floor((phase_end - 1e-12) / two_pi))
                if last_cycle >= first_cycle and freq > 0:
                    cycles = np.arange(first_cycle, last_cycle + 1, dtype=np.float64)
                    hits = (
                        float(start_sample)
                        + (cycles * two_pi - phase) * sr / (two_pi * freq)
                    )
                    valid = (hits >= start_sample - 1e-7) & (hits < end_sample - 1e-7)
                    if np.any(valid):
                        hit_chunks.append(hits[valid])
                phase = phase_end

        prepared.sort(key=lambda x: x.start)
        if hit_chunks:
            hit_samples = np.concatenate(hit_chunks)
            hit_samples.sort()
        else:
            hit_samples = np.empty(0, dtype=np.float64)

        with self.lock:
            self.preview_notes = prepared
            self._preview_hit_samples = hit_samples
            max_end = 0
            self._preview_ends = []
            for segment in prepared:
                max_end = max(max_end, segment.end)
                self._preview_ends.append(max_end)

    def set_virtual_duration(self, seconds: float) -> None:
        """
        Set the playback length used when no decoded audio buffer is loaded.
        Note preview and metronome can still play over this silent timeline.
        """
        samples = max(0, int(float(seconds) * max(1, int(self.sr))))
        with self.lock:
            self.virtual_duration_samples = samples
            if self.audio is None:
                self.pos = max(0, min(self.pos, max(0, samples - 1)))
                self._pos_float = max(0.0, min(float(self._pos_float), float(max(0, samples - 1))))

    def set_metronome(self, *, enabled: bool, bpm: float, offset_sec: float, volume: float = 0.35) -> None:
        with self.lock:
            self.metronome_enabled = bool(enabled)
            self.metronome_bpm = max(1e-6, float(bpm))
            self.metronome_offset_sec = float(offset_sec)
            self.metronome_volume = max(0.0, min(1.5, float(volume)))

    def seek(self, seconds: float) -> None:
        with self.lock:
            audio_samples = len(self.audio) if self.audio is not None else 0
            n = max(1, audio_samples, int(self.virtual_duration_samples))
            self.pos = max(0, min(n - 1, int(seconds * self.sr)))
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

    def _mix_metronome(self, outdata, source_positions: np.ndarray) -> None:
        if not self.metronome_enabled or self.metronome_bpm <= 0 or self.metronome_volume <= 0:
            return
        if len(source_positions) == 0:
            return

        beat_samples = self.sr * 60.0 / self.metronome_bpm
        if beat_samples <= 1:
            return

        offset_sample = self.metronome_offset_sec * self.sr
        click = self._click_wave(max(80, int(self.sr * 0.025)))
        click_len = len(click)

        block_start = float(source_positions[0])
        block_end = float(source_positions[-1])

        k0 = int(np.floor((block_start - offset_sample - click_len) / beat_samples))
        k1 = int(np.ceil((block_end - offset_sample) / beat_samples))

        for k in range(k0, k1 + 1):
            beat = int(round(offset_sample + k * beat_samples))
            if beat + click_len < block_start or beat > block_end:
                continue
            out_s = int(np.searchsorted(source_positions, beat, side="left"))
            out_e = int(np.searchsorted(source_positions, beat + click_len, side="left"))
            if out_e <= out_s:
                continue
            click_positions = source_positions[out_s:out_e] - beat
            i0 = np.floor(click_positions).astype(np.int64)
            frac = (click_positions - i0).astype(np.float32)[:, None]
            i1 = np.minimum(i0 + 1, click_len - 1)
            sampled = click[i0] * (1.0 - frac) + click[i1] * frac
            outdata[out_s:out_e, :] += sampled * self.metronome_volume

    def _note_sample_fft(self, fft_size: int) -> np.ndarray:
        cached = self._note_sample_fft_cache.get(int(fft_size))
        if cached is not None:
            return cached
        sample = self.note_sample
        if sample is None:
            return np.empty(0, dtype=np.complex128)
        spectrum = np.fft.rfft(sample, n=int(fft_size))
        self._note_sample_fft_cache[int(fft_size)] = spectrum
        # Playback normally needs only one or two FFT sizes. Bound stale sizes
        # after speed/sample changes so the audio callback cannot grow the cache forever.
        if len(self._note_sample_fft_cache) > 4:
            for key in list(self._note_sample_fft_cache)[:-4]:
                self._note_sample_fft_cache.pop(key, None)
        return spectrum

    def _mix_preview_sample(self, outdata, source_positions: np.ndarray) -> bool:
        sample = self.note_sample
        hits = self._preview_hit_samples
        if sample is None or len(sample) == 0:
            return False
        if len(source_positions) == 0 or len(hits) == 0:
            return True

        sample_len = len(sample)
        block_start = float(source_positions[0])
        block_end = float(source_positions[-1])

        # Render the kick train in source-sample space, then sample that result at
        # source_positions. This keeps playback-speed handling identical while
        # replacing O(hit_count * kick_length) overlap-add with one FFT convolution.
        render_start = int(np.floor(block_start)) - sample_len - 2
        render_end = int(np.ceil(block_end)) + 3
        left = int(np.searchsorted(hits, render_start, side="left"))
        right = int(np.searchsorted(hits, render_end, side="right"))
        if right <= left:
            return True

        impulse_len = max(1, render_end - render_start)
        impulses = np.zeros(impulse_len, dtype=np.float32)
        local_hits = hits[left:right] - float(render_start)
        i0 = np.floor(local_hits).astype(np.int64)
        frac = (local_hits - i0).astype(np.float32)

        valid0 = (i0 >= 0) & (i0 < impulse_len)
        if np.any(valid0):
            np.add.at(impulses, i0[valid0], 1.0 - frac[valid0])
        i1 = i0 + 1
        valid1 = (i1 >= 0) & (i1 < impulse_len) & (frac > 1e-12)
        if np.any(valid1):
            np.add.at(impulses, i1[valid1], frac[valid1])

        convolution_len = impulse_len + sample_len - 1
        fft_size = 1 << max(0, convolution_len - 1).bit_length()
        kick_fft = self._note_sample_fft(fft_size)
        train_fft = np.fft.rfft(impulses, n=fft_size)
        rendered = np.fft.irfft(train_fft * kick_fft, n=fft_size)[:convolution_len]

        local_positions = source_positions - float(render_start)
        base = np.floor(local_positions).astype(np.int64)
        valid = (base >= 0) & (base < convolution_len)
        if not np.any(valid):
            return True

        base_clipped = np.clip(base, 0, convolution_len - 1)
        next_index = np.minimum(base_clipped + 1, convolution_len - 1)
        alpha = (local_positions - base).astype(np.float64)
        sampled = (
            rendered[base_clipped] * (1.0 - alpha)
            + rendered[next_index] * alpha
        ).astype(np.float32, copy=False)
        if not np.all(valid):
            sampled = sampled * valid.astype(np.float32)
        outdata[:, 0] += sampled * self.note_volume
        return True

    def _mix_preview_notes(self, outdata, source_positions: np.ndarray) -> None:
        if not self.note_sound_enabled or self.note_volume <= 0 or not self.preview_notes:
            return
        if len(source_positions) == 0:
            return

        if str(getattr(self, "note_instrument", "sine")) == "adofai_kick":
            if self._mix_preview_sample(outdata, source_positions):
                return

        block_start = float(source_positions[0])
        block_end = float(source_positions[-1])
        sr = max(1, self.sr)

        # コールバックごとの短いブロックなので単純走査で十分。
        # ノート数がかなり多い場合でも、編集用途なら現実的。
        octave_shift = int(self.note_octave_shift)

        preview_notes = self.preview_notes
        if len(self._preview_ends) == len(preview_notes):
            first_active = bisect_right(self._preview_ends, block_start)
        else:
            first_active = 0
        for index in range(first_active, len(preview_notes)):
            segment = preview_notes[index]
            ns, ne, midi = segment
            if ne <= block_start:
                continue
            if ns > block_end:
                break

            out_s = int(np.searchsorted(source_positions, ns, side="left"))
            out_e = int(np.searchsorted(source_positions, ne, side="left"))
            if out_e <= out_s:
                continue

            freq = midi_to_hz(float(midi) + octave_shift * 12)
            sample_index = source_positions[out_s:out_e]
            # 絶対サンプル時刻から生成するのでブロック境界で位相が飛びにくい
            base_phase = getattr(segment, "phase", None)
            if base_phase is None:
                phase_offset = 2.0 * np.pi * freq * ns / sr
            else:
                # PreviewSegment.phase is accumulated at the stored/base MIDI
                # pitch. Octave transposition scales both frequency and the
                # accumulated phase by the same power of two, including when
                # the setting changes after the segments were prepared.
                phase_offset = float(base_phase) * (2.0 ** octave_shift)
            phase = phase_offset + 2.0 * np.pi * freq * (sample_index - ns) / sr
            local = sample_index - ns
            local_sec = local / float(sr)
            instrument = str(getattr(self, "note_instrument", "sine"))

            if instrument == "piano":
                # Lightweight piano-ish preview: bright attack + quick decay.
                wave = (
                    1.00 * np.sin(phase)
                    + 0.45 * np.sin(2.0 * phase)
                    + 0.22 * np.sin(3.0 * phase)
                    + 0.10 * np.sin(4.0 * phase)
                ).astype(np.float32) / 1.55
                decay_rate = float(np.clip(freq / 260.0, 1.4, 6.0))
                instrument_env = np.exp(-local_sec * decay_rate).astype(np.float32)
            elif instrument == "organ":
                wave = (
                    1.00 * np.sin(phase)
                    + 0.35 * np.sin(2.0 * phase)
                    + 0.18 * np.sin(3.0 * phase)
                ).astype(np.float32) / 1.35
                instrument_env = np.ones_like(wave, dtype=np.float32)
            elif instrument == "square":
                wave = np.sign(np.sin(phase)).astype(np.float32) * 0.65
                instrument_env = np.ones_like(wave, dtype=np.float32)
            elif instrument == "triangle":
                # 2/pi * asin(sin(x)) gives a band-limited-enough soft triangle for preview.
                wave = (2.0 / np.pi * np.arcsin(np.sin(phase))).astype(np.float32)
                instrument_env = np.ones_like(wave, dtype=np.float32)
            else:
                wave = np.sin(phase).astype(np.float32)
                instrument_env = np.ones_like(wave, dtype=np.float32)

            # ノートの頭/尻だけ軽くフェード
            note_len = max(1, ne - ns)
            fade = min(int(sr * 0.006), max(1, note_len // 4))
            env = np.ones_like(wave)
            if bool(getattr(segment, "fade_in", True)):
                env = np.minimum(env, np.clip(local / fade, 0.0, 1.0))
            if bool(getattr(segment, "fade_out", True)):
                env = np.minimum(env, np.clip((ne - sample_index) / fade, 0.0, 1.0))
            env *= instrument_env

            outdata[out_s:out_e, 0] += wave * env * self.note_volume

    def play(self) -> None:
        if not self.available:
            return
        with self._stream_control_lock:
            with self.lock:
                has_audio = self.audio is not None and len(self.audio) > 0
                has_virtual = int(self.virtual_duration_samples) > 0
                if not has_audio and not has_virtual:
                    return
                playback_end = max(len(self.audio) if has_audio else 0, int(self.virtual_duration_samples))
                if self.pos >= max(0, playback_end - 1):
                    self.pos = 0
                    self._pos_float = 0.0
                stream = self.stream
                sample_rate = self.sr
            if stream is None:
                stream = self.sd.OutputStream(
                    samplerate=sample_rate,
                    channels=1,
                    dtype="float32",
                    callback=self._callback,
                    blocksize=1024,
                )
                with self.lock:
                    self.stream = stream
            with self.lock:
                self.playing = True
            try:
                stream.start()
            except Exception as exc:
                with self.lock:
                    self.playing = False
                    self.available = False
                    self.error = repr(exc)

    def pause(self) -> None:
        with self._stream_control_lock:
            self._stop_stream_controlled(reset_position=False, close=False)

    def stop(self) -> None:
        with self._stream_control_lock:
            self._stop_stream_controlled(reset_position=True, close=True)

    def _stop_stream_controlled(self, *, reset_position: bool, close: bool) -> None:
        """Update player state under ``lock`` and wait for PortAudio without it."""
        with self.lock:
            self.playing = False
            if reset_position:
                self.pos = 0
                self._pos_float = 0.0
            stream = self.stream
            if close:
                self.stream = None
        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass
            if close:
                try:
                    stream.close()
                except Exception:
                    pass

    def toggle(self) -> None:
        if self.playing:
            self.pause()
        else:
            self.play()

    def _source_positions(self, start_pos: float, frames: int, speed: float) -> np.ndarray:
        return start_pos + np.arange(frames, dtype=np.float64) * float(speed)

    def _read_audio_block_speed(
        self,
        start_pos: float,
        frames: int,
        speed: float,
        source_positions: np.ndarray | None = None,
    ):
        assert self.audio is not None
        n = len(self.audio)
        if n <= 0:
            return np.zeros((0, 1), dtype=np.float32)

        if abs(speed - 1.0) < 1e-6 and abs(start_pos - round(start_pos)) < 1e-9:
            s = int(start_pos)
            e = min(n, s + frames)
            return self.audio[s:e]

        positions = source_positions
        if positions is None:
            positions = self._source_positions(start_pos, frames, speed)
        valid = positions < n
        if not np.any(valid):
            return np.zeros((0, 1), dtype=np.float32)

        positions = positions[valid]
        i0 = np.floor(positions).astype(np.int64)
        frac = (positions - i0).astype(np.float32)[:, None]
        i1 = np.minimum(i0 + 1, n - 1)
        return (self.audio[i0] * (1.0 - frac) + self.audio[i1] * frac).astype(np.float32, copy=False)

    def _callback(self, outdata, frames, time, status) -> None:
        with self.lock:
            if not self.playing:
                outdata.fill(0)
                return

            speed = max(0.10, min(4.0, float(getattr(self, "playback_speed", 1.0))))
            start_pos_float = float(getattr(self, "_pos_float", float(self.pos)))
            source_positions = self._source_positions(start_pos_float, frames, speed)

            outdata.fill(0)

            audio_samples = len(self.audio) if self.audio is not None else 0
            playback_end = max(audio_samples, int(self.virtual_duration_samples))
            chunk_len = int(np.searchsorted(source_positions, playback_end, side="left"))
            if self.audio is not None:
                chunk = self._read_audio_block_speed(
                    start_pos_float,
                    frames,
                    speed,
                    source_positions,
                )
                if len(chunk) > 0:
                    outdata[:len(chunk), :] = chunk * self.volume

            if chunk_len > 0:
                active_positions = source_positions[:chunk_len]
                self._mix_preview_notes(outdata[:chunk_len], active_positions)
                self._mix_metronome(outdata[:chunk_len], active_positions)
                np.clip(outdata, -1.0, 1.0, out=outdata)

            if chunk_len < frames:
                self.pos = playback_end
                self._pos_float = float(self.pos)
                self.playing = False
                raise self.sd.CallbackStop

            self._pos_float = start_pos_float + frames * speed
            self.pos = min(max(0, playback_end - 1), int(self._pos_float))
