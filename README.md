# DLGate

SoundCloud / Hypeddit のダウンロードゲートを自動処理して楽曲をダウンロードするツール。

## コンポーネント

1. **Chrome拡張** — SoundCloud/Hypedditページに「+ DL List」ボタンを追加。DL対象をリスト管理・JSONエクスポート
2. **Python CLI** — エクスポートしたJSONを読み込み、Playwrightでゲートを自動通過して楽曲をDL

## セットアップ

### Python CLI

```bash
pip install -e .
playwright install chromium
cp config.example.yaml config.yaml
# config.yaml を編集（名前・メール等）
```

### Chrome拡張

1. Chrome で `chrome://extensions` を開く
2. 「デベロッパーモード」をON
3. 「パッケージ化されていない拡張機能を読み込む」→ `extension/` フォルダを選択

## 使い方

### 1. 初回セットアップ（SNSログイン）

```bash
dlgate setup
```

ブラウザが開くので、SoundCloud・Spotify・Instagram・TikTok・YouTubeにログイン。完了したらターミナルでEnter。

### 2. DLリストにトラックを追加

SoundCloudでトラックページを開き、「+ DL List」ボタンをクリック。Hypedditページでも同様。

### 3. リストをエクスポート

Chrome拡張のポップアップで「Export JSON」をクリック。

### 4. 一括ダウンロード

```bash
dlgate process dlgate-list-20260322.json
```

## ゲート対応状況

| ゲート | ステップ | 対応 |
|--------|---------|------|
| Hypeddit | メール入力 | ✅ |
| | SoundCloud OAuth | ✅ |
| | コメント | ✅ |
| | SNSリンク (Spotify/Instagram/TikTok/YouTube等) | ✅ |
| | ダウンロード | ✅ |

## 設定（config.yaml）

```yaml
user:
  name: "Your Name"
  email: "your@email.com"

comments:
  - "Great track!"
  - "Yeah"
  - "Nice one"

download:
  output_dir: "./downloads"
  skip_existing: true

browser:
  profile_dir: "./.browser_profile"
  headless: false
  slow_mo: 100
  timeout: 30000
```
