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
