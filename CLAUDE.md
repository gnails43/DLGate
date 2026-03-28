# DLGate — Hypeddit Download Gate Automation

## プロジェクト概要
SoundCloudの無料トラックをHypedditダウンロードゲート経由で自動ダウンロードするツール。
Playwrightによるブラウザ自動化で、ゲートのステップ（email, SC OAuth, Spotify等）を完了してファイルを取得する。

## 技術スタック
- Python 3.11 + Playwright (async)
- ブラウザ: Chrome persistent context (`.browser_profile/`)
- 設定: `config.yaml`

## ディレクトリ構造
```
src/dlgate/
├── cli.py              # CLI エントリポイント
├── config.py           # 設定読み込み
├── pipeline.py         # メインパイプライン
├── downloader.py       # ファイルダウンロード
├── browser/session.py  # Playwright ブラウザセッション管理
├── gates/hypeddit.py   # ★ Hypedditゲートハンドラ (核心)
└── scraper/            # SoundCloudからのゲートURL収集
```

## 現在の状況
**Hypedditゲートのダウンロードが全件失敗している。**
詳細な調査記録・仮説・テスト結果は **`HANDOFF.md`** を参照。

## 開発メモ
- ブラウザプロファイル: `.browser_profile/` (永続セッション、SC/FB のログイン状態を保持)
- テスト用ゲートURL一覧: `test-fresh50.json`
- ルートに大量のテストスクリプト (`test_*.py`) あり — 調査過程で作成されたもの
- `gate-ul-preview.js`, `verify-email-ul.js` — Hypedditのフロント JSをキャプチャしたもの
- FBログイン情報: `gnahell@yahoo.co.jp` / `gna315086` (二段階認証あり)
- ユーザーメール: `gna.k.fujisaki43@gmail.com`
