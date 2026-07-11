# temperature-in-my-room

SwitchBot 温湿度計のデータをGitHub Actionsで15分毎に取得し、CSVではなくJSONとしてリポジトリに追記・コミットし、GitHub Pagesで公開するアプリケーションです。

## 構成

```
.github/workflows/fetch.yml   # 15分毎にAPI取得〜コミットまで実行するワークフロー
scripts/fetch_data.py         # SwitchBot APIから取得しdocs/data/へ保存するスクリプト
scripts/requirements.txt      # Pythonの依存パッケージ
docs/                         # GitHub Pagesの公開ルート
  data/latest.json            # 現在値（毎回上書き）
  data/YYYY-MM.json           # 月ごとの時系列データ（追記）
  index.html / css / js       # 現在値表示・折れ線グラフ（Chart.js）
```

## セットアップ手順

### 1. SwitchBot APIトークンの発行

SwitchBotアプリ内の「プロフィール」→「設定」→「アプリバージョン」を10回タップして開発者向けオプションを表示し、`トークン`と`シークレットキー`を取得します。

### 2. デバイスIDの確認

`GET https://api.switch-bot.com/v1.1/devices` を上記トークンで呼び出し、対象の温湿度計の `deviceId` を取得します。

### 3. GitHub Secretsの登録

リポジトリの **Settings > Secrets and variables > Actions** で以下を登録します。

| Secret名 | 内容 |
| --- | --- |
| `SWITCHBOT_TOKEN` | SwitchBotのトークン |
| `SWITCHBOT_SECRET` | SwitchBotのシークレットキー |
| `SWITCHBOT_DEVICE_ID` | 対象デバイスのID |

### 4. GitHub Pagesの有効化

**Settings > Pages** で、Source を「Deploy from a branch」、Branch を `main` / `/docs` に設定します。

### 5. ワークフローの動作確認

**Actions** タブから `Fetch SwitchBot Sensor Data` を `workflow_dispatch` で手動実行し、`docs/data/latest.json` と `docs/data/YYYY-MM.json` が更新・コミットされることを確認します。以降は15分毎に自動実行されます。

## ローカルでの動作確認

```powershell
pip install -r scripts/requirements.txt
$env:SWITCHBOT_TOKEN = "xxxx"
$env:SWITCHBOT_SECRET = "xxxx"
$env:SWITCHBOT_DEVICE_ID = "xxxx"
python scripts/fetch_data.py
```
