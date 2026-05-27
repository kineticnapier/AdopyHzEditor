# AdopyHzEditor

AdopyHzEditor is a spectrogram-based editor for manually tracing notes from audio and exporting them as MIDI or ADOFAI Hz Charts.

It is designed for this workflow:

```text
Audio file
↓
CQT spectrogram
↓
Manual note tracing / curve editing
↓
Preview playback
↓
MIDI export / ADOFAI Hz Chart export
```

This is not a fully automatic transcription tool. It is a manual editor that helps you read frequencies from audio, place notes accurately, and convert them into chart data.

## Features

- Audio loading: WAV / OGG / MP3 / FLAC / M4A, depending on the local decoder environment
- CQT spectrogram display from C0 to C10
- Manual note creation by dragging on the spectrogram
- Curve / glide note creation
- Glide interpolation modes
- Multiple note selection
- Copy / cut / paste
- Undo / redo
- Note movement by dragging or shortcuts
- BPM/offset grid generation
- Grid snapping
- Metronome
- Playback speed control
- Original audio volume and note preview volume controls
- Octave shift for preview, MIDI export, and ADOFAI export
- Harmonic suppression display modes
- MIDI export
- ADOFAI Hz Chart export
- ADOFAI Hz/angle debug preview
- Project save/load with `.adopyhz`

## Installation

Use Python 3.11 or newer if possible.

```bash
pip install -r requirements.txt
```

If OGG or MP3 loading/playback is unstable in your environment, convert the audio file to WAV first.

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
| Alt + left drag | Create Curve / Glide note |
| Left click note | Select note |
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
| Ctrl + Alt + A | Apply Target Angle to selected notes |

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

Example:

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

## Curve / Glide notes

Curve/Glide notes are used for continuously changing pitches.

Create a Curve/Glide note with:

```text
Alt + left drag
```

Interpolation mode is selected with `Interp`.

| Mode | Meaning |
|---|---|
| `bezier_pitch` | Bezier interpolation in MIDI/semitone space. This is the original/default behavior. |
| `linear_pitch` | Linear interpolation in MIDI/semitone space. Pitch ratio changes smoothly. |
| `linear_hz` | Linear interpolation in Hz space. Physical frequency changes at a constant speed. |
| `bezier_hz` | Bezier interpolation in Hz space. Useful for effect-like glides. |

To change existing Curve/Glide notes:

```text
1. Select Curve/Glide notes
2. Choose Interp
3. Press Apply Interp
```

## MIDI export

MIDI export uses the written notes and the current `Oct` setting.

Curve/Glide notes are exported by sampling the curve into short pitch steps.

## ADOFAI Hz Chart export

ADOFAI export is designed for making Hz Charts. Export starts at floor 1. Floor 0 is kept as a clean starter tile and does not receive `SetSpeed`.

The exported chart time is normalized to the first written note. If the first note in the editor starts at 50 seconds, the exported chart treats that note as the start.

### Export methods

AdopyHzEditor currently supports three ADOFAI export methods.

## Angle Compression

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

`Change x mode` controls how `change_x` is chosen:

| Mode | Meaning |
|---|---|
| `floor` | Use `floor(keycount)` for each note |
| `lowest_floor` | Use the smallest `floor(keycount)` among all notes |
| `round` | Use `round(keycount)` |
| `ceil` | Use `ceil(keycount)` |
| `fixed` | Use the value from `Fixed change x` |

## Direct 180°

```text
BPM = Hz * 60
```

This is the visually safer method. It mostly produces straight 180-degree tiles.

Fractional tiles are handled by stretching one final tile with adjusted BPM.

## Angle-only

Angle-only uses one global BPM and represents pitch with tile angles only.

```text
HzBPM = Hz * 60
angle = AngleOnlyBPM * 180 / HzBPM
```

So:

```text
angle = AngleOnlyBPM * 180 / (Hz * 60)
```

Example:

```text
Angle-only BPM = 1600
Hz = 440

angle = 1600 * 180 / (440 * 60)
      = 10.909090...°
```

`Angle-only BPM` is written to `settings.bpm`. Per-note `SetSpeed` events are not generated unless final-tile visual correction requires them.

If angles are too small and the chart looks too dense, increase `Angle-only BPM`.

## Target Angle override

Target Angle is a per-note override for Angle Compression export.

```text
target_angle = None:
  use automatic angle calculation

target_angle = 165:
  use 165° for that note/zip
```

Angle-only ignores Target Angle because, in Angle-only mode, the angle itself determines the pitch.

## Final tile mode

Final tile mode controls the final fractional tile.

| Mode | Meaning |
|---|---|
| `scaled` | Use the mathematically scaled final angle |
| `cardinal` | Snap the final absolute direction toward a cardinal/grid direction |
| `custom` | Use `Custom final angle` |

Use `custom` with `180°` if you want the final tile to behave like a straight final tile.

If a visual correction changes the final tile duration, the exporter adds a compensating `SetSpeed` event.

## Phase-continuous glide export

`Phase-continuous glide` prevents Curve/Glide notes from being exported as many short fixed-Hz notes.

Instead, the curve is treated as a continuous frequency function:

```text
f(t) = frequency at time t
phase(t) = ∫ f(t) dt
```

Tiles are placed when phase crosses:

```text
1, 2, 3, ... cycles
```

For Angle-only, each tile angle is calculated from the actual time interval:

```text
dt = next_tile_time - previous_tile_time
angle = dt * AngleOnlyBPM * 180 / 60
```

Supported methods:

| Method | Phase-continuous behavior |
|---|---|
| Angle-only | Uses variable angles, usually without per-tile SetSpeed |
| Direct 180° | Keeps 180° tiles and adds per-tile SetSpeed |
| Angle Compression | Uses the chosen main angle and adds per-tile SetSpeed |

`Angle-only + Phase-continuous glide` is the lightest option.

`Direct 180°` and `Angle Compression` with Phase-continuous glide can create many `SetSpeed` events.

## ADOFAI Debug Preview

The ADOFAI export dialog has a `Debug Preview` button.

It shows per-note/export calculations before writing the `.adofai` file.

Useful columns include:

```text
method
keycount
whole / frac
change_x
angle / angle_min / angle_max
auto_angle
target_angle
target_angle_used
target_angle_ignored
phase_continuous
effective_bpm
final_bpm
tiles_est
final_visual_used
warning
```

The preview can be copied as TSV or CSV.

## Notes about ADOFAI export

ADOFAI is a single-track chart format here. Overlapping notes are serialized.

Large Hz Charts can produce a lot of tiles. High notes, long notes, phase-continuous curves, and per-tile `SetSpeed` modes can make the exported `.adofai` file very large.

## Cache

Spectrogram analysis results may be cached under the user's home directory, such as:

```text
.adopyhzeditor_cache
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
- Direct 180° / Angle Compression with Phase-continuous glide can generate many `SetSpeed` events.
