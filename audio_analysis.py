from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import numpy as np


@dataclass
class Spectrogram:
    audio_path: str
    db: np.ndarray
    duration: float
    midi_min: int
    midi_max: int
    frame_times: np.ndarray
    sr: int


def midi_to_hz(note: float) -> float:
    return 440.0 * (2.0 ** ((note - 69.0) / 12.0))


def hz_to_midi(freq: float) -> float:
    import math
    return 69.0 + 12.0 * math.log2(freq / 440.0)


def clamp_midi_range_for_sr(midi_min: int, midi_max: int, sr: int) -> tuple[int, int]:
    """
    Avoid asking CQT for frequencies above Nyquist.
    This also prevents slow/warning-heavy analysis with impossible high bins.
    """
    import math

    nyquist_safe = max(20.0, sr * 0.49)
    max_supported = int(math.floor(hz_to_midi(nyquist_safe)))
    midi_max = min(int(midi_max), max_supported)
    midi_min = int(midi_min)
    if midi_max < midi_min + 12:
        midi_max = midi_min + 12
    return midi_min, midi_max


def cache_key(path: Path, **kwargs) -> str:
    stat = path.stat()
    data = {
        "path": str(path.resolve()),
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        **kwargs,
    }
    raw = json.dumps(data, sort_keys=True).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def analysis_profile_options(profile: str) -> dict:
    """
    Profiles trade pitch range / time resolution for load speed.

    Fast:
        noticeably faster, enough for most melody tracing.
    Normal:
        balanced default.
    Full:
        full C0-C10 range, slower.
    """
    p = (profile or "Normal").lower()
    if p.startswith("fast"):
        return {
            "sr": 22050,
            "midi_min": 24,   # C1
            "midi_max": 96,   # C7
            "hop_length": 2048,
            "engine": "hybrid",
        }
    if p.startswith("full"):
        return {
            "sr": 44100,
            "midi_min": 12,   # C0
            "midi_max": 120,  # C10
            "hop_length": 1024,
            "engine": "hybrid",
        }
    return {
        "sr": 22050,
        "midi_min": 12,      # C0
        "midi_max": 108,     # C8-ish; clamped safely by sr
        "hop_length": 1536,
        "engine": "hybrid",
    }


def analyze_cqt(
    audio_path: str | Path,
    *,
    sr: int = 22050,
    midi_min: int = 12,
    midi_max: int = 108,
    hop_length: int = 1536,
    use_cache: bool = True,
    engine: str = "hybrid",
) -> Spectrogram:
    import librosa

    path = Path(audio_path)
    midi_min, midi_max = clamp_midi_range_for_sr(midi_min, midi_max, sr)

    cache_dir = Path.home() / ".adopyhzeditor_cache"
    cache_dir.mkdir(exist_ok=True)

    # v3: uncompressed npz, hybrid CQT, safe MIDI range clamping
    key = cache_key(
        path,
        cache_version=3,
        sr=sr,
        midi_min=midi_min,
        midi_max=midi_max,
        hop_length=hop_length,
        bins_per_octave=12,
        engine=engine,
    )
    cache_path = cache_dir / f"{key}.npz"

    if use_cache and cache_path.exists():
        data = np.load(cache_path, allow_pickle=False)
        return Spectrogram(
            audio_path=str(path),
            db=data["db"].astype(np.float32),
            duration=float(data["duration"]),
            midi_min=int(data["midi_min"]),
            midi_max=int(data["midi_max"]),
            frame_times=data["frame_times"],
            sr=int(data["sr"]),
        )

    y, actual_sr = librosa.load(str(path), sr=sr, mono=True)
    duration = float(librosa.get_duration(y=y, sr=actual_sr))

    n_bins = int(midi_max - midi_min + 1)

    # hybrid_cqt is usually faster than full cqt for broad ranges.
    cqt_func = librosa.hybrid_cqt if engine == "hybrid" and hasattr(librosa, "hybrid_cqt") else librosa.cqt
    try:
        cqt = cqt_func(
            y,
            sr=actual_sr,
            hop_length=hop_length,
            fmin=midi_to_hz(midi_min),
            n_bins=n_bins,
            bins_per_octave=12,
        )
    except Exception:
        # Fallback for environments where hybrid_cqt is unavailable/unstable.
        cqt = librosa.cqt(
            y,
            sr=actual_sr,
            hop_length=hop_length,
            fmin=midi_to_hz(midi_min),
            n_bins=n_bins,
            bins_per_octave=12,
        )

    db = librosa.amplitude_to_db(np.abs(cqt), ref=np.max).astype(np.float32)
    times = librosa.frames_to_time(np.arange(db.shape[1]), sr=actual_sr, hop_length=hop_length)

    if use_cache:
        # Intentionally uncompressed: bigger cache, much faster second load.
        np.savez(
            cache_path,
            db=db,
            duration=np.array(duration),
            midi_min=np.array(midi_min),
            midi_max=np.array(midi_max),
            frame_times=times,
            sr=np.array(actual_sr),
        )

    return Spectrogram(str(path), db, duration, midi_min, midi_max, times, actual_sr)


def suppress_harmonics(z: np.ndarray, *, strength: float = 0.65, mode: str = "soft") -> np.ndarray:
    """
    表示用の簡易倍音除去。

    CQTは半音binなので、倍音のだいたいの位置は:
      2x: +12
      3x: +19
      4x: +24
      5x: +28
      6x: +31
      7x: +34
      8x: +36

    低いbinが強いとき、その上の倍音っぽいbinを暗くする。
    完全な音源分離ではなく、スペクトログラムを読みやすくするための表示加工。
    """
    if mode == "off" or strength <= 0:
        return z

    y = z.astype(np.float32).copy()
    harmonic_mask = np.zeros_like(y)

    offsets = [12, 19, 24, 28, 31, 34, 36, 38, 40]
    weights = [0.92, 0.78, 0.64, 0.52, 0.44, 0.36, 0.32, 0.28, 0.24]

    for off, w in zip(offsets, weights):
        if off >= y.shape[0]:
            continue
        harmonic_mask[off:, :] = np.maximum(harmonic_mask[off:, :], z[:-off, :] * w)

    if mode == "strong":
        s = max(0.0, min(1.0, strength * 1.25))
        # 強め: 倍音候補をかなり削る
        y = y * (1.0 - s * harmonic_mask)
        y = np.clip(y - harmonic_mask * s * 0.20, 0.0, 1.0)
    else:
        s = max(0.0, min(1.0, strength))
        # 弱め: 倍音候補を薄くする程度
        y = y * (1.0 - s * harmonic_mask * 0.65)

    return np.clip(y, 0.0, 1.0).astype(np.float32)


def enhance_spectrogram(
    db: np.ndarray,
    *,
    contrast: float = 0.72,
    gamma: float = 0.75,
    per_bin: bool = True,
    harmonic_mode: str = "off",
    harmonic_strength: float = 0.65,
) -> np.ndarray:
    x = db.astype(np.float32)

    # contrast は 0.0～3.0 くらいを想定。
    # 1.0以上では弱い成分をかなり削る。
    contrast = max(0.0, float(contrast))
    gamma = max(0.02, float(gamma))

    if per_bin:
        # 常時鳴り成分を除去
        med = np.median(x, axis=1, keepdims=True)
        y = x - med

        # contrast が高いほど下側percentileを上げて、弱い線を消す
        lo_p = min(45.0, 5.0 + contrast * 13.0)
        hi_p = max(85.0, min(99.9, 99.4 - max(0.0, contrast - 1.0) * 0.20))

        lo = np.percentile(y, lo_p)
        hi = np.percentile(y, hi_p)
        if hi <= lo:
            hi = lo + 1.0
        z = np.clip((y - lo) / (hi - lo), 0, 1)
    else:
        # raw dB表示。contrast が高いほどfloorを上げる
        floor = -90.0 + contrast * 28.0
        ceil = -4.0
        if ceil <= floor:
            ceil = floor + 1.0
        z = np.clip((x - floor) / (ceil - floor), 0, 1)

    # 追加コントラスト。高いほど暗い成分を削る
    if contrast > 0:
        threshold = min(0.92, max(0.0, (contrast - 0.50) * 0.22))
        if threshold > 0:
            z = np.clip((z - threshold) / max(0.02, 1.0 - threshold), 0, 1)

    if harmonic_mode != "off":
        z = suppress_harmonics(z, strength=harmonic_strength, mode=harmonic_mode)

    z = np.power(np.clip(z, 0.0, 1.0), gamma)
    return z.astype(np.float32)
