# React / TypeScript UI prototype

AdopyHzEditor の React / TypeScript フロントエンドです。既存の PySide6 版はそのまま残し、Web UI は `web_ui.py` から別起動します。

## ビルドと起動

Windowsではリポジトリ直下からこれだけで起動できます。

```powershell
.\run-webui.cmd
```

初回は必要に応じて frontend / Python の依存関係を導入し、その後 `npm run build` → `web_ui.py` を自動実行します。`.venv\Scripts\python.exe` がある場合はそれを優先します。

ビルド済みUIをそのまま起動したい場合:

```powershell
.\run-webui.cmd -SkipBuild
```

依存関係の自動導入を行わない場合:

```powershell
.\run-webui.cmd -NoInstall
```

## Vite 開発モード

```powershell
.\run-webui.cmd -Dev
```

Vite (`127.0.0.1:5173`) を自動起動して `web_ui.py` を接続します。Web UIを閉じるとVite側も終了します。

手動で起動する場合は従来どおり `frontend` で `npm run dev` を実行し、`ADOPY_WEB_UI_URL` を設定して `python web_ui.py` を起動できます。

## 移植済み

- 音声読み込み、再生、一時停止、停止、シーク、速度・音量変更
- CQT解析とHTML Canvas上のスペクトログラム描画
- 固定ノート / カーブノートの作成・選択・移動・削除
- ノート左右端ドラッグによる長さ変更（複数選択対応、スナップ対応）
- 移動 / リサイズ中のゴーストプレビュー
- `Alt` + 既存ノートドラッグによる複製移動
- 再生位置でのノート分割（カーブ対応）
- 複数ノートの一括時間 / 音高移動、長さ統一、開始 / 終了揃え
- 再生ヘッドの自動追従（ON/OFF可能）
- アプリ共通の単音プリセット保存・削除・再生位置への挿入
- Undo / Redo、コピー / 切り取り / 貼り付け
- ノートの数値インスペクタ（開始・終了・長さ・音高）
- ノート複製 (`Ctrl+D`) とクオンタイズ (`Q`)
- 範囲選択、時間・音高表示範囲の移動 / ズーム
- スペクトル / ノート / 両方の表示モード
- 再生、出力、グリッド / スナップ、表示、解析、カーブ設定
- プロジェクト保存 / 読み込み、ノートのみ読み込み、ノート結合
- 空のワークスペース
- MIDI読み込み / 出力、選択ノートMIDI出力
- 既存Python exporterを利用した詳細ADOFAI出力
- ADOFAIタイルプレビュー / デバッグプレビュー
- Web版ADOFAI Harmony出力は平均律固定（純正律UIは削除）
- プロジェクト音声コピー、自動 / 手動 songOffset
- ヘルプ / クイックスタート / リリースページ
- Quick Hz ツールと既存譜面への追記
- 倍音ダイアグラムのプレビュー / 挿入
- Web UIの日本語表示
- 既存主要ショートカット
- ファイル / 編集 / 解析 / ツール / オプション / ヘルプ メニュー
- GitHub ActionsによるPython構文チェックとTypeScript/Viteビルドチェック

単音プリセットはプロジェクトファイルとは別に保存されるため、曲をまたいで再利用できます。選択したノートの音高・長さ・カーブ・補間・目標角度をそのままテンプレートとして保存します。

Python側の音声解析・再生・MIDI・プロジェクト・Quick Hz・ADOFAI処理は書き直さず、pywebview bridge経由で再利用します。

## 残っている互換性調整

- 旧MIDI読み込み時の詳細cleanupオプション
- プロジェクト音声が見つからない場合のLocateフロー
- Web UIでファイルを置き換える / 閉じる際の未保存確認
- 旧PySide6版に残っている細かい確認ダイアログの差

これらが終わるまではPySide6版も並行して利用できます。
