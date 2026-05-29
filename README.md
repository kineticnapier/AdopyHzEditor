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


## Stable24 判定補助

「合っているか分からない」問題を減らすための補助機能を追加しました。

- カーソル位置の音名/周波数/近くのピークをステータスバーに表示します。
  - 例: `Cursor 12.345s / C5 523.25Hz | nearby peak: D5 587.33Hz`
- 白いクロスヘアを追加しました。
  - 今どの時間・どの音程を見ているか分かりやすくなります。
- `Pitch Assist` を追加しました。
  - ノートをドラッグ作成するとき、近くの一番強いCQTピークへ音程を補正します。
  - 右の数値は探索範囲で、単位は半音です。
  - 初期値は `4` です。
- `Pitch Assist` の状態と探索範囲をプロジェクト設定に保存します。

使い方の目安:

```text
Display      = wavetone
Colormap     = wavetone
Harmonics    = soft
Pitch Assist = ON
探索範囲      = 3～5
```

完全な自動採譜ではありません。  
手でだいたいの位置にドラッグしたあと、近くの強い線へ吸着させるための補助です。


## Stable25 ADOFAI出力の見た目対策

Angle Compression は、相対角度が小さくなるとトラック形状が円や渦のようになりやすいです。  
これは計算ミスというより、短い角度を大量に置いたときのADOFAI側の幾何的な見た目です。

対策として、ADOFAI出力ダイアログに `Track visual` を追加しました。

| Track visual | 内容 |
|---|---|
| normal | 通常表示 |
| faint | トラックを薄く表示。初期値 |
| very faint | さらに薄く表示 |
| hidden | トラックをほぼ非表示 |

音を優先するHz Chartでは `faint` または `hidden` 推奨です。  
見た目も綺麗にしたい場合は `Direct 180°` の方が安定します。


## Stable26 修正

- ADOFAI出力ダイアログの `Track visual` 初期値を `normal` に戻しました。
- `faint` / `very faint` / `hidden` は必要なときだけ手動で選ぶ形にしました。


## Stable27 修正

- `Pitch Assist` を廃止しました。
  - ノート作成時に勝手に音程補正しません。
  - 手で置いた音程をそのまま使います。
- 代わりに、音源読み込み時の解析品質を上げる `Analysis = Precise` を追加しました。

`Precise` の内容:

```text
sr = 44100
hop_length = 512
CQT = 3 bins / semitone
表示は半音1行に畳み込み
```

これにより、次のような音を拾いやすくなります。

```text
・少しチューニングがズレた音
・ビブラートしている音
・CQTのbin境界に落ちて薄く見える音
・Normalでは見えにくいが、実際にはちゃんと鳴っている音
```

おすすめ設定:

```text
Analysis = Precise
Display = wavetone
Harmonics = off または soft
Contrast = 1.0～1.4
Gamma = 0.7～1.0
```

`Precise` は重いので、ラフ確認は `Normal`、確定作業は `Precise` 推奨です。


## Stable28 修正

- `Pitch Assist` 廃止後にツールバー側のUIだけ残っていた問題を修正しました。
- `MainWindow.apply_pitch_assist` が無いという起動時エラーを解消しました。


## Stable29 修正

- `editor_view.py` で `np` が未定義になり、カーソル移動時に `NameError: name 'np' is not defined` が大量に出る問題を修正しました。
- `Pitch Assist` 廃止後に残っていた自動音程補正用の内部参照を削除しました。
- カーソル位置の `nearby peak` 表示は残しています。
  - これは自動補正ではなく、確認用の表示だけです。


## Stable30 Bezier / Glideノート

連続的に変化する音用に、Bezier/Glideノートを追加しました。

操作:

```text
左ドラッグ:
  通常ノート作成

Alt + 左ドラッグ:
  Bezier/Glideノート作成
  ドラッグ開始位置が開始音程
  ドラッグ終了位置が終了音程
```

現在の実装:

```text
・Bezier曲線ノートをプロジェクトに保存可能
・画面上では曲線として表示
・プレビュー音に反映
・MIDI出力では短い固定音へ分割して近似
・ADOFAI出力では短いHz区間へ分割して近似
```

ADOFAI出力オプション:

```text
Curve step:
  曲線を何msごとに分割するか
  初期値 25ms

Curve pitch step:
  何半音ぶん変化したら分割するか
  初期値 0.25 semitone = 25 cent
```

小さくすると滑らかになりますが、タイル数が増えます。

同梱テスト音声生成:

```bash
python scripts/make_bezier_test_audio.py
```

出力:

```text
bezier_glide_test.wav
```

この音声には、固定音、上昇グライド、下降グライド、ビブラート風の連続変化が入っています。


## Stable31 160BPMテスト音声

Bezier/Glideテスト音声生成スクリプトを、エディターのBPMグリッドで扱いやすいように **160BPM / 拍基準** に変更しました。

実行:

```bash
python scripts/make_bezier_test_audio_160bpm.py
```

従来名でも同じ内容を出力します。

```bash
python scripts/make_bezier_test_audio.py
```

出力:

```text
bezier_glide_test_160bpm.wav
```

推奨エディター設定:

```text
BPM: 160
Offset: 0 ms
Snap: ON
Snap div: 1 または 4
```

構成:

```text
0-1 beat:   F4 fixed
1-2 beat:   G4 fixed
2-6 beat:   F4 -> C5 Bezier glide
6-10 beat:  C5 -> A4 Bezier fall
10-14 beat: A4 vibrato
14-15 beat: C5 fixed
15-16 beat: F5 fixed
```

全体は16拍、160BPMなので長さは6秒です。


## Stable32 Bezier曲線の初期形状を修正

前版では、Bezierノートの制御点が

```text
p1 = p0 + 1/3
p2 = p0 + 2/3
```

になっていたため、数学的に完全な直線になっていました。

Stable32では `Curve` セレクタを追加し、Alt+ドラッグで作るBezier/Glideノートの初期形状を選べるようにしました。

| Curve | 内容 |
|---|---|
| ease | 標準。p1=start, p2=end。見た目も音も曲線になります |
| s_curve | 強めのS字 |
| linear | 従来の直線 |
| ease_in | ゆっくり始まって後半で動く |
| ease_out | 前半で動いてゆっくり終わる |

操作:

```text
Curve で形を選ぶ
Alt + 左ドラッグでBezier/Glideノート作成
```

既存の直線Bezierは自動変換しません。作り直すか、今後必要なら選択中カーブの形状変更機能を追加してください。


## Stable33 C4→C6 / 160BPM / 4拍テスト音声

C4からC6まで、160BPMで4拍分かけて滑らかに上がるテスト音声生成スクリプトを追加しました。

実行:

```bash
python scripts/make_c4_c6_glide_160bpm.py
```

出力:

```text
c4_to_c6_160bpm_4beats.wav
```

推奨エディター設定:

```text
BPM: 160
Offset: 0 ms
Snap: ON
Snap div: 1 または 4
```

期待するノート:

```text
start: 0 beat / C4
end:   4 beat / C6
```

また、`Curve` セレクタを下部のBPM/Snap欄の横に表示しました。  
`Alt + 左ドラッグ` でBezier/Glideノートを作る前に、ここで `ease`, `s_curve`, `linear`, `ease_in`, `ease_out` を選べます。


## Stable34 per-zip Target Angle override

ADOFAI Angle Compression出力用に、ノート/zip単位の `Target Angle` 上書きを追加しました。

操作:

```text
1. ノートを選択
2. 下部の Target Angle に角度を入力
3. Apply Angle
```

解除:

```text
選択中ノート → Clear Angle
```

ショートカット:

```text
Ctrl + Alt + A:
  Apply Angle
```

仕様:

```text
target_angle = None:
  従来通り自動計算

target_angle = 165:
  そのノート/zipだけ angle = 165° として出力
```

端数タイルも同じ角度を基準にします。

```text
final_angle = target_angle * fractional_part(keycount)
```

見た目:

```text
Target Angle が設定されたノートは紫寄りの色で表示されます。
```

Curve/Glideノートの場合:

```text
Curveを短い固定Hz区間へ分割したあと、
各segmentに同じ Target Angle を引き継ぎます。
```

注意:

```text
この機能は Angle Compression 用です。
Direct 180° 出力では基本的に無視されます。
```


## Stable35 選択操作の修正

- ノートを普通に左クリックしたとき、そのノートだけを選択状態にするようにしました。
- `Ctrl + 左クリック` は従来通り、複数選択への追加/解除として残しています。
- `Shift + 左クリック` は従来通り、範囲選択として残しています。
- ノートをドラッグした場合は、選択中ノートの移動として動作します。

操作:

```text
左クリック:
  そのノートだけを選択

Ctrl + 左クリック:
  複数選択に追加/解除

Shift + 左クリック:
  範囲選択

空白をクリック:
  選択解除 + 再生バー移動
```


## Stable36 Last-angle correction

Issue #3: `Add last-angle correction when overriding angle` に対応しました。

ADOFAI出力ダイアログに `Last-angle correction` を追加しました。

```text
ON:
  Target Angle を指定したとき、端数タイルも同じ比率で補正します。
  final_angle = target_angle * fractional_part(keycount)

OFF:
  端数タイルは自動計算角度のままにします。
  final_angle = auto_angle * fractional_part(keycount)
```

通常はON推奨です。

例:

```text
auto_angle   = 178°
target_angle = 165°
frac         = 0.7

ON:
  final_angle = 165 * 0.7 = 115.5°

OFF:
  final_angle = 178 * 0.7 = 124.6°
```

`Target Angle` を使って見た目を調整する場合、ONにしておくと最後の端数タイルも同じスケールで補正されます。


## Stable37 Final-tile visual correction with speed compensation

Target Angleを使ったとき、最後の端数タイルが中途半端な向きになって見た目が汚くなる問題への対策を追加しました。

ADOFAI出力ダイアログに次を追加しました。

```text
Final tile mode
Custom final angle
Cardinal step
```

Final tile mode:

```text
scaled:
  従来通り。
  final_angle = angle * frac

straight:
  最後の端数タイルを相対180°にして、前のタイルから直進させます。
  その分の時間はSetSpeedで補償します。

cardinal:
  最後の絶対角度を0/90/180/270付近へ寄せます。
  Cardinal stepを45にすると斜め方向も候補に入ります。
  その分の時間はSetSpeedで補償します。

custom:
  Custom final angleで指定した相対角度を使います。
  その分の時間はSetSpeedで補償します。
```

重要:

```text
最終タイルの角度を見た目優先で変更しても、
そのタイルの所要時間が変わらないようにSetSpeedを自動追加します。
```

つまり、

```text
角度を綺麗にする
↓
ズレた時間をSetSpeedで補償する
```

という動きです。

おすすめ:

```text
まずは Final tile mode = straight
見た目が合わない場合は cardinal
細かく合わせたい場合は custom
```


## Stable38 Export dialog cleanup

ADOFAI出力ダイアログを整理しました。

- `Last-angle correction` を削除しました。
  - `Final tile mode = scaled` では常に `final_angle = target_angle * frac` 相当で処理します。
- `Final tile mode = straight` をUIから削除しました。
  - 直進させたい場合は `Final tile mode = custom` + `Custom final angle = 180°` を使います。

残した選択肢:

```text
scaled:
  angle * frac

cardinal:
  最後の絶対角度を縦横/斜め方向へ寄せる

custom:
  Custom final angleを使う
  180°にすればstraight相当
```


## Stable39 Angle-only Hz charting mode

`Issue #4: Add angle-only Hz charting mode` に対応しました。

ADOFAI出力ダイアログに新しいMethodを追加しました。

```text
Angle-only: one BPM + angle only
```

仕様:

```text
・最初/全体のBPMは Angle-only BPM を使う
・このBPMを settings.bpm に書き込む
・各ノートごとのSetSpeedは基本的に置かない
・Hzはタイル角度だけで合わせる
```

角度計算:

```text
HzBPM = Hz * 60
angle = AngleOnlyBPM * 180 / HzBPM
```

つまり、

```text
angle = AngleOnlyBPM * 180 / (Hz * 60)
```

例:

```text
Angle-only BPM = 1600
Hz = 440

angle = 1600 * 180 / (440 * 60)
      = 10.909090...°
```

タイル数:

```text
keycount = Hz * duration
```

注意:

```text
Angle-onlyでは角度そのものが音程を決めるため、
per-note Target Angle override は無視します。
```

Final tile mode:

```text
scaled:
  final_angle = angle * frac
  基本的にSetSpeedなし

cardinal/custom:
  最後の端数タイルだけ見た目優先で角度変更
  その分はSetSpeedで時間補償
```

おすすめ:

```text
Method: Angle-only
Angle-only BPM: 1000～3000くらい
Final tile mode: scaled
```

角度が小さすぎて詰まる場合は `Angle-only BPM` を上げてください。


## Stable40 Hz/Angle Debug Preview

`Issue #5: Add Hz/angle debug preview` に対応しました。

ADOFAI出力ダイアログに `Debug Preview` ボタンを追加しました。

表示される主な値:

```text
index
floor_start / floor_end
start_s / end_s / duration_s
note / midi / freq_hz
method
keycount
whole / frac
change_x
angle
auto_angle
target_angle
target_angle_used
target_angle_ignored
final_angle_scaled
final_angle_effective
effective_bpm
final_bpm
tiles_est
final_visual_used
warning
```

コピー機能:

```text
Copy TSV
Copy CSV
```

注意:

```text
Curve/Glideノートは、ADOFAI出力時と同じように短い固定Hz区間へ分割した後の行として表示します。
```

用途:

```text
・Target Angle が効いているか確認
・Angle-onlyでTarget Angleが無視されているか確認
・final tile補正が入っているか確認
・角度が小さすぎる場所を確認
・max_tiles_per_noteで切られそうな場所を確認
```


## Stable41 Glide interpolation modes

`Issue #6: Investigate better glide interpolation modes` に対応しました。

Glide/Bezierノートの補間方式を選べるようにしました。

追加UI:

```text
Interp
Apply Interp
```

`Interp` は下部コントロールに表示されます。  
`Alt + 左ドラッグ` で新しく作るCurve/Glideノートに適用されます。

選択中の既存Curve/Glideノートへ適用したい場合:

```text
1. Curve/Glideノートを選択
2. Interp を選択
3. Apply Interp
```

追加された補間方式:

```text
bezier_pitch:
  MIDI/semitone空間でBezier補間
  従来方式

linear_pitch:
  MIDI/semitone空間で線形補間
  周波数比が一定になる

linear_hz:
  Hz空間で線形補間
  物理周波数が一定速度で変化する

bezier_hz:
  Hz空間でBezier補間
```

影響範囲:

```text
・画面上のCurve表示
・プレビュー音
・MIDI出力
・ADOFAI出力
・ADOFAI Debug Preview
・プロジェクト保存/読み込み
```

使い分け目安:

```text
自然な音階上のグライド:
  linear_pitch または bezier_pitch

一定Hz速度のサイレン的な変化:
  linear_hz

Hz上で曲線的に動かしたい:
  bezier_hz
```


## Stable42 Phase-continuous curve/glide export

Curve/GlideノートのADOFAI出力に、位相連続ベースのAngle-only出力を追加しました。

目的:

```text
従来:
  Curve/Glide
  → 短い固定Hzノートへ分割
  → segment境界でぶつ切り感が出る

Stable42:
  Curve/Glide
  → 連続した周波数関数 f(t) として扱う
  → phase(t) = ∫ f(t) dt を計算
  → phaseが1周期進む位置にタイルを置く
```

対象:

```text
Method = Angle-only
Phase-continuous glide = ON
Curve/Glideノート
```

固定ノートは従来通りです。  
Angle Compression / Direct 180° では従来通り短い固定Hz区間へ分割します。

計算:

```text
phase(t) = ∫ f(t) dt
tile boundary = phaseが1, 2, 3, ... を超える時刻
dt = 次のtile boundaryまでの秒数
angle = dt * AngleOnlyBPM * 180 / 60
```

これにより、Curve/Glideの中で周波数が連続的に変化しても、短い固定Hzノート列に分割せずに角度列を作れます。

出力ダイアログ:

```text
Phase-continuous glide:
  ON推奨
  Angle-onlyでCurve/Glideを連続位相として出力
```

Debug Preview:

```text
phase_continuous
angle_min
angle_max
```

を追加しました。

注意:

```text
Final tile mode = cardinal/custom を使うと、最後の1タイルだけは見た目補正のためSetSpeed補償が入ります。
Final tile mode = scaled なら基本的にAngle-only BPMのままです。
```


## Stable43 Phase-continuous glide for Direct / Angle Compression

Stable42では、Phase-continuous glide は Angle-only のみ対応でした。  
Stable43では、Direct 180° と Angle Compression でも Phase-continuous glide を使えるようにしました。

対象:

```text
Phase-continuous glide = ON
Curve/Glideノート
```

対応Method:

```text
Angle-only
Direct 180°
Angle Compression
```

方式:

```text
Curve/Glideを短い固定Hzノート列に分割せず、
周波数曲線 f(t) を積分してタイル境界を決めます。
```

Direct 180°:

```text
各タイルの角度は180°
各タイルの実時間dtに合わせてSetSpeedを置く
```

Angle Compression:

```text
Curve全体のtotal phaseからmain angleを決定
target_angleがあればそれを使用
各タイルの実時間dtに合わせてSetSpeedを置く
最後に端数phaseがある場合は final tile mode を適用
```

注意:

```text
Direct 180° / Angle Compression のPhase-continuous glideでは、
基本的にタイルごとにSetSpeedが追加されます。
そのため、出力は重くなりやすいです。

軽さを優先するなら Angle-only + Phase-continuous glide が最も軽いです。
```

Debug Preview:

```text
Direct 180° / Angle Compressionでも
phase_continuous = True
effective_bpm = varies
として表示されます。


## Stable45 Project loading and analysis responsiveness

音声解析まわりのフリーズ対策を追加しました。

- CQT解析をバックグラウンド `QThread` で実行するようにしました。
  - 解析中でもGUI全体が完全には固まりにくくなります。
- 同じ音声ファイル・同じ解析設定のスペクトログラムが既に読み込まれている場合、再解析せず再利用します。
- プロジェクト読み込み時、保存されたプロジェクト設定を先に適用してから音声を読み込むようにしました。
  - 保存時の `analysis_profile` が音声ロードに反映されます。
- プロジェクト読み込み時に、音声も読み込むか、ノートだけ読み込むかを選べるようにしました。
- ファイルメニューに `プロジェクト読込（ノートのみ）` を追加しました。
- 解析メニューに `音声を再解析` を追加しました。
- キャッシュがあるかどうかをステータスバーに表示するようにしました。

注意:

```text
CQT解析そのものはまだCPU処理です。
GPU STFT/CQTバックエンドは未実装です。
```


## Stable46 Notes-only project load behavior

Project loading behavior was adjusted for notes-only / unloaded-audio cases.

- When loading a project without loading its audio, the previous spectrogram is no longer kept.
- The editor now shows a black placeholder CQT instead.
- Previous decoded audio is unloaded, so playback does not accidentally use the old audio file.
- Note data still remains visible on top of the black placeholder.
- The placeholder duration is estimated from the loaded notes so the notes remain reachable.

This applies to:

```text
Load project -> ノートだけ読み込む
File menu -> プロジェクト読込（ノートのみ）
Missing/unavailable project audio path
```


## Stable47 UI language support

Basic UI language switching was added.

Supported languages:

```text
English
Japanese
```

Menu path:

```text
Options -> Language -> English / Japanese
```

The selected language is saved in the app settings and is applied after restarting AdopyHzEditor.

Translated areas include:

```text
main menus
main confirmation dialogs
project audio loading dialog
major status bar messages
ADOFAI export dialog labels
debug preview buttons
operation notes
```

Some technical labels are intentionally kept in English, such as:

```text
keycount
target_angle
phase_continuous
Angle-only
Final tile mode
```

PyInstaller note:

If you build an exe manually, include the locale JSON files:

```powershell
pyinstaller main.py --name AdopyHzEditor --windowed --add-data "locales;locales" --collect-all PySide6 --collect-all pyqtgraph --collect-all librosa --collect-all soundfile --collect-all sounddevice --collect-all audioread --collect-all mido
```


## Stable48 Playback audio loading and updater

Playback audio decoding was moved to a background worker.

Before:

```text
CQT analysis: background
playback audio decode: main UI thread
```

Now:

```text
CQT analysis: background
playback audio decode: background
```

This reduces short freezes after CQT loading, especially for long audio files or compressed formats.

### Auto updater

AdopyHzEditor can check GitHub Releases for updates.

Menu:

```text
Options -> Check for Updates
```

It also performs a silent update check shortly after startup.

Update requirements:

```text
- Releases must use version tags such as v0.1.1, v0.1.2, ...
- A release asset zip should be attached.
- The asset name should contain AdopyHzEditor and preferably Windows or win.
```

Recommended release asset name:

```text
AdopyHzEditor_Windows_v0.1.1.zip
```

When an update is available:

```text
1. The app asks whether to download it.
2. The zip is downloaded into the app config folder.
3. The app launches a temporary updater script.
4. The app closes.
5. The updater waits for the app process to exit.
6. The updater extracts and copies the new files.
7. The updated exe is restarted.
```

Automatic apply/restart is intended for PyInstaller Windows builds.  
When running from source, update checking works, but automatic apply/restart is disabled.

### PyInstaller note

The locale files must be included:

```powershell
pyinstaller main.py --name AdopyHzEditor --windowed --add-data "locales;locales" --collect-all PySide6 --collect-all pyqtgraph --collect-all librosa --collect-all soundfile --collect-all sounddevice --collect-all audioread --collect-all mido
```
