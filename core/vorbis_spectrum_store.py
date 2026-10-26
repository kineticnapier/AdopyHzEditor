"""Compact, queryable storage for experimental Vorbis Direct spectra.

The store keeps every reconstructed mono MDCT magnitude in dense NumPy
planes grouped by block size.  It deliberately contains no pitch tracking or
musical classification; viewport filtering and level-of-detail aggregation
are applied only when a caller asks for a region to draw.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import time
import tracemalloc

import numpy as np

from core.vorbis_direct import VorbisStreamInfo, extract_vorbis_spectrum


SPECTRUM_STORE_VERSION = 1
MAX_VIEWPORT_ELEMENTS = 50_000
_PACKED_CELL_DTYPE = np.dtype(
    [("time", "<u2"), ("pitch", "<u2"), ("magnitude", "u1")]
)


def _readonly(values: np.ndarray) -> np.ndarray:
    values.setflags(write=False)
    return values


@dataclass(frozen=True)
class SpectrumPlane:
    """Dense magnitudes for all blocks sharing one native MDCT size."""

    block_size: int
    block_indices: np.ndarray
    magnitudes: np.ndarray
    block_maxima: np.ndarray

    @property
    def total_bins(self) -> int:
        return int(self.magnitudes.size)

    @property
    def memory_bytes(self) -> int:
        return int(
            self.block_indices.nbytes
            + self.magnitudes.nbytes
            + self.block_maxima.nbytes
        )


@dataclass(frozen=True)
class SpectrumStoreStats:
    blocks_processed: int
    short_blocks: int
    long_blocks: int
    total_bins: int
    stored_bins: int
    analysis_seconds: float
    store_memory_bytes: int
    python_peak_memory_bytes: int

    def to_dict(self) -> dict[str, int | float | str]:
        return {
            "blocksProcessed": self.blocks_processed,
            "shortBlocks": self.short_blocks,
            "longBlocks": self.long_blocks,
            "totalBins": self.total_bins,
            "storedBins": self.stored_bins,
            "analysisSeconds": self.analysis_seconds,
            "spectrumStoreMemoryBytes": self.store_memory_bytes,
            "pythonPeakMemoryBytes": self.python_peak_memory_bytes,
            "storeVersion": SPECTRUM_STORE_VERSION,
            "analysisMode": "spectrum_layer",
        }


@dataclass(frozen=True)
class SpectrumRegion:
    packed_cells: bytes
    returned_elements: int
    time_buckets: int
    pitch_buckets: int
    aggregation_level: float
    query_seconds: float


@dataclass(frozen=True)
class VorbisSpectrumStore:
    stream_info: VorbisStreamInfo
    center_times: np.ndarray
    spans: np.ndarray
    block_sizes: np.ndarray
    planes: tuple[SpectrumPlane, ...]
    source_fingerprint: tuple[str, int, int, int]
    stats: SpectrumStoreStats

    @property
    def duration(self) -> float:
        return float(self.stream_info.duration)

    @property
    def total_bins(self) -> int:
        return int(sum(plane.total_bins for plane in self.planes))

    @property
    def memory_bytes(self) -> int:
        return int(
            self.center_times.nbytes
            + self.spans.nbytes
            + self.block_sizes.nbytes
            + sum(plane.memory_bytes for plane in self.planes)
        )

    def query_region(
        self,
        start_time: float,
        end_time: float,
        minimum_midi: float,
        maximum_midi: float,
        pixel_width: int,
        pixel_height: int,
        threshold: float,
        *,
        max_elements: int = MAX_VIEWPORT_ELEMENTS,
    ) -> SpectrumRegion:
        """Return max-pooled display cells for one editor viewport."""
        started = time.perf_counter()
        start = max(0.0, min(self.duration, float(start_time)))
        end = max(start, min(self.duration, float(end_time)))
        midi_min = max(0.0, min(127.0, float(minimum_midi)))
        midi_max = max(midi_min, min(127.0, float(maximum_midi)))
        width = max(1, min(4096, int(pixel_width)))
        height = max(1, min(2048, int(pixel_height)))
        gate = max(0.0, min(1.0, float(threshold)))
        element_limit = max(256, min(65_000, int(max_elements)))
        if end <= start or midi_max <= midi_min or not self.center_times.size:
            return SpectrumRegion(b"", 0, 1, 1, 1.0, time.perf_counter() - started)

        overlaps = (
            (self.center_times <= end)
            & (self.center_times + self.spans >= start)
        )
        visible_blocks = int(np.count_nonzero(overlaps))
        if not visible_blocks:
            return SpectrumRegion(b"", 0, 1, 1, 1.0, time.perf_counter() - started)

        native_pitch_bins = 1
        for plane in self.planes:
            frequencies = (
                np.arange(plane.block_size // 2, dtype=np.float64) + 0.5
            ) * self.stream_info.sample_rate / plane.block_size
            midi = 69.0 + 12.0 * np.log2(frequencies / 440.0)
            native_pitch_bins = max(
                native_pitch_bins,
                int(np.count_nonzero((midi >= midi_min) & (midi <= midi_max))),
            )

        time_buckets = min(width, visible_blocks)
        pitch_buckets = min(height, native_pitch_bins)
        desired_cells = time_buckets * pitch_buckets
        if desired_cells > element_limit:
            scale = math.sqrt(element_limit / desired_cells)
            time_buckets = max(1, int(time_buckets * scale))
            pitch_buckets = max(1, int(pitch_buckets * scale))

        grid = np.zeros((pitch_buckets, time_buckets), dtype=np.float32)
        time_scale = time_buckets / max(end - start, 1e-12)
        pitch_scale = pitch_buckets / max(midi_max - midi_min, 1e-12)

        for plane in self.planes:
            global_indices = plane.block_indices
            plane_times = self.center_times[global_indices]
            plane_spans = self.spans[global_indices]
            rows = np.flatnonzero(
                (plane_times <= end) & (plane_times + plane_spans >= start)
            )
            if not rows.size:
                continue

            frequencies = (
                np.arange(plane.block_size // 2, dtype=np.float64) + 0.5
            ) * self.stream_info.sample_rate / plane.block_size
            bin_midi = 69.0 + 12.0 * np.log2(frequencies / 440.0)
            bins = np.flatnonzero(
                (bin_midi >= midi_min) & (bin_midi <= midi_max)
            )
            if not bins.size:
                continue
            pitch_indices = np.clip(
                ((bin_midi[bins] - midi_min) * pitch_scale).astype(np.int32),
                0,
                pitch_buckets - 1,
            )

            for offset in range(0, int(rows.size), 256):
                chunk_rows = rows[offset : offset + 256]
                maxima = plane.block_maxima[chunk_rows]
                values = plane.magnitudes[np.ix_(chunk_rows, bins)]
                relative = np.divide(
                    values,
                    maxima[:, None],
                    out=np.zeros_like(values),
                    where=maxima[:, None] > np.finfo(np.float32).tiny,
                )
                keep = (relative > 0.0) & (relative >= gate)
                row_positions, bin_positions = np.nonzero(keep)
                if not row_positions.size:
                    continue
                time_indices = np.clip(
                    (
                        (plane_times[chunk_rows[row_positions]] - start)
                        * time_scale
                    ).astype(np.int32),
                    0,
                    time_buckets - 1,
                )
                np.maximum.at(
                    grid,
                    (pitch_indices[bin_positions], time_indices),
                    relative[row_positions, bin_positions],
                )

        pitch_positions, time_positions = np.nonzero(grid > 0.0)
        values = grid[pitch_positions, time_positions]
        cells = np.empty(values.size, dtype=_PACKED_CELL_DTYPE)
        cells["time"] = time_positions.astype(np.uint16, copy=False)
        cells["pitch"] = pitch_positions.astype(np.uint16, copy=False)
        cells["magnitude"] = np.clip(
            np.rint(values * 255.0), 1, 255
        ).astype(np.uint8)
        aggregation = max(
            visible_blocks / max(1, time_buckets),
            native_pitch_bins / max(1, pitch_buckets),
        )
        return SpectrumRegion(
            packed_cells=cells.tobytes(order="C"),
            returned_elements=int(values.size),
            time_buckets=int(time_buckets),
            pitch_buckets=int(pitch_buckets),
            aggregation_level=float(aggregation),
            query_seconds=time.perf_counter() - started,
        )


def analyze_vorbis_spectrum_store(
    audio_path: str | Path,
    *,
    helper_path: str | Path | None = None,
) -> VorbisSpectrumStore:
    """Decode one source once and retain all mono magnitudes compactly."""
    source = Path(audio_path)
    started = time.perf_counter()
    owned_tracemalloc = not tracemalloc.is_tracing()
    if owned_tracemalloc:
        tracemalloc.start()
    memory_before = tracemalloc.get_traced_memory()[1]

    centers: list[float] = []
    spans: list[float] = []
    sizes: list[int] = []
    plane_values: dict[int, list[np.ndarray]] = {}
    plane_indices: dict[int, list[int]] = {}
    short_blocks = long_blocks = total_bins = 0

    try:
        info, blocks = extract_vorbis_spectrum(source, helper_path=helper_path)
        for block_index, block in enumerate(blocks):
            magnitude = np.asarray(
                block.mono_mix().magnitude,
                dtype=np.float32,
            )
            if magnitude.ndim != 1 or magnitude.size != block.block_size // 2:
                raise ValueError("Vorbis spectrum shape does not match block size")
            if not np.all(np.isfinite(magnitude)):
                raise ValueError("Vorbis spectrum contains a non-finite magnitude")

            next_size = block.next_block_size or block.block_size
            span = (block.block_size + next_size) / (4.0 * block.sample_rate)
            centers.append(float(block.center_time))
            spans.append(float(max(span, 1.0 / block.sample_rate)))
            sizes.append(int(block.block_size))
            plane_values.setdefault(block.block_size, []).append(magnitude.copy())
            plane_indices.setdefault(block.block_size, []).append(block_index)
            total_bins += int(magnitude.size)
            if block.block_size == info.short_block_size:
                short_blocks += 1
            else:
                long_blocks += 1

        center_array = _readonly(np.asarray(centers, dtype=np.float64))
        span_array = _readonly(np.asarray(spans, dtype=np.float32))
        size_array = _readonly(np.asarray(sizes, dtype=np.uint16))
        planes: list[SpectrumPlane] = []
        for block_size in sorted(plane_values):
            magnitudes = np.stack(plane_values[block_size]).astype(
                np.float32,
                copy=False,
            )
            maxima = np.max(magnitudes, axis=1).astype(np.float32, copy=False)
            indices = np.asarray(plane_indices[block_size], dtype=np.uint32)
            planes.append(
                SpectrumPlane(
                    block_size=int(block_size),
                    block_indices=_readonly(indices),
                    magnitudes=_readonly(magnitudes),
                    block_maxima=_readonly(maxima),
                )
            )

        stat = source.stat()
        fingerprint = (
            str(source.resolve()),
            int(stat.st_size),
            int(stat.st_mtime_ns),
            SPECTRUM_STORE_VERSION,
        )
        temporary_store = VorbisSpectrumStore(
            stream_info=info,
            center_times=center_array,
            spans=span_array,
            block_sizes=size_array,
            planes=tuple(planes),
            source_fingerprint=fingerprint,
            stats=SpectrumStoreStats(0, 0, 0, 0, 0, 0.0, 0, 0),
        )
        peak_memory = max(
            0,
            tracemalloc.get_traced_memory()[1] - memory_before,
        )
        stats = SpectrumStoreStats(
            blocks_processed=len(centers),
            short_blocks=short_blocks,
            long_blocks=long_blocks,
            total_bins=total_bins,
            stored_bins=total_bins,
            analysis_seconds=time.perf_counter() - started,
            store_memory_bytes=temporary_store.memory_bytes,
            python_peak_memory_bytes=peak_memory,
        )
        return VorbisSpectrumStore(
            stream_info=info,
            center_times=center_array,
            spans=span_array,
            block_sizes=size_array,
            planes=tuple(planes),
            source_fingerprint=fingerprint,
            stats=stats,
        )
    finally:
        if owned_tracemalloc:
            tracemalloc.stop()
