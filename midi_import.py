from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import bisect
import struct

from note_model import Note


@dataclass
class MidiImportResult:
    notes: list[Note]
    format_type: int
    track_count: int
    ppq: int
    tempo_events: list[tuple[int, int]]
    duration_seconds: float

    @property
    def note_count(self) -> int:
        return len(self.notes)


class MidiImportError(ValueError):
    pass


def _read_u16(data: bytes, pos: int) -> tuple[int, int]:
    if pos + 2 > len(data):
        raise MidiImportError("Unexpected end of file while reading uint16")
    return struct.unpack_from(">H", data, pos)[0], pos + 2


def _read_u32(data: bytes, pos: int) -> tuple[int, int]:
    if pos + 4 > len(data):
        raise MidiImportError("Unexpected end of file while reading uint32")
    return struct.unpack_from(">I", data, pos)[0], pos + 4


def _read_varlen(data: bytes, pos: int, end: int) -> tuple[int, int]:
    value = 0
    for _ in range(4):
        if pos >= end:
            raise MidiImportError("Unexpected end of track while reading variable length value")
        b = data[pos]
        pos += 1
        value = (value << 7) | (b & 0x7F)
        if not (b & 0x80):
            return value, pos
    raise MidiImportError("Invalid MIDI variable length value")


def _tick_to_seconds_converter(tempo_events: list[tuple[int, int]], ppq: int):
    events = sorted((int(t), int(us)) for t, us in tempo_events)
    if not events or events[0][0] != 0:
        events.insert(0, (0, 500000))

    ticks: list[int] = []
    seconds_at: list[float] = []
    tempos: list[int] = []

    current_tick = 0
    current_seconds = 0.0
    current_tempo = events[0][1]

    for tick, tempo in events:
        tick = max(0, int(tick))
        if tick < current_tick:
            continue
        current_seconds += (tick - current_tick) * current_tempo / 1_000_000.0 / ppq
        current_tick = tick
        current_tempo = int(tempo)
        ticks.append(current_tick)
        seconds_at.append(current_seconds)
        tempos.append(current_tempo)

    def convert(tick: int) -> float:
        tick = max(0, int(tick))
        i = bisect.bisect_right(ticks, tick) - 1
        if i < 0:
            return tick * 500000 / 1_000_000.0 / ppq
        return seconds_at[i] + (tick - ticks[i]) * tempos[i] / 1_000_000.0 / ppq

    return convert


def _parse_track(track_data: bytes, track_index: int) -> tuple[list[dict[str, Any]], list[tuple[int, int]], int]:
    pos = 0
    end = len(track_data)
    abs_tick = 0
    running_status: int | None = None
    events: list[dict[str, Any]] = []
    tempo_events: list[tuple[int, int]] = []
    max_tick = 0

    while pos < end:
        delta, pos = _read_varlen(track_data, pos, end)
        abs_tick += delta
        max_tick = max(max_tick, abs_tick)

        if pos >= end:
            break

        status = track_data[pos]
        if status < 0x80:
            if running_status is None:
                raise MidiImportError(f"Running status without previous status in track {track_index}")
            status = running_status
        else:
            pos += 1
            if 0x80 <= status <= 0xEF:
                running_status = status

        if status == 0xFF:
            if pos >= end:
                raise MidiImportError(f"Truncated meta event in track {track_index}")
            meta_type = track_data[pos]
            pos += 1
            length, pos = _read_varlen(track_data, pos, end)
            payload = track_data[pos:pos + length]
            if len(payload) != length:
                raise MidiImportError(f"Truncated meta payload in track {track_index}")
            pos += length

            if meta_type == 0x51 and length == 3:
                tempo = (payload[0] << 16) | (payload[1] << 8) | payload[2]
                tempo_events.append((abs_tick, tempo))
            elif meta_type == 0x2F:
                break
            continue

        if status in (0xF0, 0xF7):
            length, pos = _read_varlen(track_data, pos, end)
            pos += length
            if pos > end:
                raise MidiImportError(f"Truncated SysEx event in track {track_index}")
            continue

        event_type = status & 0xF0
        channel = status & 0x0F

        data_len = 1 if event_type in (0xC0, 0xD0) else 2
        if pos + data_len > end:
            raise MidiImportError(f"Truncated channel event in track {track_index}")
        data1 = track_data[pos]
        data2 = track_data[pos + 1] if data_len == 2 else 0
        pos += data_len

        if event_type == 0x90:
            if data2 > 0:
                events.append({
                    "tick": abs_tick,
                    "type": "note_on",
                    "channel": channel,
                    "note": data1,
                    "velocity": data2,
                    "track": track_index,
                })
            else:
                events.append({
                    "tick": abs_tick,
                    "type": "note_off",
                    "channel": channel,
                    "note": data1,
                    "velocity": 0,
                    "track": track_index,
                })
        elif event_type == 0x80:
            events.append({
                "tick": abs_tick,
                "type": "note_off",
                "channel": channel,
                "note": data1,
                "velocity": data2,
                "track": track_index,
            })

    return events, tempo_events, max_tick


def import_midi(path: str | Path, *, min_duration_seconds: float = 0.001) -> MidiImportResult:
    data = Path(path).read_bytes()
    pos = 0

    if data[:4] != b"MThd":
        raise MidiImportError("Not a standard MIDI file: missing MThd header")
    pos = 4
    header_len, pos = _read_u32(data, pos)
    if header_len < 6:
        raise MidiImportError("Invalid MIDI header length")
    header_end = pos + header_len
    if header_end > len(data):
        raise MidiImportError("Truncated MIDI header")

    format_type, pos = _read_u16(data, pos)
    track_count, pos = _read_u16(data, pos)
    division, pos = _read_u16(data, pos)
    pos = header_end

    if division & 0x8000:
        raise MidiImportError("SMPTE-time MIDI files are not supported yet")
    ppq = int(division)
    if ppq <= 0:
        raise MidiImportError("Invalid MIDI PPQ division")

    all_events: list[dict[str, Any]] = []
    tempo_events: list[tuple[int, int]] = [(0, 500000)]
    max_tick = 0

    for track_index in range(track_count):
        if pos + 8 > len(data):
            raise MidiImportError(f"Missing track {track_index + 1}/{track_count}")
        chunk_id = data[pos:pos + 4]
        pos += 4
        length, pos = _read_u32(data, pos)
        if chunk_id != b"MTrk":
            # Unknown chunks are skipped for tolerance.
            pos += length
            continue
        track_data = data[pos:pos + length]
        if len(track_data) != length:
            raise MidiImportError(f"Truncated track {track_index}")
        pos += length

        events, tempos, track_max_tick = _parse_track(track_data, track_index)
        all_events.extend(events)
        tempo_events.extend(tempos)
        max_tick = max(max_tick, track_max_tick)

    tempo_events = sorted(tempo_events, key=lambda x: x[0])
    tick_to_seconds = _tick_to_seconds_converter(tempo_events, ppq)

    # Sort note_off before note_on at the same tick so repeated notes do not
    # accidentally overlap forever.
    type_order = {"note_off": 0, "note_on": 1}
    all_events.sort(key=lambda e: (int(e["tick"]), int(e.get("track", 0)), type_order.get(str(e["type"]), 9)))

    active: dict[tuple[int, int], list[dict[str, Any]]] = {}
    notes: list[Note] = []

    for event in all_events:
        key = (int(event["channel"]), int(event["note"]))
        if event["type"] == "note_on":
            active.setdefault(key, []).append(event)
            continue

        stack = active.get(key)
        if not stack:
            continue

        start_event = stack.pop(0)
        start_tick = int(start_event["tick"])
        end_tick = int(event["tick"])
        if end_tick <= start_tick:
            continue

        start = tick_to_seconds(start_tick)
        end = tick_to_seconds(end_tick)
        if end - start < float(min_duration_seconds):
            end = start + float(min_duration_seconds)

        notes.append(Note(
            start=start,
            end=end,
            midi=float(event["note"]),
            velocity=int(start_event.get("velocity", 100)),
        ).normalized())

    notes.sort(key=lambda n: (n.start, n.midi, n.end))
    duration_seconds = max([tick_to_seconds(max_tick)] + [n.end for n in notes] + [0.0])

    return MidiImportResult(
        notes=notes,
        format_type=int(format_type),
        track_count=int(track_count),
        ppq=int(ppq),
        tempo_events=tempo_events,
        duration_seconds=float(duration_seconds),
    )
