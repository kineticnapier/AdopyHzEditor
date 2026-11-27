"""Append a generated Hz chart to the end of an existing ADOFAI level.

The existing level keeps its settings, tiles and events.  The generated
tiles follow its last tile so the chart plays on after it:

* Every generated angle is rotated by the existing level's last angle, so
  each turn, and with it the timing, is the same as in the generated chart.
* Twirl state is restored at the joint: the generated part always starts
  clockwise, like a fresh level.
* A SetSpeed at the joint sets the generated part's starting BPM, which a
  fresh level takes from ``settings.bpm``.

The join is not aligned with the song: the generated part starts when the
existing level ends.
"""

from __future__ import annotations

import json
from i18n import tr
from typing import Any

MIDSPIN = 999
DEFAULT_LEVEL_BPM = 100.0
# Events on the joint floor that only affected the travel after it.  The
# existing level has no travel after its last floor, so they are replaced.
_JOINT_REPLACED_EVENTS = {"SetSpeed", "Twirl"}


class AppendError(ValueError):
    """The existing level cannot be appended to."""


def _strip_trailing_commas(text: str) -> str:
    """Remove commas right before ``]`` or ``}`` outside strings.

    The ADOFAI editor writes them, so its files are not strict JSON.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    pending_comma: list[str] | None = None
    for ch in text:
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if pending_comma is not None:
            if ch.isspace():
                pending_comma.append(ch)
                continue
            if ch not in "]}":
                out.append(",")
            out.extend(pending_comma[1:])
            pending_comma = None
        if ch == ",":
            pending_comma = [","]
            continue
        if ch == '"':
            in_string = True
        out.append(ch)
    if pending_comma is not None:
        out.extend(pending_comma)
    return "".join(out)


def load_adofai_text(text: str) -> dict[str, Any]:
    """Parse an .adofai file's text (BOM and trailing commas allowed)."""
    text = text.lstrip("﻿")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            data = json.loads(_strip_trailing_commas(text))
        except json.JSONDecodeError as exc:
            raise AppendError(tr("msg.chart_file_unreadable", error=exc)) from exc
    if not isinstance(data, dict):
        raise AppendError(tr("msg.chart_bad_format"))
    return data


def _floor_count(level: dict[str, Any]) -> int:
    return len(level["angleData"]) + 1


def _effective_last_angle(angles: list[Any]) -> float:
    """Absolute direction of the last floor, seen by the tile after it."""
    turn = 0.0
    for value in reversed(angles):
        number = float(value)
        if number == MIDSPIN:
            turn += 180.0
            continue
        return (number + turn) % 360.0
    return turn % 360.0


def _twirls_before(actions: list[dict[str, Any]], floor: int) -> int:
    return sum(1 for a in actions if a.get("eventType") == "Twirl" and int(a.get("floor", -1)) < floor)


def append_level(base: dict[str, Any], generated: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(merged_level, info)``; neither input is modified."""
    if not isinstance(base.get("angleData"), list):
        if "pathData" in base:
            raise AppendError(tr("msg.chart_path_data"))
        raise AppendError(tr("msg.chart_no_angle_data"))
    base_angles = list(base["angleData"])
    gen_angles = list(generated["angleData"])
    joint = len(base_angles)  # last floor of the existing level
    rotation = _effective_last_angle(base_angles)

    merged = json.loads(json.dumps(base))
    merged["angleData"] = base_angles + [
        value if float(value) == MIDSPIN else round((float(value) + rotation) % 360.0, 9)
        for value in gen_angles
    ]

    base_actions = [a for a in merged.get("actions", []) if isinstance(a, dict)]
    gen_actions = [json.loads(json.dumps(a)) for a in generated.get("actions", []) if isinstance(a, dict)]

    kept_base = [
        a
        for a in base_actions
        if not (int(a.get("floor", -1)) == joint and a.get("eventType") in _JOINT_REPLACED_EVENTS)
    ]
    gen_floor0_twirls = sum(
        1 for a in gen_actions if a.get("eventType") == "Twirl" and int(a.get("floor", -1)) == 0
    )
    gen_floor0_speed = any(
        a.get("eventType") == "SetSpeed" and int(a.get("floor", -1)) == 0 for a in gen_actions
    )
    shifted = []
    for action in gen_actions:
        floor = int(action.get("floor", 0))
        if floor == 0 and action.get("eventType") == "Twirl":
            continue  # folded into the joint twirl below
        action["floor"] = floor + joint
        shifted.append(action)

    joint_events: list[dict[str, Any]] = []
    # Direction entering the generated part must match a fresh level.
    if (gen_floor0_twirls - _twirls_before(kept_base, joint)) % 2:
        joint_events.append({"floor": joint, "eventType": "Twirl"})
    start_bpm = float(generated.get("settings", {}).get("bpm", DEFAULT_LEVEL_BPM))
    if not gen_floor0_speed:
        joint_events.append(
            {
                "floor": joint,
                "eventType": "SetSpeed",
                "speedType": "Bpm",
                "beatsPerMinute": round(start_bpm, 6),
                "bpmMultiplier": 1,
            }
        )

    actions = kept_base + joint_events + shifted
    actions.sort(key=lambda a: int(a.get("floor", 0)))  # stable: keeps order within a floor
    merged["actions"] = actions

    decorations = [json.loads(json.dumps(d)) for d in generated.get("decorations", []) if isinstance(d, dict)]
    for decoration in decorations:
        if "floor" in decoration:
            decoration["floor"] = int(decoration["floor"]) + joint
    if decorations:
        merged["decorations"] = list(merged.get("decorations", [])) + decorations

    warnings = []
    if any(a.get("eventType") == "MultiPlanet" for a in base_actions):
        warnings.append(tr("msg.chart_multiplanet"))
    info = {
        "baseFloors": _floor_count(base),
        "addedFloors": len(gen_angles),
        "jointFloor": joint,
        "rotation": rotation,
        "warnings": warnings,
    }
    return merged, info
