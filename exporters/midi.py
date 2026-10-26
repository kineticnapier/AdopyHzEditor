from __future__ import annotations

from pathlib import Path
from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo
from core.note_model import Note


def _merged_note_intervals(notes: list[Note]) -> list[tuple[float, float, int, int]]:
    """Union overlapping intervals per emitted MIDI key.

    Standard MIDI note-off messages do not carry an identity. Emitting two
    overlapping instances of the same channel/key lets the first note-off cut
    the second note short in many players, so export their audible union.
    """
    by_key: dict[int, list[tuple[float, float, int]]] = {}
    for note in notes:
        for segment in note.sample_fixed_segments(max_seconds=0.030, max_pitch_step=0.25):
            n = segment.normalized()
            if n.duration <= 0:
                continue
            key = max(0, min(127, int(round(n.midi))))
            by_key.setdefault(key, []).append((n.start, n.end, n.velocity))

    merged: list[tuple[float, float, int, int]] = []
    for key, intervals in by_key.items():
        intervals.sort(key=lambda item: (item[0], item[1]))
        start, end, velocity = intervals[0]
        for next_start, next_end, next_velocity in intervals[1:]:
            if next_start <= end + 1e-9:
                end = max(end, next_end)
                velocity = max(velocity, next_velocity)
            else:
                merged.append((start, end, key, velocity))
                start, end, velocity = next_start, next_end, next_velocity
        merged.append((start, end, key, velocity))
    return sorted(merged, key=lambda item: (item[0], item[2], item[1]))


def export_midi(notes: list[Note], path: str | Path, *, bpm: float = 120.0, ticks_per_beat: int = 480) -> None:
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage("set_tempo", tempo=bpm2tempo(bpm), time=0))

    ticks_per_sec = ticks_per_beat * bpm / 60.0
    events = []
    for start, end, key, velocity in _merged_note_intervals(notes):
        s = int(round(start * ticks_per_sec))
        e = max(s + 1, int(round(end * ticks_per_sec)))
        events.append((s, 1, key, velocity))
        events.append((e, 0, key, velocity))

    events.sort(key=lambda x: (x[0], x[1]))
    last = 0
    for tick, typ, key, velocity in events:
        delta = max(0, tick - last)
        last = tick
        if typ:
            track.append(Message("note_on", note=key, velocity=velocity, time=delta))
        else:
            track.append(Message("note_off", note=key, velocity=0, time=delta))

    track.append(MetaMessage("end_of_track", time=0))
    mid.save(str(path))
