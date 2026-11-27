"""Find stretches of an ADOFAI level that are too fast to play by hand.

KPS (keys per second) of a tile is one over the time the planet takes to
travel from it to the next tile, the number ADOFAI shows next to TBPM
(TBPM / 60).  Hz charts often go far past what a person can hit, so the
exporter warns about the stretches above ``HUMAN_KPS_LIMIT``.
"""

from __future__ import annotations

from collections import defaultdict
from i18n import tr
from typing import Any

HUMAN_KPS_LIMIT = 200.0
MIDSPIN = 999
# Ranges listed in the warning; the rest are only counted.
MAX_LISTED_RANGES = 5
# KPS is averaged over this many hits, so one leftover sliver of a tile at a
# note boundary does not read as thousands of KPS.
KPS_WINDOW_TILES = 4


def tile_travel_seconds(level: dict[str, Any]) -> list[tuple[int, float, float]]:
    """``(floor, start_seconds, travel_seconds)`` for every tile that is hit.

    Follows SetSpeed (Bpm and Multiplier), Twirl, Pause and midspins; other
    events do not change the timing.  Times count from floor 0.
    """
    angles = [0.0] + [float(a) for a in level.get("angleData", [])]
    bpm = float(level.get("settings", {}).get("bpm", 100.0) or 100.0)
    events: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for action in level.get("actions", []):
        if isinstance(action, dict):
            events[int(action.get("floor", 0))].append(action)

    clockwise = True
    direction = angles[0]  # where the planet arrived from, as an absolute angle
    out: list[tuple[int, float, float]] = []
    t = 0.0
    floor = 0
    while floor < len(angles) - 1:
        pause_beats = 0.0
        for action in events.get(floor, ()):
            kind = action.get("eventType")
            if kind == "SetSpeed":
                if action.get("speedType", "Bpm") == "Multiplier":
                    bpm *= float(action.get("bpmMultiplier", 1.0))
                else:
                    bpm = float(action.get("beatsPerMinute", bpm))
            elif kind == "Twirl":
                clockwise = not clockwise
            elif kind == "Pause":
                pause_beats += float(action.get("duration", 0.0))
        nxt = floor + 1
        turn_back = 0.0
        # A midspin tile is passed instantly and reverses the direction.
        while nxt < len(angles) and angles[nxt] == MIDSPIN:
            turn_back += 180.0
            nxt += 1
        if nxt >= len(angles):
            break
        here = (direction + turn_back) % 360.0
        turn = (here + 180.0 - angles[nxt]) % 360.0
        if not clockwise:
            turn = (360.0 - turn) % 360.0
        if turn <= 1e-9:
            turn = 360.0
        seconds = (turn / 180.0 + pause_beats) * 60.0 / max(bpm, 1e-9)
        out.append((floor, t, seconds))
        t += seconds
        direction = angles[nxt]
        floor = nxt
    return out


def kps_report(
    level: dict[str, Any],
    *,
    limit: float = HUMAN_KPS_LIMIT,
    first_floor: int = 0,
) -> dict[str, Any]:
    """Stretches of tiles faster than ``limit`` KPS, from ``first_floor`` on.

    KPS is averaged over windows of ``KPS_WINDOW_TILES`` hits, leaving out
    the shortest one, and a tile takes the fastest window it is part of.
    Each range gives its first and last floor, its start time from floor 0
    (the chart's own time, without the song offset), and its highest KPS.
    """
    tiles = [(floor, start, seconds) for floor, start, seconds in tile_travel_seconds(level) if floor >= first_floor]
    window = max(1, min(KPS_WINDOW_TILES, len(tiles)))
    window_kps: list[float] = []
    for j in range(len(tiles) - window + 1):
        durations = [seconds for _f, _s, seconds in tiles[j : j + window]]
        if len(durations) >= 3:
            # The shortest one may be a sliver left at a note boundary.
            durations.remove(min(durations))
        total = sum(durations)
        window_kps.append(len(durations) / total if total > 0 else 0.0)
    ranges: list[dict[str, Any]] = []
    max_kps = 0.0
    over = 0
    for i, (floor, start, _seconds) in enumerate(tiles):
        # A tile is as fast as the fastest window it is part of.
        kps = max(window_kps[max(0, i - window + 1) : i + 1] or [0.0])
        max_kps = max(max_kps, kps)
        if kps <= limit:
            continue
        over += 1
        last = ranges[-1] if ranges else None
        if last and last["_next"] == floor:
            last["endFloor"] = floor
            last["maxKps"] = max(last["maxKps"], kps)
        else:
            ranges.append({"startFloor": floor, "endFloor": floor, "startSeconds": start, "maxKps": kps})
        ranges[-1]["_next"] = floor + 1
    for item in ranges:
        item.pop("_next")
        item["startSeconds"] = round(item["startSeconds"], 3)
        item["maxKps"] = round(item["maxKps"], 1)
    return {
        "limit": float(limit),
        "maxKps": round(max_kps, 1),
        "tilesOver": over,
        "ranges": ranges,
    }


def kps_warning(report: dict[str, Any]) -> str | None:
    """A short Japanese warning for the status line, or None if all is playable."""
    ranges = report.get("ranges") or []
    if not ranges:
        return None
    listed = tr("msg.list_sep").join(
        tr(
            "msg.kps_range",
            start=r["startFloor"],
            end=r["endFloor"],
            seconds=f"{r['startSeconds']:.2f}",
            kps=f"{r['maxKps']:.0f}",
        )
        for r in ranges[:MAX_LISTED_RANGES]
    )
    rest = len(ranges) - MAX_LISTED_RANGES
    if rest > 0:
        listed += tr("msg.kps_more", count=rest)
    return tr(
        "msg.kps_warning",
        limit=f"{report['limit']:.0f}",
        count=len(ranges),
        max=f"{report['maxKps']:.0f}",
        listed=listed,
    )
