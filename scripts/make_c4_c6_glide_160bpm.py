from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


SAMPLE_RATE = 44100
BPM = 160.0
BEAT_SEC = 60.0 / BPM
BEATS = 4.0
DURATION_SEC = BEAT_SEC * BEATS
OUTPUT = Path("c4_to_c6_160bpm_4beats.wav")
VOLUME = 0.30


def midi_to_hz(note: float) -> float:
    return 440.0 * (2.0 ** ((note - 69.0) / 12.0))


def smoothstep(u: float) -> float:
    # 0->1 with zero slope at both ends.
    return u * u * (3.0 - 2.0 * u)


def smootherstep(u: float) -> float:
    # Even smoother than smoothstep.
    return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)


def envelope(i: int, n: int, fade_sec: float = 0.006) -> float:
    fade = max(1, int(SAMPLE_RATE * fade_sec))
    a = min(1.0, i / fade)
    b = min(1.0, (n - 1 - i) / fade)
    return max(0.0, min(a, b))


def main() -> None:
    start_midi = 60.0  # C4
    end_midi = 84.0    # C6
    total_samples = int(round(DURATION_SEC * SAMPLE_RATE))

    print(f"BPM: {BPM:g}")
    print(f"1 beat: {BEAT_SEC:.6f} sec")
    print(f"duration: {DURATION_SEC:.6f} sec = {BEATS:g} beats")
    print("Recommended editor settings:")
    print("  BPM = 160")
    print("  Offset = 0 ms")
    print("  Snap = ON")
    print("  Snap div = 1 or 4")
    print("Expected note:")
    print("  C4 -> C6")
    print("  start: 0 beat")
    print("  end:   4 beat")
    print("  Curve: smootherstep-like glide")

    pcm: list[int] = []
    phase = 0.0

    for i in range(total_samples):
        u = i / max(1, total_samples - 1)

        # Smooth continuous pitch from C4 to C6.
        # Change this to smoothstep(u) if you want a slightly more linear curve.
        shaped = smootherstep(u)
        midi = start_midi + (end_midi - start_midi) * shaped
        freq = midi_to_hz(midi)

        value = math.sin(phase) * VOLUME * envelope(i, total_samples)
        pcm.append(int(max(-1.0, min(1.0, value)) * 32767))

        phase += 2.0 * math.pi * freq / SAMPLE_RATE

    with wave.open(str(OUTPUT), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(struct.pack("<h", s) for s in pcm))

    print(f"written: {OUTPUT.resolve()}")


if __name__ == "__main__":
    main()
