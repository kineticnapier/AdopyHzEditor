from __future__ import annotations

from pathlib import Path
from mido import MidiFile, MidiTrack, Message, MetaMessage, bpm2tempo
from note_model import Note


def export_midi(notes: list[Note], path: str | Path, *, bpm: float = 120.0, ticks_per_beat: int = 480) -> None:
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage("set_tempo", tempo=bpm2tempo(bpm), time=0))

    ticks_per_sec = ticks_per_beat * bpm / 60.0
    events = []
    for n in notes:
        nn = n.normalized()
        if nn.duration <= 0:
            continue
        s = int(round(nn.start * ticks_per_sec))
        e = max(s + 1, int(round(nn.end * ticks_per_sec)))
        events.append((s, 1, nn))
        events.append((e, 0, nn))

    events.sort(key=lambda x: (x[0], x[1]))
    last = 0
    for tick, typ, n in events:
        delta = max(0, tick - last)
        last = tick
        if typ:
            track.append(Message("note_on", note=n.midi, velocity=n.velocity, time=delta))
        else:
            track.append(Message("note_off", note=n.midi, velocity=0, time=delta))

    track.append(MetaMessage("end_of_track", time=0))
    mid.save(str(path))
