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


## Stable17 修正

- タンギング処理を廃止しました。
- ADOFAI出力ダイアログから `Tongue seconds` / `Tongue ratio` を削除しました。
- 出力時にノート末尾を自動で短くする処理は行いません。
- ノート長は、エディタ上で書いた長さをそのまま使います。

音を切りたい場合は、エディタ上でノート自体を短くしてください。


## Stable18 修正

- ADOFAI出力ダイアログで `Angle Compression` を最初の選択肢にしました。
- ADOFAI出力時の `Base BPM` 初期値は、プロジェクト側の `BPM` を使うようにしました。
- プロジェクト保存時にBPM/Offsetなどの設定を保存するようにしました。
  - `BPM`
  - `Offset`
  - `Grid`
  - `Metronome`
  - `Snap`
  - `Snap div`
  - `Oct`
  - 音量系
  - 再生速度
- プロジェクト読み込み時にこれらの設定を復元するようにしました。
- `Oct` がMIDI出力/ADOFAI出力にも効くように修正しました。
- 速度変化は、Hzセクション開始floorに置く方針を維持しています。
  - floor 0には置きません。
  - Base BPMのSetSpeedは重ねません。


## Stable19 修正

- ADOFAI出力の `SetSpeed` 配置を1タイル後ろへずらしました。
  - これにより、角・遷移タイルではなく、その次のHzセクション開始タイル側に速度変化が置かれます。
  - floor 0には引き続き `SetSpeed` を置きません。
- `Oct` がMIDI/ADOFAI出力へ確実に反映されるよう、出力用ノート生成処理を再確認・補強しました。
- 出力方式の最初の選択肢は `Angle Compression` のままです。


## Stable20 読み込み高速化

音声読み込みまわりを軽くしました。

- CQT解析に `librosa.hybrid_cqt` を優先使用するようにしました。
- CQTキャッシュを非圧縮 `.npz` に変更しました。
  - キャッシュ容量は増えますが、2回目以降の読み込みが速くなります。
- 再生用音声の読み込みを、スペクトログラム表示後に遅延実行するようにしました。
  - 先に編集画面が表示されます。
  - 再生は `Playback ready` 表示後に安定します。
- `Analysis` プロファイルを追加しました。

Analysis:

| Profile | 内容 |
|---|---|
| Fast | C1-C7、粗め、最速寄り |
| Normal | バランス設定 |
| Full C0-C10 | 広い音域、重い |

一度解析した音声は `~/.adopyhzeditor_cache` にキャッシュされます。
キャッシュ削除は安全ですが、次回読み込みは再解析になります。


## Stable21 修正

- 新しい音声ファイルを開いたとき、前のノートが引き継がれないようにしました。
  - `Open Audio` 時にノート一覧を空にします。
- 保存していない変更がある状態で新しい音声ファイルを開く前に警告を出すようにしました。
- 保存していない変更がある状態でプロジェクトを読み込む前にも警告を出すようにしました。
- ウィンドウを閉じるときにも保存確認を出すようにしました。
- ノートやプロジェクト設定を変更すると、タイトルに `*` が付きます。
- 保存後・読み込み後は未保存状態を解除します。


## Stable22 修正

- ノート選択判定を狭くしました。
  - 以前は近くのノートを拾っていました。
  - 今回から、ノート矩形に直接触れたときだけ選択します。
- 複数選択後の削除を補強しました。
  - `Delete` は選択中ノートをまとめて削除します。
  - 複数選択中に選択済みノートを右クリック削除した場合も、選択中ノートをまとめて削除します。
- ADOFAI出力の `Change x mode` に `lowest_floor` を追加しました。

`lowest_floor`:

```text
各ノートの x = floor(Keycount) を計算
その中で一番小さい x に全ノートを固定

例:
x = 3, 4, 5, 6
=> 全ノート change_x = 3
```

`floor` は従来通り、各ノートごとに `floor(Keycount)` を使います。


## Stable23 表示改善

WaveTone寄りに読みやすくする表示モードを追加しました。

- `Display` を追加
  - `wavetone`: 黒背景に、弱い成分を落として色付きブロック表示
  - `ridge`: ピッチ方向の山だけを残す表示
  - `smooth`: 従来のなめらかなスペクトログラム
- `wavetone` カラーマップを追加
  - black → blue → cyan → green → yellow → red
- ピッチ方向の補助線を追加
  - 半音ごとに薄い線
  - C音/オクターブごとに強い線
- 左軸をC0/C1/...のような音名表示に変更
- 初期表示を `Display=wavetone`, `Colormap=wavetone`, `Contrast=1.15` に変更

見づらい場合の目安:

```text
Display = wavetone
Colormap = wavetone
Contrast = 1.0～1.6
Gamma = 0.6～1.0
Harmonics = soft
```

細かい倍音やノイズまで確認したい場合は `Display=smooth` に戻してください。
