"""Experimental extraction of Vorbis spectra before inverse MDCT.

This module is deliberately separate from the production CQT path. It builds
the small native helper, streams reconstructed Vorbis coefficient blocks,
extracts peaks incrementally, and can turn tracked peaks into normal Notes.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import csv
import hashlib
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import tracemalloc
from typing import BinaryIO, Iterable, Iterator, Literal

import numpy as np

from core.note_model import Note, hz_to_midi


_MAGIC = b"ADVMDCT1"
_FORMAT_VERSION = 1
_BLOCK_TAG = 0x4B434C42
_HEADER = struct.Struct("<8sIIIIIQ")
_BLOCK_HEADER = struct.Struct("<IIIIIq")
_U32 = struct.Struct("<I")


class VorbisDirectError(RuntimeError):
    """Base error for the experimental direct backend."""


class VorbisDirectUnavailableError(VorbisDirectError):
    """The source or native toolchain cannot use the direct backend."""


@dataclass(frozen=True)
class VorbisStreamInfo:
    sample_rate: int
    channels: int
    short_block_size: int
    long_block_size: int
    total_samples: int

    @property
    def duration(self) -> float:
        return self.total_samples / self.sample_rate


@dataclass(frozen=True)
class VorbisSpectrumChannel:
    channel: int
    signed_coefficients: np.ndarray
    magnitude: np.ndarray
    normalized_magnitude: np.ndarray


@dataclass(frozen=True)
class VorbisSpectrumBlock:
    packet_index: int
    mode_index: int
    start_time: float
    center_time: float
    block_size: int
    sample_rate: int
    previous_block_size: int
    next_block_size: int
    granule_position: int | None
    channels: tuple[VorbisSpectrumChannel, ...]

    @property
    def bin_frequencies_hz(self) -> np.ndarray:
        bins = np.arange(self.block_size // 2, dtype=np.float64)
        return (bins + 0.5) * self.sample_rate / self.block_size

    def mono_mix(self) -> VorbisSpectrumChannel:
        if len(self.channels) == 1:
            return self.channels[0]
        signed = self.channels[0].signed_coefficients.copy()
        for channel in self.channels[1:]:
            signed += channel.signed_coefficients
        signed /= len(self.channels)
        return _make_channel(-1, signed)


@dataclass(frozen=True)
class BackendSelection:
    requested: Literal["pcm", "vorbis_direct"]
    selected: Literal["pcm", "vorbis_direct"]
    fallback_reason: str | None = None


@dataclass(frozen=True)
class VorbisPeakSettings:
    max_peaks_per_frame: int = 4
    minimum_normalized_magnitude: float = 0.15
    minimum_frequency_hz: float = 40.0
    maximum_frequency_hz: float = 6000.0
    frequency_tolerance_cents: float = 90.0
    maximum_gap_seconds: float = 0.075
    minimum_note_duration: float = 0.03
    minimum_track_frames: int = 4
    short_block_minimum_frames: int = 6
    short_block_aggregation: int = 3


@dataclass(frozen=True)
class VorbisDirectAnalysisStats:
    blocks_processed: int
    short_blocks: int
    long_blocks: int
    raw_peaks_detected: int
    peaks_after_threshold: int
    peaks_selected: int
    final_note_count: int
    analysis_seconds: float
    python_peak_memory_bytes: int

    def to_dict(self) -> dict[str, int | float]:
        return {
            "blocksProcessed": self.blocks_processed,
            "shortBlocks": self.short_blocks,
            "longBlocks": self.long_blocks,
            "rawPeaksDetected": self.raw_peaks_detected,
            "peaksAfterThreshold": self.peaks_after_threshold,
            "peaksSelected": self.peaks_selected,
            "finalNoteCount": self.final_note_count,
            "analysisSeconds": self.analysis_seconds,
            "pythonPeakMemoryBytes": self.python_peak_memory_bytes,
        }


@dataclass(frozen=True)
class VorbisDirectNoteResult:
    notes: tuple[Note, ...]
    stream_info: VorbisStreamInfo
    stats: VorbisDirectAnalysisStats


@dataclass(frozen=True)
class _PeakEvidence:
    time: float
    end_time: float
    frequency_hz: float
    magnitude: float
    bin_width_hz: float
    short_block: bool


@dataclass
class _PeakTrack:
    start_time: float
    last_time: float
    end_time: float
    log_frequency_sum: float
    weight_sum: float
    frames: int
    long_frames: int

    @property
    def frequency_hz(self) -> float:
        return math.exp(self.log_frequency_sum / max(self.weight_sum, 1e-12))


def is_vorbis_source(path: str | Path) -> bool:
    """Check the Ogg container and Vorbis identification signature."""
    try:
        with Path(path).open("rb") as source:
            prefix = source.read(4096)
    except OSError:
        return False
    return prefix.startswith(b"OggS") and b"\x01vorbis" in prefix


def select_analysis_backend(
    path: str | Path,
    requested: Literal["pcm", "vorbis_direct"],
) -> BackendSelection:
    """Resolve experimental backend support without changing existing code."""
    if requested != "vorbis_direct":
        return BackendSelection(requested="pcm", selected="pcm")
    if not is_vorbis_source(path):
        return BackendSelection(
            requested=requested,
            selected="pcm",
            fallback_reason=(
                "Vorbis Direct is unavailable for this source; "
                "falling back to PCM analysis."
            ),
        )
    return BackendSelection(requested=requested, selected="vorbis_direct")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _helper_sources() -> tuple[Path, Path]:
    root = _project_root()
    return (
        root / "native" / "vorbis_spectrum_dump.c",
        root / "third_party" / "stb" / "stb_vorbis.c",
    )


def _helper_digest() -> str:
    digest = hashlib.sha256()
    for source in _helper_sources():
        digest.update(source.read_bytes())
    digest.update(sys.platform.encode("ascii"))
    return digest.hexdigest()[:16]


def _compile_helper(output_path: Path) -> None:
    source, _ = _helper_sources()
    compiler_override = os.environ.get("ADOPY_VORBIS_DIRECT_CC")
    compiler = compiler_override or shutil.which("cc") or shutil.which("gcc")

    if os.name == "nt" and compiler is None:
        compiler = shutil.which("cl")
    if compiler is None:
        raise VorbisDirectUnavailableError(
            "Vorbis Direct requires a C compiler or "
            "ADOPY_VORBIS_DIRECT_HELPER."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(
        f".{output_path.stem}.tmp{output_path.suffix}"
    )
    temporary.unlink(missing_ok=True)
    compiler_name = Path(compiler).name.lower()
    if compiler_name in {"cl", "cl.exe"}:
        command = [
            compiler,
            "/nologo",
            "/O2",
            str(source),
            f"/Fe:{temporary}",
        ]
    else:
        command = [
            compiler,
            "-O2",
            "-std=c99",
            str(source),
            "-lm",
            "-o",
            str(temporary),
        ]

    try:
        completed = subprocess.run(
            command,
            cwd=_project_root(),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout).strip()
            raise VorbisDirectUnavailableError(
                f"Could not build Vorbis Direct helper: {details}"
            )
        os.replace(temporary, output_path)
    finally:
        temporary.unlink(missing_ok=True)


def ensure_vorbis_direct_helper() -> Path:
    override = os.environ.get("ADOPY_VORBIS_DIRECT_HELPER")
    if override:
        helper = Path(override)
        if helper.is_file():
            return helper
        raise VorbisDirectUnavailableError(
            f"ADOPY_VORBIS_DIRECT_HELPER does not exist: {helper}"
        )

    suffix = ".exe" if os.name == "nt" else ""
    helper = (
        Path(tempfile.gettempdir())
        / "adopyhzeditor-vorbis-direct"
        / f"vorbis_spectrum_{_helper_digest()}{suffix}"
    )
    if not helper.exists():
        _compile_helper(helper)
    return helper


def _read_exact(stream, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise VorbisDirectError("Truncated Vorbis Direct helper output")
    return data


def _normalized_magnitude(coefficients: np.ndarray) -> np.ndarray:
    """L2-normalize spectral shape while preserving raw magnitude separately."""
    magnitude = np.abs(coefficients).astype(np.float32, copy=False)
    norm = float(np.linalg.norm(magnitude.astype(np.float64, copy=False)))
    if not math.isfinite(norm) or norm <= np.finfo(np.float32).tiny:
        return np.zeros_like(magnitude)
    return (magnitude / norm).astype(np.float32, copy=False)


def _make_channel(
    channel_index: int,
    coefficients: np.ndarray,
) -> VorbisSpectrumChannel:
    signed = np.asarray(coefficients, dtype=np.float32)
    signed.setflags(write=False)
    magnitude = np.abs(signed).astype(np.float32, copy=False)
    magnitude.setflags(write=False)
    normalized = _normalized_magnitude(signed)
    normalized.setflags(write=False)
    return VorbisSpectrumChannel(
        channel=channel_index,
        signed_coefficients=signed,
        magnitude=magnitude,
        normalized_magnitude=normalized,
    )


def _validate_stream_info(info: VorbisStreamInfo) -> None:
    sizes = (info.short_block_size, info.long_block_size)
    if (
        info.sample_rate <= 0
        or not 1 <= info.channels <= 255
        or any(size < 64 or size > 8192 or size & (size - 1) for size in sizes)
        or info.short_block_size > info.long_block_size
    ):
        raise VorbisDirectError("Invalid Vorbis stream metadata from helper")


def _read_vorbis_spectrum_stream(
    stream: BinaryIO,
    *,
    close_stream: bool,
) -> tuple[VorbisStreamInfo, Iterator[VorbisSpectrumBlock]]:
    try:
        (
            magic,
            version,
            sample_rate,
            channel_count,
            short_size,
            long_size,
            total_samples,
        ) = _HEADER.unpack(_read_exact(stream, _HEADER.size))
        if magic != _MAGIC or version != _FORMAT_VERSION:
            raise VorbisDirectError("Unsupported Vorbis Direct helper format")
        info = VorbisStreamInfo(
            sample_rate=sample_rate,
            channels=channel_count,
            short_block_size=short_size,
            long_block_size=long_size,
            total_samples=total_samples,
        )
        _validate_stream_info(info)
    except Exception:
        if close_stream:
            stream.close()
        raise

    def blocks() -> Iterator[VorbisSpectrumBlock]:
        previous_size = 0
        center_sample = 0.0
        expected_packet = 0
        try:
            while True:
                tag = _U32.unpack(_read_exact(stream, _U32.size))[0]
                if tag == 0:
                    if stream.read(1):
                        raise VorbisDirectError(
                            "Trailing bytes in Vorbis Direct helper output"
                        )
                    return
                if tag != _BLOCK_TAG:
                    raise VorbisDirectError("Invalid Vorbis Direct block tag")

                (
                    packet_index,
                    mode_index,
                    block_size,
                    declared_previous,
                    next_size,
                    granule_position,
                ) = _BLOCK_HEADER.unpack(
                    _read_exact(stream, _BLOCK_HEADER.size)
                )
                if packet_index != expected_packet:
                    raise VorbisDirectError("Non-contiguous Vorbis packet index")
                if block_size not in {
                    info.short_block_size,
                    info.long_block_size,
                }:
                    raise VorbisDirectError("Unexpected Vorbis block size")
                if declared_previous != previous_size:
                    raise VorbisDirectError(
                        "Inconsistent previous Vorbis block size"
                    )
                if next_size not in {
                    0,
                    info.short_block_size,
                    info.long_block_size,
                }:
                    raise VorbisDirectError("Unexpected next Vorbis block size")

                coefficient_count = block_size // 2
                byte_count = info.channels * coefficient_count * 4
                flat = np.frombuffer(
                    _read_exact(stream, byte_count),
                    dtype="<f4",
                ).copy()
                if not np.all(np.isfinite(flat)):
                    raise VorbisDirectError(
                        "Non-finite reconstructed Vorbis coefficient"
                    )

                if previous_size:
                    center_sample += (previous_size + block_size) / 4.0
                window_start_sample = center_sample - block_size / 2.0
                channels = tuple(
                    _make_channel(
                        channel,
                        flat[
                            channel
                            * coefficient_count : (channel + 1)
                            * coefficient_count
                        ],
                    )
                    for channel in range(info.channels)
                )
                yield VorbisSpectrumBlock(
                    packet_index=packet_index,
                    mode_index=mode_index,
                    start_time=max(0.0, window_start_sample / info.sample_rate),
                    center_time=center_sample / info.sample_rate,
                    block_size=block_size,
                    sample_rate=info.sample_rate,
                    previous_block_size=declared_previous,
                    next_block_size=next_size,
                    granule_position=(
                        None if granule_position < 0 else granule_position
                    ),
                    channels=channels,
                )
                expected_packet += 1
                previous_size = block_size
        finally:
            if close_stream:
                stream.close()

    return info, blocks()


def read_vorbis_spectrum_file(
    binary_path: str | Path,
) -> tuple[VorbisStreamInfo, Iterator[VorbisSpectrumBlock]]:
    """Open a saved helper dump and return metadata plus a block iterator."""
    return _read_vorbis_spectrum_stream(
        Path(binary_path).open("rb"),
        close_stream=True,
    )


def extract_vorbis_spectrum(
    audio_path: str | Path,
    *,
    helper_path: str | Path | None = None,
) -> tuple[VorbisStreamInfo, Iterator[VorbisSpectrumBlock]]:
    """Decode an Ogg/Vorbis file only as far as reconstructed MDCT spectra."""
    source = Path(audio_path)
    if not is_vorbis_source(source):
        raise VorbisDirectUnavailableError(
            f"Vorbis Direct only supports Ogg/Vorbis sources: {source}"
        )
    helper = Path(helper_path) if helper_path else ensure_vorbis_direct_helper()

    process = subprocess.Popen(
        [str(helper), str(source), "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise VorbisDirectError("Could not open Vorbis Direct helper pipes")
    try:
        info, raw_blocks = _read_vorbis_spectrum_stream(
            process.stdout,
            close_stream=False,
        )

        def blocks() -> Iterator[VorbisSpectrumBlock]:
            try:
                yield from raw_blocks
                return_code = process.wait()
                if return_code != 0:
                    details = process.stderr.read().decode(
                        "utf-8", errors="replace"
                    ).strip()
                    raise VorbisDirectError(
                        f"Vorbis Direct helper failed ({return_code}): "
                        f"{details}"
                    )
            finally:
                raw_blocks.close()
                process.stdout.close()
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                process.stderr.close()

        return info, blocks()
    except Exception:
        process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()
        raise


def write_vorbis_spectrum_csv(
    blocks: Iterable[VorbisSpectrumBlock],
    csv_path: str | Path,
) -> None:
    """Write an explicit, opt-in coefficient dump for decoder validation."""
    with Path(csv_path).open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(
            [
                "time",
                "start_time",
                "center_time",
                "block_size",
                "previous_block_size",
                "next_block_size",
                "channel",
                "bin",
                "frequency_hz",
                "signed_coefficient",
                "magnitude",
                "normalized_magnitude",
            ]
        )
        for block in blocks:
            frequencies = block.bin_frequencies_hz
            for channel in block.channels:
                for bin_index, frequency_hz in enumerate(frequencies):
                    writer.writerow(
                        [
                            f"{block.center_time:.9f}",
                            f"{block.start_time:.9f}",
                            f"{block.center_time:.9f}",
                            block.block_size,
                            block.previous_block_size,
                            block.next_block_size,
                            channel.channel,
                            bin_index,
                            f"{frequency_hz:.9f}",
                            f"{channel.signed_coefficients[bin_index]:.9g}",
                            f"{channel.magnitude[bin_index]:.9g}",
                            f"{channel.normalized_magnitude[bin_index]:.9g}",
                        ]
                    )


def _validate_peak_settings(settings: VorbisPeakSettings) -> None:
    if settings.max_peaks_per_frame < 1:
        raise ValueError("max_peaks_per_frame must be positive")
    if not 0.0 <= settings.minimum_normalized_magnitude <= 1.0:
        raise ValueError("minimum_normalized_magnitude must be in [0, 1]")
    if not 0.0 < settings.minimum_frequency_hz < settings.maximum_frequency_hz:
        raise ValueError("frequency range must be positive and increasing")
    if settings.frequency_tolerance_cents <= 0.0:
        raise ValueError("frequency_tolerance_cents must be positive")
    if settings.maximum_gap_seconds < 0.0:
        raise ValueError("maximum_gap_seconds must not be negative")
    if settings.minimum_note_duration <= 0.0:
        raise ValueError("minimum_note_duration must be positive")
    if settings.minimum_track_frames < 1 or settings.short_block_minimum_frames < 1:
        raise ValueError("track frame minimums must be positive")
    if settings.short_block_aggregation < 1:
        raise ValueError("short_block_aggregation must be positive")


def _extract_local_peaks(
    block: VorbisSpectrumBlock,
    normalized_magnitude: np.ndarray,
    settings: VorbisPeakSettings,
    *,
    short_block: bool,
) -> tuple[list[_PeakEvidence], int, int]:
    """Extract strongest local maxima without changing the MDCT bin grid."""
    magnitudes = np.asarray(normalized_magnitude, dtype=np.float32)
    if magnitudes.ndim != 1 or magnitudes.size != block.block_size // 2:
        raise VorbisDirectError("Invalid mono spectrum shape")
    if magnitudes.size < 3:
        return [], 0, 0

    frequencies = block.bin_frequencies_hz[1:-1]
    middle = magnitudes[1:-1]
    candidates = np.flatnonzero(
        (frequencies >= settings.minimum_frequency_hz)
        & (frequencies <= settings.maximum_frequency_hz)
        & (middle >= magnitudes[:-2])
        & (middle > magnitudes[2:])
    ) + 1
    raw_count = int(candidates.size)
    candidates = candidates[
        magnitudes[candidates] >= settings.minimum_normalized_magnitude
    ]
    threshold_count = int(candidates.size)
    if not threshold_count:
        return [], raw_count, 0

    bin_width = block.sample_rate / block.block_size
    order = candidates[np.argsort(magnitudes[candidates])[::-1]]
    selected: list[int] = []
    for candidate in order:
        candidate = int(candidate)
        frequency = (candidate + 0.5) * bin_width
        if any(
            _cents_distance(frequency, (other + 0.5) * bin_width)
            < settings.frequency_tolerance_cents
            for other in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) >= settings.max_peaks_per_frame:
            break
    next_size = block.next_block_size or block.block_size
    frame_span = (block.block_size + next_size) / (4.0 * block.sample_rate)
    end_time = block.center_time + max(frame_span, 0.0)
    peaks: list[_PeakEvidence] = []
    for index in selected:
        left = float(magnitudes[index - 1])
        center = float(magnitudes[index])
        right = float(magnitudes[index + 1])
        denominator = left - 2.0 * center + right
        offset = 0.0
        if abs(denominator) > 1e-12:
            offset = max(-0.5, min(0.5, 0.5 * (left - right) / denominator))
        frequency = (index + 0.5 + offset) * bin_width
        if math.isfinite(frequency) and frequency > 0.0:
            peaks.append(
                _PeakEvidence(
                    time=float(block.center_time),
                    end_time=float(end_time),
                    frequency_hz=float(frequency),
                    magnitude=center,
                    bin_width_hz=float(bin_width),
                    short_block=short_block,
                )
            )
    return peaks, raw_count, threshold_count


def _cents_distance(left_hz: float, right_hz: float) -> float:
    if left_hz <= 0.0 or right_hz <= 0.0:
        return math.inf
    return abs(1200.0 * math.log2(left_hz / right_hz))


def _tracking_tolerance_cents(
    peak: _PeakEvidence,
    settings: VorbisPeakSettings,
) -> float:
    low = max(1e-6, peak.frequency_hz - peak.bin_width_hz / 2.0)
    high = peak.frequency_hz + peak.bin_width_hz / 2.0
    bin_resolution = 1200.0 * math.log2(high / low)
    return max(
        settings.frequency_tolerance_cents,
        min(600.0, bin_resolution * (1.1 if peak.short_block else 0.65)),
    )


def _finish_track(
    track: _PeakTrack,
    settings: VorbisPeakSettings,
    duration: float,
) -> Note | None:
    required_frames = (
        settings.minimum_track_frames
        if track.long_frames
        else settings.short_block_minimum_frames
    )
    if track.frames < required_frames:
        return None
    start = max(0.0, min(float(duration), track.start_time))
    end = max(track.end_time, start + settings.minimum_note_duration)
    end = max(start, min(float(duration), end))
    frequency = track.frequency_hz
    if end <= start or not math.isfinite(frequency) or frequency <= 0.0:
        return None
    return Note(start, end, hz_to_midi(frequency), 100).normalized()


def analyze_vorbis_direct_notes(
    audio_path: str | Path,
    *,
    settings: VorbisPeakSettings | None = None,
    helper_path: str | Path | None = None,
) -> VorbisDirectNoteResult:
    """Stream Vorbis spectra into greedily tracked production ``Note`` objects."""
    peak_settings = settings or VorbisPeakSettings()
    _validate_peak_settings(peak_settings)
    started = time.perf_counter()
    owned_tracemalloc = not tracemalloc.is_tracing()
    if owned_tracemalloc:
        tracemalloc.start()
    memory_before = tracemalloc.get_traced_memory()[1]

    blocks_processed = short_blocks = long_blocks = 0
    raw_peaks = threshold_peaks = selected_peaks = 0
    active: list[_PeakTrack] = []
    notes: list[Note] = []
    short_history: deque[np.ndarray] = deque(
        maxlen=peak_settings.short_block_aggregation
    )

    try:
        info, blocks = extract_vorbis_spectrum(
            audio_path,
            helper_path=helper_path,
        )
        for block in blocks:
            blocks_processed += 1
            is_short = block.block_size == info.short_block_size
            if is_short:
                short_blocks += 1
            else:
                long_blocks += 1

            mono = block.mono_mix().normalized_magnitude
            if is_short:
                short_history.append(mono)
                if len(short_history) > 1:
                    # This tiny bounded window smooths coarse short-block bins
                    # without retaining the complete spectrum stream.
                    mono = np.mean(np.stack(tuple(short_history)), axis=0)
                    norm = float(np.linalg.norm(mono.astype(np.float64)))
                    if norm > np.finfo(np.float32).tiny:
                        mono = (mono / norm).astype(np.float32, copy=False)
            else:
                short_history.clear()

            peaks, frame_raw, frame_threshold = _extract_local_peaks(
                block,
                mono,
                peak_settings,
                short_block=is_short,
            )
            raw_peaks += frame_raw
            threshold_peaks += frame_threshold
            selected_peaks += len(peaks)

            still_active: list[_PeakTrack] = []
            for track in active:
                if block.center_time - track.last_time > peak_settings.maximum_gap_seconds:
                    note = _finish_track(track, peak_settings, info.duration)
                    if note is not None:
                        notes.append(note)
                else:
                    still_active.append(track)
            active = still_active

            available_tracks = set(range(len(active)))
            for peak in sorted(peaks, key=lambda item: item.magnitude, reverse=True):
                best_index: int | None = None
                best_distance = math.inf
                tolerance = _tracking_tolerance_cents(peak, peak_settings)
                for index in available_tracks:
                    distance = _cents_distance(
                        active[index].frequency_hz,
                        peak.frequency_hz,
                    )
                    if distance <= tolerance and distance < best_distance:
                        best_index = index
                        best_distance = distance
                weight = max(1e-6, peak.magnitude) * (
                    0.25 if peak.short_block else 1.0
                )
                if best_index is None:
                    active.append(
                        _PeakTrack(
                            start_time=peak.time,
                            last_time=peak.time,
                            end_time=peak.end_time,
                            log_frequency_sum=math.log(peak.frequency_hz) * weight,
                            weight_sum=weight,
                            frames=1,
                            long_frames=0 if peak.short_block else 1,
                        )
                    )
                else:
                    track = active[best_index]
                    track.last_time = peak.time
                    track.end_time = max(track.end_time, peak.end_time)
                    track.log_frequency_sum += math.log(peak.frequency_hz) * weight
                    track.weight_sum += weight
                    track.frames += 1
                    track.long_frames += 0 if peak.short_block else 1
                    available_tracks.remove(best_index)

        for track in active:
            note = _finish_track(track, peak_settings, info.duration)
            if note is not None:
                notes.append(note)
        notes.sort(key=lambda note: (note.start, note.midi, note.end))
        peak_memory = max(
            0,
            tracemalloc.get_traced_memory()[1] - memory_before,
        )
    finally:
        if owned_tracemalloc:
            tracemalloc.stop()

    stats = VorbisDirectAnalysisStats(
        blocks_processed=blocks_processed,
        short_blocks=short_blocks,
        long_blocks=long_blocks,
        raw_peaks_detected=raw_peaks,
        peaks_after_threshold=threshold_peaks,
        peaks_selected=selected_peaks,
        final_note_count=len(notes),
        analysis_seconds=time.perf_counter() - started,
        python_peak_memory_bytes=peak_memory,
    )
    return VorbisDirectNoteResult(tuple(notes), info, stats)
