from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
import math
from pathlib import Path
from typing import Any

from adofai_angles import clean_angle, clean_relative_angle
from export_adofai import set_bpm


class HzToolError(ValueError):
    """User-facing validation error for the quick Hz tools."""


@dataclass(frozen=True)
class HzCalculationInfo:
    bpm: float
    hz: float
    interval_ms: float
    beat_ms: float
    beats_per_hit: float
    relative_angle: float
    equivalent_bpm: float
    beat_fraction: Fraction

    @property
    def beat_fraction_text(self) -> str:
        frac = self.beat_fraction
        if frac.numerator == 1:
            return f"1/{frac.denominator} beat"
        return f"{frac.numerator}/{frac.denominator} beat"


@dataclass(frozen=True)
class GeneratedHzStep:
    index: int
    floor: int
    time_ms_from_start: float
    relative_angle: float


@dataclass(frozen=True)
class ChartAppendResult:
    source_path: Path
    output_path: Path | None
    start_floor: int
    generated_tiles: int
    actions_added: int
    angle_data_added: int


def _finite_positive(value: float, name: str) -> float:
    try:
        out = float(value)
    except Exception as exc:
        raise HzToolError(f"{name} must be a number.") from exc
    if not math.isfinite(out) or out <= 0:
        raise HzToolError(f"{name} must be greater than 0.")
    return out


def _non_negative_int(value: int | float, name: str) -> int:
    try:
        out = int(value)
    except Exception as exc:
        raise HzToolError(f"{name} must be an integer.") from exc
    if out < 0:
        raise HzToolError(f"{name} must be 0 or greater.")
    return out


def CalculateHzInfo(bpm: float, hz: float) -> HzCalculationInfo:
    bpm = _finite_positive(bpm, "BPM")
    hz = _finite_positive(hz, "Hz")

    interval_ms = 1000.0 / hz
    beat_ms = 60000.0 / bpm
    beats_per_hit = interval_ms / beat_ms
    relative_angle = clean_relative_angle(beats_per_hit * 180.0)
    equivalent_bpm = hz * 60.0
    beat_fraction = Fraction(beats_per_hit).limit_denominator(256)

    return HzCalculationInfo(
        bpm=bpm,
        hz=hz,
        interval_ms=interval_ms,
        beat_ms=beat_ms,
        beats_per_hit=beats_per_hit,
        relative_angle=relative_angle,
        equivalent_bpm=equivalent_bpm,
        beat_fraction=beat_fraction,
    )


def ResolveGenerateCount(start_floor: int, count: int | None = None, end_floor: int | None = None) -> int:
    start = _non_negative_int(start_floor, "Start floor")
    if end_floor is not None:
        end = _non_negative_int(end_floor, "End floor")
        if end <= start:
            raise HzToolError("End floor must be greater than start floor.")
        return end - start

    if count is None:
        raise HzToolError("Generate count is required.")
    out = _non_negative_int(count, "Generate count")
    if out <= 0:
        raise HzToolError("Generate count must be greater than 0.")
    return out


def GenerateHzPreview(info: HzCalculationInfo, start_floor: int, count: int) -> list[GeneratedHzStep]:
    start = _non_negative_int(start_floor, "Start floor")
    count = ResolveGenerateCount(start, count=count)

    return [
        GeneratedHzStep(
            index=i + 1,
            floor=start + i + 1,
            time_ms_from_start=(i + 1) * info.interval_ms,
            relative_angle=info.relative_angle,
        )
        for i in range(count)
    ]


def GenerateOutputText(info: HzCalculationInfo, start_floor: int, count: int, *, add_set_speed: bool = True) -> str:
    start = _non_negative_int(start_floor, "Start floor")
    count = ResolveGenerateCount(start, count=count)
    steps = GenerateHzPreview(info, start, count)
    speed_actions = [set_bpm(start, info.bpm)] if add_set_speed else []

    preview_limit = 200
    lines: list[str] = [
        "# AdopyHzEditor Quick Hz Output",
        f"BPM: {info.bpm:.6f}",
        f"Hz: {info.hz:.6f}",
        f"intervalMs: {info.interval_ms:.6f}",
        f"beatMs: {info.beat_ms:.6f}",
        f"beatsPerHit: {info.beats_per_hit:.9f} ({info.beat_fraction_text})",
        f"relativeAnglePerHit: {info.relative_angle:.9f}",
        f"equivalentBpmFor180deg: {info.equivalent_bpm:.6f}",
        f"startFloor: {start}",
        f"generatedTiles: {count}",
        "",
        "# ADOFAI actions fragment",
        json.dumps(speed_actions, ensure_ascii=False, indent=2),
        "",
        "# Relative angle preview",
    ]

    for step in steps[:preview_limit]:
        lines.append(
            f"floor {step.floor}: rel={step.relative_angle:.9f} "
            f"time=+{step.time_ms_from_start:.6f}ms"
        )
    if len(steps) > preview_limit:
        lines.append(f"... {len(steps) - preview_limit} more rows omitted from text preview")

    return "\n".join(lines)


def _load_chart(path: str | Path) -> dict[str, Any]:
    chart_path = Path(path)
    if not chart_path:
        raise HzToolError("No ADOFAI file selected.")
    try:
        text = chart_path.read_text(encoding="utf-8-sig")
    except Exception as exc:
        raise HzToolError(f"Could not read ADOFAI file: {exc}") from exc

    try:
        data = json.loads(text)
    except Exception as exc:
        raise HzToolError(f"ADOFAI JSON is invalid: {exc}") from exc

    if not isinstance(data, dict):
        raise HzToolError("ADOFAI root must be a JSON object.")
    return data



def ReadChartTailFloor(chart_path: str | Path) -> int:
    data = _load_chart(chart_path)
    angle_data = data.get("angleData")
    if not isinstance(angle_data, list) or not angle_data:
        return 0
    return max(0, len(angle_data) - 1)


def _safe_float_angle(value: Any, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return fallback
    if not math.isfinite(out):
        return fallback
    return out


def _append_relative_angle(angle_data: list[Any], relative_angle: float) -> None:
    prev = _safe_float_angle(angle_data[-1] if angle_data else 0.0, 0.0)
    rel = clean_relative_angle(relative_angle)
    angle_data.append(clean_angle(prev + 180.0 - rel))


def AppendGeneratedDataToChart(
    chart_path: str | Path,
    info: HzCalculationInfo,
    count: int,
    *,
    start_floor: int | None = None,
    add_set_speed: bool = True,
) -> tuple[dict[str, Any], ChartAppendResult]:
    source = Path(chart_path)
    data = _load_chart(source)

    angle_data = data.get("angleData")
    if angle_data is None:
        angle_data = [0]
        data["angleData"] = angle_data
    if not isinstance(angle_data, list):
        raise HzToolError("angleData must be an array.")
    if not angle_data:
        angle_data.append(0)

    actions = data.get("actions")
    if actions is None:
        actions = []
        data["actions"] = actions
    if not isinstance(actions, list):
        raise HzToolError("actions must be an array.")

    append_start = len(angle_data) - 1 if start_floor is None else _non_negative_int(start_floor, "Start floor")
    if append_start < len(angle_data) - 1:
        # This tool is intentionally append-only. Keep the chart safe by writing to the tail.
        append_start = len(angle_data) - 1

    count = ResolveGenerateCount(append_start, count=count)

    actions_added = 0
    if add_set_speed:
        actions.append(set_bpm(append_start, info.bpm))
        actions_added = 1

    for _ in range(count):
        _append_relative_angle(angle_data, info.relative_angle)

    return data, ChartAppendResult(
        source_path=source,
        output_path=None,
        start_floor=append_start,
        generated_tiles=count,
        actions_added=actions_added,
        angle_data_added=count,
    )


def default_added_path(source_path: str | Path) -> Path:
    source = Path(source_path)
    if source.suffix:
        return source.with_name(f"{source.stem}_added{source.suffix}")
    return source.with_name(f"{source.name}_added.adofai")


def SaveChartAs(
    chart_data: dict[str, Any],
    source_path: str | Path,
    output_path: str | Path | None = None,
    *,
    overwrite: bool = False,
) -> Path:
    source = Path(source_path)
    if output_path is None:
        output = source if overwrite else default_added_path(source)
    else:
        output = Path(output_path)

    if output.exists() and output.resolve() == source.resolve() and not overwrite:
        raise HzToolError("Overwrite is disabled.")

    try:
        output.write_text(
            json.dumps(chart_data, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        raise HzToolError(f"Could not save ADOFAI file: {exc}") from exc
    return output


# snake_case aliases for internal callers that prefer the existing project style.
calculate_hz_info = CalculateHzInfo
generate_output_text = GenerateOutputText
append_generated_data_to_chart = AppendGeneratedDataToChart
save_chart_as = SaveChartAs
