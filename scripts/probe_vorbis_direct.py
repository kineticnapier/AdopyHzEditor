"""Probe the experimental Vorbis Direct backend.

Examples:
    python scripts/probe_vorbis_direct.py input.ogg
    python scripts/probe_vorbis_direct.py input.ogg --csv spectrum.csv
    python scripts/probe_vorbis_direct.py input.ogg --compare-stft
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import tracemalloc

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.vorbis_direct import (  # noqa: E402
    extract_vorbis_spectrum,
    write_vorbis_spectrum_csv,
)


def _percentiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"median": None, "p10": None, "p90": None}
    data = np.asarray(values, dtype=np.float64)
    return {
        "median": float(np.median(data)),
        "p10": float(np.percentile(data, 10)),
        "p90": float(np.percentile(data, 90)),
    }


def probe_direct(source: Path) -> tuple[dict, list]:
    tracemalloc.start()
    started = time.perf_counter()
    info, iterator = extract_vorbis_spectrum(source)
    decode_seconds = time.perf_counter() - started

    conversion_started = time.perf_counter()
    blocks = list(iterator)
    conversion_seconds = time.perf_counter() - conversion_started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_frequencies = []
    short_blocks = 0
    long_blocks = 0
    for block in blocks:
        channel = block.mono_mix()
        peak_bin = int(np.argmax(channel.normalized_magnitude))
        peak_frequencies.append(float(block.bin_frequencies_hz[peak_bin]))
        if block.block_size == info.short_block_size:
            short_blocks += 1
        if block.block_size == info.long_block_size:
            long_blocks += 1

    return (
        {
            "backend": "vorbis_direct",
            "decode_seconds": decode_seconds,
            "conversion_seconds": conversion_seconds,
            "total_seconds": decode_seconds + conversion_seconds,
            "python_peak_memory_bytes": peak_bytes,
            "decoded_pcm_bytes": 0,
            "spectrum_frame_count": len(blocks),
            "short_block_count": short_blocks,
            "long_block_count": long_blocks,
            "sample_rate": info.sample_rate,
            "channels": info.channels,
            "duration_seconds": info.duration,
            "dominant_frequency_hz": _percentiles(peak_frequencies),
        },
        blocks,
    )


def probe_stft(source: Path) -> dict:
    try:
        import soundfile
        from scipy import signal
    except ImportError as exc:
        raise SystemExit(
            "--compare-stft requires the normal core dependencies "
            "(pip install -r requirements-core.txt)"
        ) from exc

    tracemalloc.start()
    started = time.perf_counter()
    decoded_started = time.perf_counter()
    decoded, sample_rate = soundfile.read(
        str(source), always_2d=True, dtype="float32"
    )
    samples = np.mean(decoded, axis=1, dtype=np.float32)
    decode_seconds = time.perf_counter() - decoded_started

    stft_started = time.perf_counter()
    frequencies, _times, complex_spectrum = signal.stft(
        samples,
        fs=sample_rate,
        nperseg=2048,
        noverlap=1536,
        boundary="zeros",
        padded=True,
    )
    spectrum = np.abs(complex_spectrum).astype(np.float32, copy=False)
    stft_seconds = time.perf_counter() - stft_started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_bins = np.argmax(spectrum, axis=0)
    peak_frequencies = frequencies[peak_bins].tolist()
    return {
        "backend": "pcm_stft",
        "decode_seconds": decode_seconds,
        "stft_seconds": stft_seconds,
        "total_seconds": time.perf_counter() - started,
        "python_peak_memory_bytes": peak_bytes,
        "decoded_pcm_bytes": int(samples.nbytes),
        "spectrum_bytes": int(spectrum.nbytes),
        "spectrum_frame_count": int(spectrum.shape[1]),
        "sample_rate": int(sample_rate),
        "duration_seconds": float(len(samples) / sample_rate),
        "dominant_frequency_hz": _percentiles(peak_frequencies),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Extract reconstructed Vorbis coefficients before inverse MDCT."
        )
    )
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "--csv",
        type=Path,
        help="Explicitly write the large per-bin debug CSV.",
    )
    parser.add_argument(
        "--compare-stft",
        action="store_true",
        help="Also benchmark a PCM decode plus 2048-point STFT.",
    )
    args = parser.parse_args()

    direct, blocks = probe_direct(args.source)
    report = {"vorbis_direct": direct}
    if args.csv:
        write_vorbis_spectrum_csv(blocks, args.csv)
        report["csv"] = str(args.csv)
    if args.compare_stft:
        report["pcm_stft"] = probe_stft(args.source)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
