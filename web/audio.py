from __future__ import annotations

from typing import NamedTuple

import numpy as np

from core.audio_player import AudioPlayer, decode_audio_file as _decode_audio_file


class DecodedAudio(NamedTuple):
    samples: np.ndarray
    sample_rate: int

    @property
    def duration(self) -> float:
        if self.sample_rate <= 0:
            return 0.0
        return float(len(self.samples) / self.sample_rate)


class PlaybackSnapshot(NamedTuple):
    position: float
    duration: float
    playing: bool
    audio_loaded: bool
    error: str | None


def decode_audio_file(path, *, sr: int = 44100) -> DecodedAudio:
    """Return the shape expected by the Web backend while staying tuple-compatible."""
    samples, sample_rate = _decode_audio_file(path, sr=sr)
    return DecodedAudio(samples, int(sample_rate))


class WebAudioPlayer(AudioPlayer):
    """Adapter for the Web backend's older AudioPlayer-facing API."""

    def set_audio(self, audio: np.ndarray, sr: int, *, path: str | None = None) -> None:
        del path
        super().set_audio(audio, sr)

    def set_speed(self, speed: float) -> None:
        self.set_playback_speed(speed)

    def configure_preview(
        self,
        *,
        enabled: bool,
        volume: float,
        octave: int = 0,
        sound: str | None = None,
    ) -> None:
        self.set_note_sound(
            enabled=enabled,
            volume=volume,
            octave_shift=octave,
            instrument=sound,
        )

    def configure_metronome(
        self,
        *,
        enabled: bool,
        bpm: float,
        offset_seconds: float,
        volume: float = 0.35,
    ) -> None:
        self.set_metronome(
            enabled=enabled,
            bpm=bpm,
            offset_sec=offset_seconds,
            volume=volume,
        )

    def snapshot(self) -> PlaybackSnapshot:
        return PlaybackSnapshot(
            position=float(self.time),
            duration=float(self.duration),
            playing=bool(self.playing),
            audio_loaded=self.audio is not None,
            error=self.error,
        )

    def stop(self, reset: bool = True) -> None:
        if reset:
            super().stop()
            return

        with self.lock:
            pos = int(self.pos)
            pos_float = float(self._pos_float)
            super().stop()
            self.pos = pos
            self._pos_float = pos_float
