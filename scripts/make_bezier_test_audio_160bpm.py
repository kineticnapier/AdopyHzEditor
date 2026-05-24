from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


SAMPLE_RATE = 44100
BPM = 160.0
BEAT_SEC = 60.0 / BPM
OUTPUT = Path("bezier_glide_test_160bpm.wav")
VOLUME = 0.30


def midi_to_hz(note: float) -> float:
    return 440.0 * (2.0 ** ((note - 69.0) / 12.0))


def bezier(p0: float, p1: float, p2: float, p3: float, u: float) -> float:
    v = 1.0 - u
    return (
        (v ** 3) * p0
        + 3.0 * (v ** 2) * u * p1
        + 3.0 * v * (u ** 2) * p2
        + (u ** 3) * p3
    )


def envelope(i: int, n: int, fade_sec: float = 0.006) -> float:
    fade = max(1, int(SAMPLE_RATE * fade_sec))
    a = min(1.0, i / fade)
    b = min(1.0, (n - 1 - i) / fade)
    return max(0.0, min(a, b))


def append_fixed(buf: list[int], midi: float, beats: float, phase: float) -> float:
    n = int(round(BEAT_SEC * beats * SAMPLE_RATE))
    freq = midi_to_hz(midi)

    for i in range(n):
        value = math.sin(phase) * VOLUME * envelope(i, n)
        buf.append(int(max(-1.0, min(1.0, value)) * 32767))
        phase += 2.0 * math.pi * freq / SAMPLE_RATE

    return phase


def append_bezier_glide(
    buf: list[int],
    p0: float,
    p1: float,
    p2: float,
    p3: float,
    beats: float,
    phase: float,
) -> float:
    n = int(round(BEAT_SEC * beats * SAMPLE_RATE))

    for i in range(n):
        u = i / max(1, n - 1)
        midi = bezier(p0, p1, p2, p3, u)
        freq = midi_to_hz(midi)

        value = math.sin(phase) * VOLUME * envelope(i, n)
        buf.append(int(max(-1.0, min(1.0, value)) * 32767))
        phase += 2.0 * math.pi * freq / SAMPLE_RATE

    return phase


def append_vibrato(
    buf: list[int],
    center_midi: float,
    depth_semitones: float,
    cycles: float,
    beats: float,
    phase: float,
) -> float:
    n = int(round(BEAT_SEC * beats * SAMPLE_RATE))

    for i in range(n):
        u = i / max(1, n - 1)
        midi = center_midi + math.sin(2.0 * math.pi * cycles * u) * depth_semitones
        freq = midi_to_hz(midi)

        value = math.sin(phase) * VOLUME * envelope(i, n)
        buf.append(int(max(-1.0, min(1.0, value)) * 32767))
        phase += 2.0 * math.pi * freq / SAMPLE_RATE

    return phase


def main() -> None:
    buf: list[int] = []
    phase = 0.0

    print(f"BPM: {BPM:g}")
    print(f"1 beat: {BEAT_SEC:.6f} sec")
    print("Recommended editor settings:")
    print("  BPM = 160")
    print("  Offset = 0 ms")

    sections = [
        "0-1 beat:   F4 fixed",
        "1-2 beat:   G4 fixed",
        "2-6 beat:   F4 -> C5 Bezier glide",
        "6-10 beat:  C5 -> A4 Bezier fall",
        "10-14 beat: A4 vibrato",
        "14-15 beat: C5 fixed",
        "15-16 beat: F5 fixed",
    ]
    print("Sections:")
    for s in sections:
        print("  " + s)

    phase = append_fixed(buf, 65.0, 1.0, phase)  # F4
    phase = append_fixed(buf, 67.0, 1.0, phase)  # G4

    phase = append_bezier_glide(buf, 65.0, 65.0, 70.5, 72.0, 4.0, phase)
    phase = append_bezier_glide(buf, 72.0, 73.0, 68.0, 69.0, 4.0, phase)
    phase = append_vibrato(buf, center_midi=69.0, depth_semitones=0.35, cycles=4.0, beats=4.0, phase=phase)

    phase = append_fixed(buf, 72.0, 1.0, phase)  # C5
    phase = append_fixed(buf, 77.0, 1.0, phase)  # F5

    with wave.open(str(OUTPUT), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(struct.pack("<h", s) for s in buf))

    duration = len(buf) / SAMPLE_RATE
    print(f"written: {OUTPUT.resolve()}")
    print(f"duration: {duration:.6f} sec")
    print(f"beats: {duration / BEAT_SEC:.3f}")


if __name__ == "__main__":
    main()
