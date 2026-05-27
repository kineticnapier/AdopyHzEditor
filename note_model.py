from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import math


@dataclass
class Note:
    start: float
    end: float
    midi: float
    velocity: int = 100

    # "note" = fixed pitch rectangle
    # "curve" = cubic Bezier pitch curve
    kind: str = "note"
    midi_end: float | None = None
    ctrl1_midi: float | None = None
    ctrl2_midi: float | None = None

    # Optional per-zip/section angle override for ADOFAI Angle Compression export.
    # None = auto angle.
    target_angle: float | None = None

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def is_curve(self) -> bool:
        return self.kind == "curve"

    @property
    def freq(self) -> float:
        return midi_to_hz(self.midi_at(0.0))

    def midi_at(self, u: float) -> float:
        u = max(0.0, min(1.0, float(u)))
        if not self.is_curve:
            return float(self.midi)

        p0 = float(self.midi)
        p1 = float(self.ctrl1_midi if self.ctrl1_midi is not None else self.midi)
        p2 = float(self.ctrl2_midi if self.ctrl2_midi is not None else (self.midi_end if self.midi_end is not None else self.midi))
        p3 = float(self.midi_end if self.midi_end is not None else self.midi)

        v = 1.0 - u
        return (
            (v ** 3) * p0
            + 3.0 * (v ** 2) * u * p1
            + 3.0 * v * (u ** 2) * p2
            + (u ** 3) * p3
        )

    def freq_at(self, u: float) -> float:
        return midi_to_hz(self.midi_at(u))

    def normalized(self) -> "Note":
        a = float(self.start)
        b = float(self.end)
        p0 = float(self.midi)
        p3 = float(self.midi_end if self.midi_end is not None else self.midi)
        p1 = float(self.ctrl1_midi if self.ctrl1_midi is not None else p0)
        p2 = float(self.ctrl2_midi if self.ctrl2_midi is not None else p3)

        if b < a:
            a, b = b, a
            p0, p3 = p3, p0
            p1, p2 = p2, p1

        kind = "curve" if self.kind == "curve" else "note"
        target_angle = None if self.target_angle is None else float(self.target_angle)
        if kind != "curve":
            return Note(a, b, p0, int(self.velocity), "note", None, None, None, target_angle)

        return Note(a, b, p0, int(self.velocity), "curve", p3, p1, p2, target_angle)

    def with_time_offset(self, offset: float) -> "Note":
        n = self.normalized()
        return Note(
            n.start + offset,
            n.end + offset,
            n.midi,
            n.velocity,
            n.kind,
            n.midi_end,
            n.ctrl1_midi,
            n.ctrl2_midi,
            n.target_angle,
        ).normalized()

    def with_pitch_offset(self, semitones: float) -> "Note":
        n = self.normalized()
        s = float(semitones)
        return Note(
            n.start,
            n.end,
            n.midi + s,
            n.velocity,
            n.kind,
            None if n.midi_end is None else n.midi_end + s,
            None if n.ctrl1_midi is None else n.ctrl1_midi + s,
            None if n.ctrl2_midi is None else n.ctrl2_midi + s,
            n.target_angle,
        ).normalized()

    def shifted(self, dx: float = 0.0, dy: float = 0.0) -> "Note":
        return self.with_time_offset(dx).with_pitch_offset(dy)

    def with_target_angle(self, target_angle: float | None) -> "Note":
        n = self.normalized()
        angle = None if target_angle is None else float(target_angle)
        return Note(
            n.start,
            n.end,
            n.midi,
            n.velocity,
            n.kind,
            n.midi_end,
            n.ctrl1_midi,
            n.ctrl2_midi,
            angle,
        ).normalized()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self.normalized())
        # Keep old project files readable-ish and avoid noisy nulls.
        if d.get("kind") == "note":
            d.pop("midi_end", None)
            d.pop("ctrl1_midi", None)
            d.pop("ctrl2_midi", None)
        if d.get("target_angle") is None:
            d.pop("target_angle", None)
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Note":
        kind = str(d.get("kind", "note"))
        return Note(
            start=float(d["start"]),
            end=float(d["end"]),
            midi=float(d["midi"]),
            velocity=int(d.get("velocity", 100)),
            kind=kind,
            midi_end=None if d.get("midi_end") is None else float(d.get("midi_end")),
            ctrl1_midi=None if d.get("ctrl1_midi") is None else float(d.get("ctrl1_midi")),
            ctrl2_midi=None if d.get("ctrl2_midi") is None else float(d.get("ctrl2_midi")),
            target_angle=None if d.get("target_angle") is None else float(d.get("target_angle")),
        ).normalized()

    def sample_fixed_segments(
        self,
        *,
        max_seconds: float = 0.025,
        max_pitch_step: float = 0.25,
        min_segments: int = 1,
        max_segments: int = 1000,
    ) -> list["Note"]:
        """
        Convert fixed/curve note into short fixed-pitch segments.

        max_pitch_step is in semitones. 0.25 = 25 cents.
        ADOFAI export uses these segments to approximate continuous pitch.
        """
        n = self.normalized()
        if n.duration <= 0:
            return []

        if not n.is_curve:
            return [n]

        # Estimate curve pitch travel.
        probe = [n.midi_at(i / 32.0) for i in range(33)]
        travel = sum(abs(probe[i + 1] - probe[i]) for i in range(32))
        by_time = math.ceil(n.duration / max(0.001, float(max_seconds)))
        by_pitch = math.ceil(travel / max(0.01, float(max_pitch_step)))

        count = max(int(min_segments), by_time, by_pitch, 1)
        count = min(int(max_segments), count)

        out: list[Note] = []
        for i in range(count):
            u0 = i / count
            u1 = (i + 1) / count
            um = (u0 + u1) * 0.5
            s = n.start + n.duration * u0
            e = n.start + n.duration * u1
            out.append(Note(s, e, n.midi_at(um), n.velocity, target_angle=n.target_angle).normalized())
        return out


def midi_to_hz(note: float) -> float:
    return 440.0 * (2.0 ** ((float(note) - 69.0) / 12.0))


def hz_to_midi(freq: float) -> float:
    return 69.0 + 12.0 * math.log2(freq / 440.0)


def note_name(midi: float) -> str:
    m = int(round(float(midi)))
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[m % 12]}{m // 12 - 1}"
