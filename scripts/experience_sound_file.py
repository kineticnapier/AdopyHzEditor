from __future__ import annotations

import math
import struct
import wave


SAMPLE_RATE = 44100
BPM = 160
BEAT_SEC = 60.0 / BPM
VOLUME = 0.35
OUTPUT = "doremi_160bpm.wav"

# C major: ド レ ミ ファ ソ ラ シ ド
NOTES = [
    ("C4", 261.625565),
    ("D4", 293.664768),
    ("E4", 329.627557),
    ("F4", 349.228231),
    ("G4", 391.995436),
    ("A4", 440.000000),
    ("B4", 493.883301),
    ("C5", 523.251131),
]


def sine_sample(freq: float, t: float) -> float:
    return math.sin(2.0 * math.pi * freq * t)


def fade_envelope(i: int, total: int, fade_samples: int) -> float:
    # クリック音防止用の短いフェード。音長は変えない。
    if fade_samples <= 0:
        return 1.0

    if i < fade_samples:
        return i / fade_samples

    remain = total - i - 1
    if remain < fade_samples:
        return remain / fade_samples

    return 1.0


def main() -> None:
    beat_samples = int(round(BEAT_SEC * SAMPLE_RATE))
    fade_samples = int(round(0.005 * SAMPLE_RATE))  # 5ms

    pcm: list[int] = []

    for name, freq in NOTES:
        print(f"{name}: {freq:.3f} Hz, {BEAT_SEC:.3f} sec")

        for i in range(beat_samples):
            t = i / SAMPLE_RATE
            env = fade_envelope(i, beat_samples, fade_samples)
            value = sine_sample(freq, t) * VOLUME * env

            # 16-bit PCM
            sample = int(max(-1.0, min(1.0, value)) * 32767)
            pcm.append(sample)

    with wave.open(OUTPUT, "wb") as wf:
        wf.setnchannels(1)          # mono
        wf.setsampwidth(2)          # 16-bit
        wf.setframerate(SAMPLE_RATE)

        data = b"".join(struct.pack("<h", s) for s in pcm)
        wf.writeframes(data)

    print(f"written: {OUTPUT}")
    print(f"duration: {len(pcm) / SAMPLE_RATE:.3f} sec")


if __name__ == "__main__":
    main()