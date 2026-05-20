from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import math


@dataclass
class Note:
    start: float
    end: float
    midi: int
    velocity: int = 100

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def freq(self) -> float:
        return midi_to_hz(self.midi)

    def normalized(self) -> "Note":
        a = min(self.start, self.end)
        b = max(self.start, self.end)
        return Note(a, b, int(round(self.midi)), int(self.velocity))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Note":
        return Note(
            start=float(d["start"]),
            end=float(d["end"]),
            midi=int(d["midi"]),
            velocity=int(d.get("velocity", 100)),
        ).normalized()


def midi_to_hz(note: float) -> float:
    return 440.0 * (2.0 ** ((note - 69.0) / 12.0))


def hz_to_midi(freq: float) -> float:
    return 69.0 + 12.0 * math.log2(freq / 440.0)


def note_name(midi: int) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[midi % 12]}{midi // 12 - 1}"
