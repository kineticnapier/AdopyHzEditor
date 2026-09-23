"""Experimental extraction of Vorbis spectra before inverse MDCT.

This module is deliberately separate from the production CQT path. It is a
Phase 1-3 proof of concept: build the small native helper, stream reconstructed
Vorbis coefficient blocks, and optionally dump them as CSV for comparison.
"""

from __future__ import annotations

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
from typing import Iterable, Iterator, Literal

import numpy as np


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
        signed = np.mean(
            np.stack(
                [channel.signed_coefficients for channel in self.channels],
                axis=0,
            ),
            axis=0,
            dtype=np.float32,
        ).astype(np.float32, copy=False)
        return _make_channel(-1, signed)


@dataclass(frozen=True)
class BackendSelection:
    requested: Literal["pcm", "vorbis_direct"]
    selected: Literal["pcm", "vorbis_direct"]
    fallback_reason: str | None = None


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


def read_vorbis_spectrum_file(
    binary_path: str | Path,
) -> tuple[VorbisStreamInfo, Iterator[VorbisSpectrumBlock]]:
    """Open a helper dump and return validated metadata plus a block iterator."""
    stream = Path(binary_path).open("rb")
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
            stream.close()

    return info, blocks()


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

    temporary = tempfile.NamedTemporaryFile(
        prefix="adopyhz-vorbis-spectrum-",
        suffix=".bin",
        delete=False,
    )
    output_path = Path(temporary.name)
    temporary.close()
    output_path.unlink(missing_ok=True)
    try:
        completed = subprocess.run(
            [str(helper), str(source), str(output_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout).strip()
            raise VorbisDirectError(
                f"Vorbis Direct helper failed ({completed.returncode}): "
                f"{details}"
            )
        info, raw_blocks = read_vorbis_spectrum_file(output_path)

        def blocks() -> Iterator[VorbisSpectrumBlock]:
            try:
                yield from raw_blocks
            finally:
                output_path.unlink(missing_ok=True)

        return info, blocks()
    except Exception:
        output_path.unlink(missing_ok=True)
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
