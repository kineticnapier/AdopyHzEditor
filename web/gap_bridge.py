from __future__ import annotations

import math
from typing import Any

from exporters.adofai import build_adofai_level as _core_build_adofai_level


_EPS = 1e-9
_MAX_BRIDGE_BPM = 999999.0


def _initial_bpm(level: dict[str, Any]) -> float:
    settings = level.get("settings", {})
    for key in ("bpm", "beatsPerMinute"):
        try:
            value = float(settings.get(key))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value > _EPS:
            return value
    return 120.0


def _apply_speed_action(current_bpm: float, action: dict[str, Any]) -> float:
    if action.get("eventType") != "SetSpeed":
        return current_bpm

    speed_type = str(action.get("speedType", "Bpm")).lower()
    if speed_type == "multiplier":
        try:
            multiplier = float(action.get("bpmMultiplier", 1.0))
        except (TypeError, ValueError):
            return current_bpm
        if math.isfinite(multiplier) and multiplier > _EPS:
            return current_bpm * multiplier
        return current_bpm

    try:
        bpm = float(action.get("beatsPerMinute"))
    except (TypeError, ValueError):
        return current_bpm
    if math.isfinite(bpm) and bpm > _EPS:
        return bpm
    return current_bpm


def _pause_bpms(level: dict[str, Any]) -> dict[int, float]:
    """Return the effective BPM for each Pause action index."""
    actions = list(level.get("actions", []))
    ordered = sorted(
        enumerate(actions),
        key=lambda item: (int(item[1].get("floor", 0) or 0), item[0]),
    )
    current_bpm = _initial_bpm(level)
    result: dict[int, float] = {}
    for index, action in ordered:
        if action.get("eventType") == "SetSpeed":
            current_bpm = _apply_speed_action(current_bpm, action)
        elif action.get("eventType") == "Pause":
            result[index] = current_bpm
    return result


def _set_bpm_event(floor: int, bpm: float) -> dict[str, Any]:
    return {
        "floor": int(floor),
        "eventType": "SetSpeed",
        "speedType": "Bpm",
        "beatsPerMinute": round(float(bpm), 6),
        "bpmMultiplier": 1,
    }


def replace_note_gap_pauses_with_bridge_tiles(
    level: dict[str, Any],
    stats: dict[str, Any],
    *,
    max_tiles: int = 0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Replace ordinary note-gap Pause events with one timed 180-degree tile.

    The core exporter normalizes the first note to t=0, so in non-Harmony modes
    every generated Pause is a gap between notes.  A bridge tile is inserted
    immediately after the paused floor.  Its relative angle is exactly 180°
    (duplicate absolute heading), and a SetSpeed on that bridge floor makes the
    tile consume the same real time as the removed Pause.

    Existing floors after the gap are shifted by one.  If the next original
    floor did not already carry SetSpeed, an explicit restore event is inserted
    there so Angle-only charts return to their global BPM.
    """
    angle_data = list(level.get("angleData", []))
    actions = [dict(action) for action in level.get("actions", [])]
    if len(angle_data) < 2 or not actions:
        return level, stats

    pause_bpm = _pause_bpms(level)
    current_tiles = int(stats.get("tiles_total", max(0, len(angle_data) - 2)) or 0)
    capacity = None if int(max_tiles or 0) <= 0 else max(0, int(max_tiles) - current_tiles)

    # A SetSpeed on original floor P+1 belongs to the first tile after the gap;
    # after insertion it naturally shifts to P+2 and restores the correct speed.
    set_speed_floors = {
        int(action.get("floor", -1))
        for action in actions
        if action.get("eventType") == "SetSpeed"
    }

    chosen: dict[int, dict[str, float]] = {}
    converted_action_indices: set[int] = set()
    fallback_count = 0

    for index, action in enumerate(actions):
        if action.get("eventType") != "Pause":
            continue
        try:
            floor = int(action.get("floor", -1))
            beats = float(action.get("duration", 0.0))
            bpm = max(_EPS, float(pause_bpm.get(index, 120.0)))
        except (TypeError, ValueError):
            fallback_count += 1
            continue
        if floor < 0 or floor >= len(angle_data) or beats <= _EPS:
            fallback_count += 1
            continue
        seconds = beats * 60.0 / bpm
        bridge_bpm = 60.0 / max(_EPS, seconds)
        if (
            not math.isfinite(seconds)
            or seconds <= 1e-6
            or not math.isfinite(bridge_bpm)
            or bridge_bpm > _MAX_BRIDGE_BPM
        ):
            fallback_count += 1
            continue
        if capacity is not None and len(chosen) >= capacity:
            fallback_count += 1
            continue

        # Multiple Pause events on the same floor are unusual.  Keep one bridge
        # tile and combine their real durations rather than adding overlapping
        # bridge tiles at the same location.
        if floor in chosen:
            chosen[floor]["seconds"] += seconds
            chosen[floor]["bridge_bpm"] = 60.0 / chosen[floor]["seconds"]
        else:
            chosen[floor] = {
                "seconds": seconds,
                "bridge_bpm": bridge_bpm,
                "restore_bpm": bpm,
            }
        converted_action_indices.add(index)

    if not chosen:
        out_stats = dict(stats)
        out_stats["gap_bridge_tiles"] = 0
        out_stats["gap_bridge_seconds"] = 0.0
        out_stats["gap_pause_fallbacks"] = fallback_count
        return level, out_stats

    gap_floors = sorted(chosen)

    def shift_before(old_floor: int) -> int:
        # Insertion happens after its Pause floor, so that floor itself does not
        # move; every later original floor moves by one for each earlier gap.
        return sum(1 for gap_floor in gap_floors if gap_floor < old_floor)

    new_angles: list[Any] = []
    for old_floor, angle in enumerate(angle_data):
        new_angles.append(angle)
        if old_floor in chosen:
            # Same absolute heading => relative angle 180° with or without Twirl.
            new_angles.append(angle)

    new_actions: list[dict[str, Any]] = []
    for index, action in enumerate(actions):
        old_floor = int(action.get("floor", 0) or 0)
        if index in converted_action_indices:
            gap = chosen[old_floor]
            adjusted_pause_floor = old_floor + shift_before(old_floor)
            bridge_floor = adjusted_pause_floor + 1
            next_original_floor = old_floor + 1
            next_floor = next_original_floor + shift_before(next_original_floor)

            new_actions.append(_set_bpm_event(bridge_floor, gap["bridge_bpm"]))
            if next_original_floor not in set_speed_floors:
                new_actions.append(_set_bpm_event(next_floor, gap["restore_bpm"]))
            continue

        shifted = dict(action)
        shifted["floor"] = old_floor + shift_before(old_floor)
        new_actions.append(shifted)

    level_out = dict(level)
    level_out["angleData"] = new_angles
    level_out["actions"] = new_actions

    out_stats = dict(stats)
    bridge_count = len(chosen)
    out_stats["gap_bridge_tiles"] = bridge_count
    out_stats["gap_bridge_seconds"] = round(sum(v["seconds"] for v in chosen.values()), 6)
    out_stats["gap_pause_fallbacks"] = fallback_count
    out_stats["tiles_total"] = current_tiles + bridge_count
    out_stats["floors_total"] = len(new_angles) - 1
    out_stats["actions_total"] = len(new_actions)
    return level_out, out_stats


def build_adofai_level_with_gap_bridges(*args: Any, **kwargs: Any):
    level, stats = _core_build_adofai_level(*args, **kwargs)
    method = str(kwargs.get("method", "rabbit_zip")).lower().replace(" ", "_").replace("-", "_")
    if method in {"harmony", "harmony_polyrhythm"}:
        return level, stats
    return replace_note_gap_pauses_with_bridge_tiles(
        level,
        stats,
        max_tiles=int(kwargs.get("max_tiles", 0) or 0),
    )


def install_web_gap_bridge() -> None:
    """Install the Web-only wrapper without changing the shared desktop exporter."""
    from web import adofai as web_adofai

    web_adofai.build_adofai_level = build_adofai_level_with_gap_bridges
