# AdopyHzEditor

AdopyHzEditor は、スペクトログラムを見ながら手作業でノートを配置し、MIDI や ADOFAI Hz Chart として出力するためのエディタです。

想定している作業フローは次のとおりです。

```text
音声ファイル
↓
CQTスペクトログラム
↓
手動でノートをトレース・編集
↓
MIDI出力 / ADOFAI Hz Chart出力
```

完全自動採譜ツールではありません。音源中の周波数を確認しながら、正確にノートを置くための手動編集ツールです。

## 主な機能

- WAV / OGG / MP3 / FLAC / M4A などの音声読み込み（利用できる形式はローカルのデコーダ環境に依存）
- C0～C10 の CQT スペクトログラム表示
- スペクトログラム上のドラッグによるノート作成
- 複数ノート選択
- コピー / 切り取り / 貼り付け
- Undo / Redo
- ドラッグやショートカットによるノート移動
- BPM / Offset からのグリッド生成
- グリッドスナップ
- メトロノーム
- 再生速度変更
- 作成したノートのプレビュー再生
- プレビュー / MIDI出力 / ADOFAI出力の音程シフト
- MIDI出力
- ADOFAI Hz Chart出力
- `.adopyhz` プロジェクトの保存 / 読み込み
- Curve / Glide ノート
- Harmony / Polyrhythm 出力
- Microtonal CQT（41 EDO / 53 EDO など）
- Web UI（React + TypeScript + pywebview）

## インストール

可能であれば Python 3.11 以降を使用してください。

通常版:

```bash
pip install -r requirements.txt
```

Web UI:

```bash
pip install -r requirements-webui.txt
```

OGG や MP3 の再生・読み込みが環境によって不安定な場合は、先に WAV へ変換すると安定しやすくなります。

```bash
ffmpeg -i input.ogg input.wav
```

## 起動

従来の PySide6 UI:

```bash
python main.py
```

Web UI:

```bash
python web_ui.py
```

Windows の Web UI は、source / packaged ともに既定で Qt backend を使用します。

開発時に renderer を切り替える場合は `ADOPY_WEB_UI_GUI` を使用できます。

```text
ADOPY_WEB_UI_GUI=qt
ADOPY_WEB_UI_GUI=edgechromium
ADOPY_WEB_UI_GUI=auto
```

## 基本的な使い方

1. 音声ファイルを開きます。
2. 時間・音程表示範囲を調整してスペクトログラムを見やすくします。
3. スペクトログラム上をドラッグしてノートを作成します。
4. 再生やノートプレビューで確認します。
5. MIDI または ADOFAI Hz Chart として出力します。

## プロジェクトファイル

AdopyHzEditor の標準プロジェクト拡張子は次のとおりです。

```text
.adopyhz
```

古い `.ahe.json` / `.json` も読み込みできますが、新規保存には `.adopyhz` を使用してください。

将来バージョンのプロジェクトを古い AdopyHzEditor で開いて未知の項目を失わないよう、対応していない新しい project version は読み込みを拒否します。

## 主な操作

| 操作 | 動作 |
|---|---|
| 左ドラッグ | ノート作成 |
| ノートを左クリック | そのノートを選択 |
| 空白を左クリック | 選択解除 + 再生位置移動 |
| Ctrl + 左クリック | 複数選択へ追加 / 解除 |
| Shift + 左クリック | 範囲選択 |
| 右クリック | ノート削除 |
| Delete | 選択ノート削除 |
| Ctrl + A | 全ノート選択 |
| Esc | 選択解除 |
| Alt + 左ドラッグ | Curve / Glide ノート作成 |

## 編集ショートカット

| ショートカット | 動作 |
|---|---|
| Ctrl + C | 選択ノートをコピー |
| Ctrl + X | 選択ノートを切り取り |
| Ctrl + V | 再生位置へ貼り付け |
| Ctrl + Z | Undo |
| Ctrl + Y | Redo |
| Ctrl + Shift + Z | Redo |
| Ctrl + Shift + Left / Right | 選択ノートを左右へ移動 |
| Ctrl + Shift + Up / Down | 選択ノートを半音単位で上下移動 |
| Ctrl + S | プロジェクトを保存 |
| Ctrl + Shift + S | 名前を付けて保存 |

Snap が有効な場合、横方向のノート移動は BPM / Offset グリッドへ吸着します。

## 再生ショートカット

| ショートカット | 動作 |
|---|---|
| Space | 再生 / 一時停止 |
| Ctrl + Space | 停止 |
| Left / Right | 1秒シーク |
| Shift + Left / Right | 5秒シーク |

## 表示設定

| 項目 | 内容 |
|---|---|
| Time | 横方向スクロール |
| Visible | 表示する時間幅 |
| Pitch bottom | 表示する最低音程 |
| Visible notes | 縦方向ズーム |
| Fit | 全体表示 |
| Enhance | スペクトログラムを見やすく正規化 |
| Harmonics | 倍音らしい上側成分を抑制: off / soft / strong |
| Contrast | スペクトログラムのコントラスト |
| Gamma | 明るさカーブ |
| Colormap | カラーマップ |
| Analysis | 解析プロファイル |
| CQT Resolution | CQTの音程分解能 |

## 音声・ノートプレビュー設定

| 項目 | 内容 |
|---|---|
| Song Vol | 元音源の音量 |
| Speed | 再生速度 |
| Note Vol | 作成ノートのプレビュー音量 |
| Preview Oct | プレビューだけのオクターブシフト |
| Export Oct | MIDI / ADOFAI 出力のオクターブシフト |
| Export Semi | MIDI / ADOFAI 出力の半音シフト |
| Metro Vol | メトロノーム音量 |

出力時の音程は次のように計算します。

```text
export_pitch = note_pitch + Export Oct * 12 + Export Semi
```

プレビューを聴きやすくするために `Preview Oct` を変更しても、MIDI / ADOFAI の出力音程は変わりません。

## Grid / Snap / Metronome

| 項目 | 内容 |
|---|---|
| Grid | BPM / Offset のガイド線を表示 |
| Metronome | クリック音を有効化 |
| BPM | Grid / Metronome のBPM |
| Offset | Grid / Metronome のオフセット（ms） |
| Snap | 作成・移動したノートをグリッドへ吸着 |
| Snap div | 1拍の分割数 |

例:

```text
Snap div = 1  -> 1拍単位
Snap div = 4  -> 1/4拍単位
Snap div = 8  -> 1/8拍単位
```

## ADOFAI Hz Chart 出力

### Angle Compression

補正済み Keycount 式を使用します。

```text
beat_count = note_duration_seconds * Base BPM / 60
keycount   = Hz * 60 * beat_count / Base BPM
x_tiles    = floor(keycount)
change_x   = x_tiles or user-specified value
angle      = 180 * change_x / keycount
BPM        = (Hz * 60) * (angle / 180)
```

出力:

```text
x_tiles 個のタイル:
  relative angle = angle

最後の端数タイル:
  relative angle = angle * fractional_part(keycount)
```

出力は floor 1 から開始し、floor 0 には `SetSpeed` を置きません。

### Angle-only

1つの基準 BPM を使い、主にタイル角度で Hz を表現します。

```text
angle = AngleOnlyBPM * 180 / (Hz * 60)
```

Curve / Glide では phase-continuous 出力を利用できます。

### Harmony / Polyrhythm

複数の周波数系列を時刻でマージし、1本の ADOFAI パスとしてシリアライズします。

```text
root pitch impulse train
+ harmony pitch impulse train
-> 時刻でマージ
-> 1本のADOFAIタイル列へ変換
```

### Auto Route (Twirl)

タイミング用 relative angle を変更せず、先の経路を見ながら自然な折り返し位置へ `Twirl` を配置して見た目を整えます。

```text
relative angle / timing: 維持
Twirl配置: 自動計画
absolute angleData: Twirlに合わせて再構築
```

旧 `twirl upward` は互換 alias として残っています。

### Final tile mode

```text
scaled:
  angle * frac

cardinal:
  最後の絶対角度を縦横/斜め方向へ寄せる

custom:
  Custom final angle を使用
  180°にすればstraight相当
```

見た目のために角度を変えた場合も、必要に応じて `SetSpeed` で時間を補償します。

## ADOFAI出力についての注意

このエクスポータでは ADOFAI を単一トラックとして扱うため、重なったノートは直列化されます。

Hz Chart は高音や長いノートでタイル数が非常に多くなり、`.adofai` ファイルが大きくなることがあります。

## キャッシュ

スペクトログラム解析結果はユーザーディレクトリ以下へキャッシュされます。

例:

```text
~/.adopyhzeditor_cache
```

キャッシュを削除しても問題ありません。次回読み込み時に再解析されるため、その分だけ遅くなります。

## リポジトリ構成

主な構成は次のとおりです。

```text
AdopyHzEditor/
├─ main.py                 # 従来のPySide6 UI
├─ web_ui.py               # React + pywebview UIのエントリポイント
├─ core/                   # ノート・音声・解析・project I/O
├─ exporters/              # ADOFAI / MIDI出力
├─ importers/              # MIDI等の読み込み
├─ web/                    # Web UI backend / I/O / tools
├─ frontend/               # React + TypeScript frontend
├─ desktop/                # Desktop側ダイアログ等
├─ locales/                # 翻訳JSON
├─ tests/                  # テスト
├─ scripts/                # ビルド・テスト音声生成等
├─ requirements.txt
├─ requirements-webui.txt
└─ README.md
```

## 既知の制限

- 完全自動採譜ではありません。
- 密度の高い曲ではスペクトログラムが見づらくなる場合があります。
- Harmonics 抑制は表示補助であり、実際の音源分離ではありません。
- 極端に大量のノートや巨大な ADOFAI 出力は重くなる場合があります。
- CQT解析は基本的にCPU処理です。

---

# 更新履歴

以下は主要な Stable 更新の記録です。技術識別子やUI上の英語ラベルは、コードとの対応を保つため一部そのまま記載しています。

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

| Profile | 内容 |
|---|---|
| Fast | C1-C7、粗め、最速寄り |
| Normal | バランス設定 |
| Full C0-C10 | 広い音域、重い |

一度解析した音声は `~/.adopyhzeditor_cache` にキャッシュされます。

## Stable21 修正

- 新しい音声ファイルを開いたとき、前のノートが引き継がれないようにしました。
- 保存していない変更がある状態で新しい音声ファイルを開く前に警告を出すようにしました。
- 保存していない変更がある状態でプロジェクトを読み込む前にも警告を出すようにしました。
- ウィンドウを閉じるときにも保存確認を出すようにしました。
- ノートやプロジェクト設定を変更すると、タイトルに `*` が付きます。
- 保存後・読み込み後は未保存状態を解除します。

## Stable22 修正

- ノート選択判定を狭くしました。
- 複数選択後の削除を補強しました。
- ADOFAI出力の `Change x mode` に `lowest_floor` を追加しました。

```text
各ノートの x = floor(Keycount) を計算
その中で一番小さい x に全ノートを固定

例:
x = 3, 4, 5, 6
=> 全ノート change_x = 3
```

## Stable23 表示改善

WaveTone寄りに読みやすくする表示モードを追加しました。

- `Display`: `wavetone` / `ridge` / `smooth`
- `wavetone` カラーマップ
- 半音 / C音ごとの補助線
- 左軸の音名表示

目安:

```text
Display = wavetone
Colormap = wavetone
Contrast = 1.0～1.6
Gamma = 0.6～1.0
Harmonics = soft
```

## Stable24 判定補助

- カーソル位置の音名 / 周波数 / 近くのピークをステータスバーに表示。
- 白いクロスヘアを追加。
- `Pitch Assist` を追加（後のStable27で廃止）。

## Stable25 ADOFAI出力の見た目対策

`Track visual` を追加しました。

| Track visual | 内容 |
|---|---|
| normal | 通常表示 |
| faint | 薄く表示 |
| very faint | さらに薄く表示 |
| hidden | ほぼ非表示 |

## Stable26 修正

- `Track visual` 初期値を `normal` に戻しました。

## Stable27 修正

- `Pitch Assist` を廃止しました。
- 代わりに解析品質を上げる `Analysis = Precise` を追加しました。

```text
sr = 44100
hop_length = 512
CQT = 3 bins / semitone
表示は半音1行に畳み込み
```

## Stable28 修正

- `Pitch Assist` 廃止後に残っていたUIを削除。
- `MainWindow.apply_pitch_assist` が無い起動時エラーを修正。

## Stable29 修正

- `editor_view.py` の `np` 未定義エラーを修正。
- 廃止済み自動音程補正の内部参照を削除。
- 確認用の `nearby peak` 表示は維持。

## Stable30 Bezier / Glideノート

連続的に変化する音用の Curve / Glide ノートを追加しました。

```text
左ドラッグ:
  通常ノート

Alt + 左ドラッグ:
  Curve / Glideノート
```

- プロジェクト保存対応
- 曲線表示
- プレビュー対応
- MIDI / ADOFAI 出力対応

## Stable31 160BPMテスト音声

Bezier/Glideテスト音声を160BPM・拍基準へ変更しました。

```bash
python scripts/make_bezier_test_audio_160bpm.py
```

## Stable32 Bezier曲線の初期形状を修正

`Curve` セレクタを追加しました。

| Curve | 内容 |
|---|---|
| ease | 標準 |
| s_curve | 強めのS字 |
| linear | 直線 |
| ease_in | ゆっくり開始 |
| ease_out | ゆっくり終了 |

## Stable33 C4→C6 / 160BPM / 4拍テスト音声

```bash
python scripts/make_c4_c6_glide_160bpm.py
```

## Stable34 per-zip Target Angle override

ADOFAI Angle Compression出力用に、ノート / zip 単位の `Target Angle` 上書きを追加しました。

```text
target_angle = None:
  自動計算

target_angle = 165:
  そのノート/zipだけ165°で出力
```

## Stable35 選択操作の修正

- 左クリック: そのノートだけを選択
- Ctrl + 左クリック: 複数選択へ追加 / 解除
- Shift + 左クリック: 範囲選択
- 空白クリック: 選択解除 + 再生位置移動

## Stable36 Last-angle correction

`Target Angle` 指定時の端数タイル補正を追加しました。

## Stable37 Final-tile visual correction with speed compensation

`Final tile mode` / `Custom final angle` / `Cardinal step` を追加し、見た目を変えた分の時間を `SetSpeed` で補償するようにしました。

## Stable38 Export dialog cleanup

- `Last-angle correction` を削除。
- `straight` をUIから削除し、`custom = 180°` で代替。

## Stable39 Angle-only Hz charting mode

`Angle-only: one BPM + angle only` を追加しました。

```text
angle = AngleOnlyBPM * 180 / (Hz * 60)
```

## Stable40 Hz/Angle Debug Preview

ADOFAI出力ダイアログへ `Debug Preview` を追加しました。

主な確認項目:

```text
floor_start / floor_end
start_s / end_s / duration_s
note / midi / freq_hz
keycount
angle
target_angle
final_angle_effective
effective_bpm
tiles_est
warning
```

`Copy TSV` / `Copy CSV` に対応しています。

## Stable41 Glide interpolation modes

Curve / Glide の補間方式を選択できるようにしました。

```text
bezier_pitch
linear_pitch
linear_hz
bezier_hz
```

## Stable42 Phase-continuous curve/glide export

Angle-onlyで、Curve / Glide を短い固定Hz列へ分割せず、連続した周波数関数として扱う出力を追加しました。

```text
phase(t) = ∫ f(t) dt
tile boundary = phaseが1, 2, 3, ... を超える時刻
dt = 次のtile boundaryまでの秒数
angle = dt * AngleOnlyBPM * 180 / 60
```

## Stable43 Phase-continuous glide for Direct / Angle Compression

Phase-continuous glide を Direct 180° / Angle Compression にも拡張しました。

Direct 180°:

```text
各タイルの角度は180°
各タイルの実時間dtに合わせてSetSpeed
```

Angle Compression:

```text
Curve全体のtotal phaseからmain angleを決定
target_angleがあれば使用
各タイルの実時間dtに合わせてSetSpeed
```

## Stable45 Project loading and analysis responsiveness

音声解析まわりのフリーズ対策を追加しました。

- CQT解析をバックグラウンド `QThread` で実行。
- 同じ音声 / 解析設定のスペクトログラムを再利用。
- プロジェクト設定を音声読み込み前に適用。
- 「音声も読み込む / ノートだけ読み込む」を選択可能に。
- `音声を再解析` を追加。

## Stable46 ノートのみ読み込む場合の挙動

ノートのみ / 音声未読み込み時のプロジェクト読込挙動を調整しました。

- 音声を読み込まない場合、以前のスペクトログラムを残さない。
- 黒いプレースホルダCQTを表示。
- 以前のデコード済み音声を解除。
- ノートはプレースホルダ上に表示。
- ノートが見えるよう、プレースホルダ時間長をノートから推定。

対象:

```text
Load project -> ノートだけ読み込む
File menu -> プロジェクト読込（ノートのみ）
project audio path が見つからない場合
```

## Stable47 UI言語対応

UI言語切り替えを追加しました。

```text
English
Japanese
```

```text
Options -> Language -> English / Japanese
```

主要メニュー、確認ダイアログ、ステータス、ADOFAI出力ダイアログなどを翻訳しています。

技術識別子はコードとの対応のため英語のまま残しているものがあります。

## Stable48 再生音声読み込みとアップデータ

再生音声のデコードをバックグラウンド処理へ移しました。

```text
以前:
CQT analysis: background
playback audio decode: main UI thread

変更後:
CQT analysis: background
playback audio decode: background
```

長い音声や圧縮形式を読み込んだ直後の短いフリーズを軽減します。

当初はGitHub Releasesを利用する自動アップデータも追加しました。

## Stable49 Releaseページによる更新確認

PyInstaller環境のSSL / OpenSSL DLL問題を避けるため、アプリ内自動更新を廃止し、GitHub Releasesページを開く方式へ変更しました。

```text
Options -> Open Releases
```

## Stable50 UIの見つけやすさとヘルプ

アプリ内ヘルプを追加しました。

```text
Help -> Quick Start
Help -> Controls / Shortcuts
Help -> ADOFAI Export Guide
Help -> Curve / Glide Guide
Help -> Troubleshooting
Help -> About
```

`F1` で Quick Start を開けます。

## Stable51 出力用Pitch / Octave設定の分離

プレビュー音程と出力音程を分離しました。

```text
Preview Oct:
  ノートプレビューだけに影響

Export Oct:
  MIDI / ADOFAI 出力だけに影響

Export Semi:
  MIDI / ADOFAI 出力だけに影響
```

古いprojectの `note_octave` は互換性のため Preview / Export の両方へ読み込みます。

## Stable52 右側Settings Panel

ツールバーを整理し、編集設定を右側dockへ移動しました。

```text
Settings
├─ Playback
├─ Export Pitch
├─ Grid / Snap
├─ View / Analysis
└─ Curve / Angle
```

```text
View -> Settings Panel
```

から表示 / 非表示を切り替えられます。

## Stable53 ポータブルproject audio / ADOFAI song offset

projectへ次の音声パスメタデータを保存するようにしました。

```text
audio_path
audio_path_relative
audio_filename
```

読み込み時の探索順:

```text
1. project-relative audio path
2. 相対audio_path
3. 元の絶対audio_path
4. projectと同じフォルダのaudio_filename
```

音源が見つからない場合は `Locate audio` / `Load notes only` / `Cancel` を選択できます。

ADOFAI出力では `songFilename` / `songOffset` と音源コピーに対応しました。

## Stable54 ADOFAI songFilename fix

ADOFAI出力で誤った `settings.song` ではなく、正しい

```text
settings.songFilename
```

を書き込むように修正しました。

## Stable55 Harmony Charting / Polyrhythm export

新しいADOFAI出力方式を追加しました。

```text
Harmony / Polyrhythm: merged impulse trains
```

```text
root pitch impulse train
+ harmony pitch impulse train
-> 時刻でマージ
-> 1本のADOFAI tile pathへ直列化
```

主なpreset:

```text
octave +12
fifth +7
major third +4
minor third +3
lower octave -12
custom
```

## Stable56 初期Blank Workspace

音声やprojectを開いていなくても、黒い60秒ワークスペース上ですぐノート編集できるようにしました。

## Stable57 Harmony Charting後のTile Preview復元

Harmony Charting実装時に欠落していた `Tile Preview` を復元しました。

previewは実際の `build_adofai_level(...)` と同じ生成経路を使用し、`level["angleData"]` から座標を作成します。

## Stable58 SetSpeed補償付きHarmony角度remap

Harmony / Polyrhythm に見た目用角度remapを追加しました。

```text
raw
round 45°
round 90°
custom step
```

タイミングは `SetSpeed` で補償します。

```text
old_bpm = old_angle * 60 / (180 * dt)
new_bpm = old_bpm * (new_angle / old_angle)
```

## Stable59 Angle-only / Harmony のTarget Angle対応

`Target Angle` override を Angle-only / Harmony でも利用できるようにしました。

角度を変更した場合、BPMを補償して元のタイミングを保ちます。

## Stable60 Export dialog UI cleanup

ADOFAI出力ダイアログをタブ構成へ整理しました。

```text
Basic
Harmony
Advanced
Final Tile
Song
Preview / Help
```

## Stable61 Export dialog simplification

- `Direct 180°` をMethod一覧から削除。
  - `Target Angle = 180°` で表現できます。
- Curve / Glide のphase-continuousを標準化し、関連する旧UIを簡略化。

## Stable62 Just Intonation / Harmony root最適化

Harmony Chartingへ和音presetとtuning modeを追加しました。

preset:

```text
major triad
minor triad
sus4
dominant 7
```

tuning:

```text
equal temperament
just intonation
```

Just Intonationの例:

```text
major triad: C:E:G = 4:5:6
minor triad: C:Eb:G = 10:12:15
sus4:        C:F:G = 6:8:9
dominant 7: 4:5:6:7
```

root最適化:

```text
fixed root
least squares Hz
least squares cents
minimax cents
```

## Stable63 設定可能なBlank Workspace

```text
File -> Set Blank Workspace...
```

から次を指定できるようにしました。

```text
Duration
Lowest MIDI
Highest MIDI
```

project settingsにも保存されます。

## Stable64 Harmony Angle-only timing

Harmony / Polyrhythm に2種類のtiming modeを追加しました。

```text
setspeed
angle-only
```

`angle-only` は1つのglobal BPMを使い、次のimpulseまでの時間を角度へ直接エンコードします。

```text
angle = dt * BPM * 180 / 60
```

## Stable65 Microtonal CQT / Harmonic Diagram input

`CQT Resolution` を追加しました。

```text
profile default
100 cents
50 cents
25 cents
12.5 cents
41 EDO
53 EDO
```

microtonal modeではsub-binを半音へ畳み込まず、そのまま表示します。

Harmonic Diagram入力も追加しました。

```text
Edit -> Insert Harmonic Diagram...
```

ratio例:

```text
1/3
7/3
5:4
1.25
```

Caftaphata風pitch numberもpreviewできます。

```text
pitch_number = offset + round(EDO * log2(ratio)) mod EDO
```

## Stable66 音声なしでのノート再生

音源を読み込んでいないBlank Workspaceでも、作成したノートのpreview synthだけを再生できるようにしました。

```text
Blank workspace + placed notes + Play
-> editor note preview synthのみ再生
```

AudioPlayerはデコード済み音声がなくてもvirtual silent timelineを持ち、そこへpreview note / metronomeをmixします。

Harmony Chartingやmicrotonal実験を、音源なしでも行えるようになりました。
