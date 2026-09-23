"""Literal Vorbis spectrum-to-Note import for the experimental Direct backend.

This intentionally does not try to decide whether a component is a fundamental,
harmonic, or noise. Reconstructed pre-IMDCT bins are transferred to normal
``Note`` objects with only a simple per-block amplitude gate to keep numerical
spectral dust from exploding the editor state.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import time
import tracemalloc

import numpy as np

from core.note_model import Note, hz_to_midi, midi_to_hz
from core.vorbis_direct import (
    VorbisStreamInfo,
    extract_vorbis_spectrum,
)


@dataclass(frozen=True)
class VorbisSpectrumImportSettings:
    """Transport-only controls; none of these classify musical meaning."""

    minimum_relative_magnitude: float = 0.02
    minimum_midi: float = 0.0
    maximum_midi: float = 127.0


@dataclass(frozen=True)
class VorbisSpectrumImportStats:
    blocks_processed: int
    short_blocks: int
    long_blocks: int
    bins_considered: int
    bins_imported: int
    final_note_count: int
    analysis_seconds: float
    python_peak_memory_bytes: int
    minimum_relative_magnitude: float

    def to_dict(self) -> dict[str, int | float]:
        # Keep the old peak-oriented keys as aliases so the existing Web state
        # and debug consumers remain compatible while Direct changes from
        # pitch interpretation to literal spectrum transport.
        return {
            "blocksProcessed": self.blocks_processed,
            "shortBlocks": self.short_blocks,
            "longBlocks": self.long_blocks,
            "rawPeaksDetected": self.bins_considered,
            "peaksAfterThreshold": self.bins_imported,
            "peaksSelected": self.bins_imported,
            "binsConsidered": self.bins_considered,
            "binsImported": self.bins_imported,
            "finalNoteCount": self.final_note_count,
            "analysisSeconds": self.analysis_seconds,
            "pythonPeakMemoryBytes": self.python_peak_memory_bytes,
            "minimumRelativeMagnitude": self.minimum_relative_magnitude,
            "importMode": "spectrum_bins",
        }


@dataclass(frozen=True)
class VorbisSpectrumImportResult:
    notes: tuple[Note, ...]
    stream_info: VorbisStreamInfo
    stats: VorbisSpectrumImportStats


def _validate_settings(settings: VorbisSpectrumImportSettings) -> None:
    if not 0.0 <= settings.minimum_relative_magnitude <= 1.0:
        raise ValueError("minimum_relative_magnitude must be in [0, 1]")
    if not math.isfinite(settings.minimum_midi) or not math.isfinite(settings.maximum_midi):
        raise ValueError("MIDI bounds must be finite")
    if settings.minimum_midi >= settings.maximum_midi:
        raise ValueError("minimum_midi must be smaller than maximum_midi")


def analyze_vorbis_spectrum_notes(
    audio_path: str | Path,
    *,
    settings: VorbisSpectrumImportSettings | None = None,
    helper_path: str | Path | None = None,
) -> VorbisSpectrumImportResult:
    """Transfer significant pre-IMDCT bins directly into ordinary Notes.

    There is deliberately no local-peak selection, harmonic/fundamental test,
    noise classifier, pitch tracker, or temporal merge. Every representable bin
    that passes the simple relative-amplitude gate becomes one Note for that
    Vorbis block interval.
    """

    import_settings = settings or VorbisSpectrumImportSettings()
    _validate_settings(import_settings)

    minimum_hz = midi_to_hz(import_settings.minimum_midi)
    maximum_hz = midi_to_hz(import_settings.maximum_midi)

    started = time.perf_counter()
    owned_tracemalloc = not tracemalloc.is_tracing()
    if owned_tracemalloc:
        tracemalloc.start()
    memory_before = tracemalloc.get_traced_memory()[1]

    blocks_processed = 0
    short_blocks = 0
    long_blocks = 0
    bins_considered = 0
    bins_imported = 0
    notes: list[Note] = []

    try:
        info, blocks = extract_vorbis_spectrum(
            audio_path,
            helper_path=helper_path,
        )
        duration = max(0.0, float(info.duration))

        for block in blocks:
            blocks_processed += 1
            if block.block_size == info.short_block_size:
                short_blocks += 1
            else:
                long_blocks += 1

            channel = block.mono_mix()
            magnitudes = np.asarray(channel.magnitude, dtype=np.float32)
            frequencies = block.bin_frequencies_hz
            if magnitudes.ndim != 1 or magnitudes.size != frequencies.size:
                raise ValueError("Vorbis spectrum shape does not match bin frequencies")

            representable = (
                np.isfinite(magnitudes)
                & (magnitudes > 0.0)
                & (frequencies >= minimum_hz)
                & (frequencies <= maximum_hz)
            )
            indices = np.flatnonzero(representable)
            bins_considered += int(indices.size)
            if not indices.size:
                continue

            block_max = float(np.max(magnitudes[indices]))
            if not math.isfinite(block_max) or block_max <= np.finfo(np.float32).tiny:
                continue

            floor = block_max * float(import_settings.minimum_relative_magnitude)
            if floor > 0.0:
                indices = indices[magnitudes[indices] >= floor]
            bins_imported += int(indices.size)
            if not indices.size:
                continue

            next_size = block.next_block_size or block.block_size
            frame_span = (
                block.block_size + next_size
            ) / (4.0 * block.sample_rate)
            start = max(0.0, min(duration, float(block.center_time)))
            end = min(duration, start + max(frame_span, 1.0 / block.sample_rate))
            if end <= start:
                continue

            relative = np.clip(
                magnitudes[indices].astype(np.float64) / block_max,
                0.0,
                1.0,
            )
            velocities = np.clip(
                np.rint(1.0 + 126.0 * relative),
                1,
                127,
            ).astype(np.int16)

            for index, velocity in zip(indices.tolist(), velocities.tolist()):
                frequency = float(frequencies[index])
                if not math.isfinite(frequency) or frequency <= 0.0:
                    continue
                notes.append(
                    Note(
                        start,
                        end,
                        hz_to_midi(frequency),
                        int(velocity),
                    ).normalized()
                )

        notes.sort(key=lambda note: (note.start, note.midi, note.end))
        peak_memory = max(
            0,
            tracemalloc.get_traced_memory()[1] - memory_before,
        )
    finally:
        if owned_tracemalloc:
            tracemalloc.stop()

    stats = VorbisSpectrumImportStats(
        blocks_processed=blocks_processed,
        short_blocks=short_blocks,
        long_blocks=long_blocks,
        bins_considered=bins_considered,
        bins_imported=bins_imported,
        final_note_count=len(notes),
        analysis_seconds=time.perf_counter() - started,
        python_peak_memory_bytes=peak_memory,
        minimum_relative_magnitude=float(import_settings.minimum_relative_magnitude),
    )
    return VorbisSpectrumImportResult(tuple(notes), info, stats)
