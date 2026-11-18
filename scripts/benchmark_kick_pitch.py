"""Compare the kick pitch estimators on synthetic signals with known pitch.

Usage::

    python scripts/benchmark_kick_pitch.py [--hop 0.001] [--real DIR]

For every signal and method it prints the median / 90th percentile error in
cents over frames with confidence >= 0.5, the share of such frames
("coverage"), the analysis time (untraced run) and the tracemalloc peak (second run).  With ``--real`` the
WAV files in DIR (e.g. piep-kick.wav) are analysed and their primary
trajectory summary is printed; nothing is written to disk.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
import time
import tracemalloc

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.pitch_tracking import METHODS, PitchTrackingSettings, analyze_pitch_region  # noqa: E402


SR = 44_100


def _synth(freq: np.ndarray, harmonics: dict[int, float] | None = None) -> np.ndarray:
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    return sum(a * np.sin(h * phase) for h, a in (harmonics or {1: 1.0}).items())


def signals() -> list[tuple[str, np.ndarray, callable, float]]:
    out = []

    def add(name, duration, f_fn, harmonics=None, post=None):
        t = np.arange(int(duration * SR)) / SR
        y = _synth(f_fn(t), harmonics)
        if post is not None:
            y = post(t, y)
        out.append((name, y, f_fn, duration))

    add("constant 112.3Hz", 0.5, lambda t: np.full_like(t, 112.3))
    add("linear 150->50Hz", 0.25, lambda t: 150.0 - 100.0 * np.clip(t / 0.25, 0, 1))
    add("exp 165->45Hz", 0.35, lambda t: 45.0 + 120.0 * np.exp(-t / 0.05))
    add(
        "exp kick w/ attack",
        0.35,
        lambda t: 45.0 + 120.0 * np.exp(-np.clip(t - 0.02, 0, None) / 0.05),
        post=lambda t, y: y * (t >= 0.02) * np.minimum(1.0, np.clip(t - 0.02, 0, None) / 0.002)
        * np.exp(-np.clip(t - 0.02, 0, None) / 0.4),
    )
    add("73Hz + harmonics + strong h12 (876Hz)", 0.4, lambda t: np.full_like(t, 73.0),
        {1: 1.0, 2: 0.5, 3: 0.3, 4: 0.2, 12: 1.6})
    add("piep glide 150->50 + h12", 0.3, lambda t: 50.0 + 100.0 * np.exp(-t / 0.08),
        {1: 1.0, 2: 0.4, 3: 0.25, 12: 1.4})
    add("zaag tanh(6 sin) 120->55", 0.3, lambda t: 55.0 + 65.0 * np.exp(-t / 0.07),
        post=lambda t, y: np.tanh(6.0 * y))
    add("saw 8 harmonics 90Hz", 0.4, lambda t: np.full_like(t, 90.0),
        {h: 1.0 / h for h in range(1, 9)})
    rng = np.random.default_rng(1234)
    add("110Hz + noise (+6dB SNR)", 0.5, lambda t: np.full_like(t, 110.0),
        post=lambda t, y: y + rng.standard_normal(y.size) * np.sqrt(np.mean(y**2)) / 2.0)
    add("100Hz + 317Hz (primary=100)", 0.4, lambda t: np.full_like(t, 100.0),
        post=lambda t, y: y + 0.7 * np.sin(2 * np.pi * 317.0 * t))
    return out


def evaluate(settings: PitchTrackingSettings) -> None:
    analyze_pitch_region(np.zeros(4410), SR, 0, 0.05, settings)  # warm imports
    print(f"hop={settings.hop_seconds * 1000:.2f} ms  min_periods={settings.min_periods}")
    print(f"{'signal':40s} {'method':12s} {'median':>8s} {'p90':>8s} {'cover':>6s} {'sec':>6s} {'MiB':>6s} cands")
    for name, y, f_fn, duration in signals():
        for method in METHODS:
            options = replace(settings, method=method)
            started = time.perf_counter()
            result = analyze_pitch_region(y, SR, 0.0, duration, options)
            elapsed = time.perf_counter() - started
            tracemalloc.start()  # separate run: tracing slows the timing run
            analyze_pitch_region(y, SR, 0.0, duration, options)
            _current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            fr = result.frames
            inner = (fr.times >= 0.03) & (fr.times <= duration - 0.03)
            keep = inner & np.isfinite(fr.hz) & (fr.confidence >= 0.5)
            err = 1200.0 * np.abs(np.log2(fr.hz[keep] / f_fn(fr.times[keep]))) if keep.any() else np.array([np.nan])
            roles = ",".join(
                f"{c.role[:3]}:{np.median(c.hz):.0f}" for c in result.candidates if c.duration >= 0.05
            )
            print(
                f"{name:40s} {method:12s} {np.median(err):8.2f} {np.percentile(err, 90):8.2f} "
                f"{keep.sum() / max(1, inner.sum()):6.2f} {elapsed:6.3f} {peak / 2**20:6.1f} {roles}"
            )


def real_files(directory: Path, settings: PitchTrackingSettings) -> None:
    import soundfile as sf

    for path in sorted(directory.glob("*.wav")):
        data, sr = sf.read(str(path), always_2d=True)
        duration = min(data.shape[0] / sr, settings.max_region_seconds)
        started = time.perf_counter()
        result = analyze_pitch_region(data, sr, 0.0, duration, settings)
        elapsed = time.perf_counter() - started
        print(f"\n{path.name}: {duration:.3f}s analysed in {elapsed:.3f}s, {len(result.candidates)} candidates")
        for c in sorted(result.candidates, key=lambda c: -c.score)[:6]:
            ok = c.confidence >= 0.5
            print(
                f"  #{c.id} {c.role:11s} {c.times[0]:.3f}-{c.times[-1]:.3f}s "
                f"start {c.hz[0]:.1f}Hz -> end {c.hz[-1]:.1f}Hz, median {np.median(c.hz):.1f}Hz, "
                f"confident {ok.mean():.2f}"
                + (f" harmonic x{c.harmonic_number}" if c.harmonic_number else "")
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hop", type=float, default=0.001)
    parser.add_argument("--min-periods", type=float, default=PitchTrackingSettings().min_periods)
    parser.add_argument("--real", type=Path)
    args = parser.parse_args()
    settings = PitchTrackingSettings(hop_seconds=args.hop, min_periods=args.min_periods)
    if args.real:
        real_files(args.real, settings)
    else:
        evaluate(settings)


if __name__ == "__main__":
    main()
