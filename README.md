# AdopyHzEditor

AdopyHzEditor is a spectrogram-based editor for creating notes by hand, then exporting them as MIDI or ADOFAI Hz Charts.

It is designed for the workflow:

```text
Audio file
↓
CQT spectrogram
↓
Manual note tracing/editing
↓
MIDI export / ADOFAI Hz Chart export
```

This is not a fully automatic transcription tool. It is a manual editor that helps you read frequencies from audio and place notes accurately.

## Features

- Audio loading: WAV / OGG / MP3 / FLAC / M4A, depending on the local decoder environment
- CQT spectrogram display from C0 to C10
- Manual note creation by dragging on the spectrogram
- Multiple note selection
- Copy / cut / paste
- Undo / redo
- Note movement by dragging or shortcut
- Grid generation from BPM and offset
- Grid snapping
- Metronome
- Playback speed control
- Preview playback for written notes
- Octave shifting for preview, MIDI export, and ADOFAI export
- MIDI export
- ADOFAI Hz Chart export
- Project save/load with `.adopyhz`

## Installation

Use Python 3.11 or newer if possible.

```bash
pip install -r requirements.txt
```

If OGG or MP3 playback/loading is unstable on your environment, convert the audio file to WAV first.

```bash
ffmpeg -i input.ogg input.wav
```

## Run

```bash
python main.py
```

## Basic usage

1. Open an audio file.
2. Adjust the spectrogram view with the time and pitch controls.
3. Drag on the spectrogram to create notes.
4. Use playback and note preview to check the result.
5. Export as MIDI or ADOFAI Hz Chart.

## Project files

AdopyHzEditor uses:

```text
.adopyhz
```

Older project files such as `.ahe.json` and `.json` are still accepted for loading, but new project saves should use `.adopyhz`.

## Main controls

| Control | Action |
|---|---|
| Left drag | Create note |
| Left click near note | Select note |
| Left click empty area | Move playhead |
| Ctrl + left click | Add/remove note from selection |
| Shift + left click | Range selection |
| Right click | Delete nearest note |
| Delete | Delete selected notes |
| Ctrl + A | Select all notes |
| Esc | Clear selection |

## Editing shortcuts

| Shortcut | Action |
|---|---|
| Ctrl + C | Copy selected notes |
| Ctrl + X | Cut selected notes |
| Ctrl + V | Paste notes at playhead |
| Ctrl + Z | Undo |
| Ctrl + Y | Redo |
| Ctrl + Shift + Z | Redo |
| Ctrl + Shift + Left / Right | Move selected notes left/right |
| Ctrl + Shift + Up / Down | Move selected notes up/down by semitone |

If Snap is enabled, horizontal note movement snaps to the BPM/offset grid.

## Playback shortcuts

| Shortcut | Action |
|---|---|
| Space | Play / pause |
| Ctrl + Space | Stop |
| Left / Right | Seek by 1 second |
| Shift + Left / Right | Seek by 5 seconds |

## View controls

| Control | Meaning |
|---|---|
| Time | Horizontal scroll |
| Visible | Visible time width |
| Pitch bottom | Lowest visible pitch |
| Visible notes | Vertical zoom amount |
| Fit | Show the whole spectrogram |
| Enhance | Normalize the spectrogram for readability |
| Harmonics | Hide harmonic-like upper frequencies: off / soft / strong |
| Contrast | Spectrogram contrast |
| Gamma | Spectrogram brightness curve |
| Colormap | Spectrogram color map |

## Audio and note preview controls

| Control | Meaning |
|---|---|
| Song Vol | Original audio volume |
| Speed | Playback speed |
| Note Vol | Written-note preview volume |
| Oct | Octave shift for preview, MIDI export, and ADOFAI export |
| Metro Vol | Metronome volume |

`Oct` does not move notes on the screen. It only changes the pitch used for:

```text
preview sound
MIDI export
ADOFAI Hz Chart export
```

For example:

```text
Oct = +1
screen note position: unchanged
preview sound: one octave higher
MIDI export: one octave higher
ADOFAI export: one octave higher
```

## Grid, snap, and metronome

| Control | Meaning |
|---|---|
| Grid | Show BPM/offset guide lines |
| Metronome | Enable click sound |
| BPM | Grid/metronome BPM |
| Offset | Grid/metronome offset in milliseconds |
| Snap | Snap created/moved notes to the grid |
| Snap div | Number of subdivisions per beat |

Examples:

```text
Snap div = 1  -> snap to beats
Snap div = 4  -> snap to quarter-beat positions
Snap div = 8  -> snap to eighth-beat positions
```

## ADOFAI Hz Chart export

The exporter supports two methods.

### Direct 180°

```text
BPM = Hz * 60
```

This is the visually safer method. It mostly produces straight 180-degree tiles.

Fractional tiles are handled by stretching one final tile with adjusted BPM.

### Angle Compression

This follows the corrected Keycount formula:

```text
beat_count = note_duration_seconds * Base BPM / 60
keycount   = Hz * 60 * beat_count / Base BPM
x_tiles    = floor(keycount)
change_x   = x_tiles or user-specified value
angle      = 180 * change_x / keycount
BPM        = (Hz * 60) * (angle / 180)
```

Output:

```text
x_tiles tiles:
  relative angle = angle

final fractional tile:
  relative angle = angle * fractional_part(keycount)
```

Export starts at floor 1. Floor 0 is kept clean and does not receive `SetSpeed`.

The exported chart time is normalized to the first written note. If the first note in the editor starts at 50 seconds, the exported chart treats that note as the start.

## Notes about ADOFAI export

ADOFAI is a single-track chart format here. Overlapping notes are serialized.

Large Hz Charts can produce a lot of tiles. High notes and long notes can make the exported `.adofai` file very large.

## Cache

Spectrogram analysis results may be cached under the user's home directory, such as:

```text
.audiohzeditor_cache_stable
```

Deleting the cache is safe. It only makes future audio loading slower until the cache is rebuilt.

## Repository structure

```text
AdopyHzEditor/
├─ main.py              # Main PySide6 UI
├─ editor_view.py       # Spectrogram and note editor view
├─ audio_analysis.py    # Audio loading and CQT spectrogram generation
├─ audio_player.py      # Playback, metronome, and note preview
├─ note_model.py        # Note data model
├─ export_midi.py       # MIDI export
├─ export_adofai.py     # ADOFAI Hz Chart export
├─ project_io.py        # .adopyhz project save/load
├─ requirements.txt
├─ README.md
└─ .gitignore
```

## Known limitations

- This is not automatic transcription.
- Dense full songs can make the spectrogram noisy.
- Harmonic suppression is a display aid, not real source separation.
- Playback speed uses simple resampling and may change pitch.
- Extremely large note counts or huge ADOFAI exports can become slow.
