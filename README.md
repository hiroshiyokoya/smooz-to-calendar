# Smooz 自動予約カレンダー登録スクリプト

このリポジトリは、Smooz予約サイトから予約情報を自動取得し、Google Calendarに定期的に登録する仕組みをCloud Run上で動作させることを目的としています。

---

## 必要なファイル

`app/` フォルダ直下に以下のファイルを配置してください。**いずれも機密情報を含むため、絶対にGitなどの公開リポジトリにアップロードしないでください（.gitignoreに追加してください）**。

### `login.txt`
- Smoozログイン情報（メールアドレス・パスワード）を1行ずつ記述します。

### `credentials.json`
- Google Calendar API・Gmail APIの認証情報（Google Cloud ConsoleでOAuth 2.0クライアントIDを作成しダウンロード）。

#### 取得手順
1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 「APIとサービス」→「認証情報」へ進む
3. 「OAuth 2.0 クライアントIDを作成」（アプリケーションの種類：デスクトップアプリ）
4. ダウンロードして `credentials.json` という名前で保存

#### 必要なAPI
- Google Calendar API
- Gmail API

### `token.json`
- 初回OAuth認証後に自動生成されるファイル（Google APIへのアクセス用トークン）。

---

## ディレクトリ構成例

```
Dockerfile           # 本番用Docker設定（Cloud Run向け）
Dockerfile.dev       # 開発用Docker設定
compose.yaml         # ローカル開発用Docker Compose構成
requirements.txt     # Python依存パッケージ一覧
.gcloudignore        # Cloud Build用の除外設定
.gitignore           # Git用の除外設定
LICENSE              # MITライセンス

app/
├── app.py               # Flaskエントリーポイント
├── main.py              # ローカル実行用
├── fetch_reservations.py  # Smooz予約の取得処理
├── calendar_sync.py     # Googleカレンダーへの登録処理
├── authorize_once.py    # Google OAuth認証用スクリプト
├── __init__.py         # Pythonパッケージ定義
├── login.txt            # Smoozログイン情報
├── credentials.json     # Google API認証情報
├── token.json           # GoogleのOAuthトークン

gas/
└── main.gs              # Gmailトリガー用Google Apps Script
```

---

## Cloud Run デプロイ手順

1. 必要なAPIを有効化
    ```bash
    gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
    ```
2. イメージをビルドしてGCPにpush
    ```bash
    gcloud builds submit --tag gcr.io/$(gcloud config get-value project)/smooz-runner
    ```
3. Cloud Run にデプロイ（1GiBメモリ、認証あり）
    ```bash
    gcloud run deploy smooz-runner \
      --image gcr.io/$(gcloud config get-value project)/smooz-runner \
      --platform managed \
      --region asia-northeast1 \
      --memory 1Gi \
      --allow-unauthenticated
    ```

---

## エラー通知の設定

エラー発生時はGmailで通知が送信されます。通知先メールアドレスは `app/authorize_once.py` の `NOTIFICATION_EMAIL` 変数で設定してください。

### 通知が送信される主なケース
- Google Calendar APIの認証エラー
- カレンダー同期処理のエラー
- イベント登録の失敗

### 設定方法
1. `app/authorize_once.py` を開く
2. `NOTIFICATION_EMAIL` 変数を設定
    ```python
    NOTIFICATION_EMAIL = 'your-email@example.com'  # 通知先メールアドレス
    ```
3. 初回認証を実行
    ```bash
    python app/authorize_once.py
    ```

## GASトリガー設定

Gmailの新着メールを監視し、Smoozからのメールを検出した際に自動的に処理を実行します。

### トリガーの種類
1. メール検出トリガー
   - Smoozからの新着メールを検出した場合に実行
   - 処理完了後、メールに"Smooz"ラベルを付与

2. 強制実行トリガー
   - 最後の実行から一定時間（デフォルト: 24時間）経過した場合に強制的に実行
   - メールの有無に関わらず実行される
   - 実行間隔は`FORCE_RUN_INTERVAL_HOURS`で設定可能

### 設定方法
1. Google Apps Scriptの管理画面で `gas/main.gs` を開く
2. トリガーを設定
   - 関数: `checkSmoozMail`
   - イベントのソース: 時間主導型
   - 時間ベースのトリガーのタイプ: 分ベースのタイマー
   - 監視間隔: 1分、5分など、お好みで

### 設定値のカスタマイズ
`gas/main.gs` の `Config` オブジェクトで以下の設定を変更できます：
- `LABEL_NAME`: Smoozメールに付与するラベル名
- `SMOOZ_MAIL_QUERY`: Smoozメールを検出するためのGmail検索クエリ
- `CLOUD_RUN_URL`: Cloud RunのエンドポイントURL
- `FORCE_RUN_INTERVAL_HOURS`: 強制実行までの時間間隔（時間）

---

## Gmail通知をトリガーとした自動実行（イベント駆動）

GmailにSmoozから通知メールが届いたタイミングでCloud Runを自動実行できます。
これにより、無駄なリクエストを減らし、変更があった場合にすばやく予約情報を反映できます。

### 仕組み概要
- Gmailの受信トリガーをApps Script（GAS）で定期実行
- 件名に `【チケットレスサービス「Smooz」】` を含む新着メールを検知
- Cloud Run上の `/fetch_and_update` エンドポイントを呼び出し、予約情報を再取得・同期

### GASスクリプト例（`gas/main.gs`）
```
function checkSmoozMail() {
  const labelName = "Smooz";
  const label = GmailApp.getUserLabelByName(labelName) || GmailApp.createLabel(labelName);

  const threads = GmailApp.search('from:info@smooz.jp subject:【チケットレスサービス「Smooz」】 -label:' + labelName);
  if (threads.length === 0) return;

  const latestThread = threads[0];
  const alreadyProcessed = PropertiesService.getScriptProperties().getProperty("lastThreadId");
  if (alreadyProcessed === latestThread.getId().toString()) return;

  UrlFetchApp.fetch("https://YOUR_CLOUD_RUN_URL/fetch_and_update", {
    method: "post",
    muteHttpExceptions: true
  });

  PropertiesService.getScriptProperties().setProperty("lastThreadId", latestThread.getId());
  threads.forEach(thread => thread.addLabel(label));
}

function resetLastThreadId() {
  PropertiesService.getScriptProperties().deleteProperty("lastThreadId");
}
```

### 使用方法
1. 上記スクリプトをGoogle Apps Scriptに貼り付け
2. トリガーとして `checkSmoozMail` を1分おき（または5分おき）に設定
3. `YOUR_CLOUD_RUN_URL` を実際のCloud Runエンドポイントに置換
4. 初回は `resetLastThreadId()` を実行

> 補足：Cloud Runのエンドポイントは `--allow-unauthenticated` オプション付きでデプロイしてください。

---

## ローカルでの実行方法

1. 依存パッケージのインストール
    ```bash
    pip install -r requirements.txt
    ```
2. 初回認証の実行
    ```bash
    python app/authorize_once.py
    ```
3. スクリプトの実行
    ```bash
    python app/main.py
    ```
4. デバッグモードでの実行
    ```bash
    python app/main.py --debug
    ```

---

## 注意事項

- `login.txt`、`credentials.json`、`token.json` は**すべて機密情報**です。
  誤ってもGitなどの公開リポジトリにアップロードしないよう、`.gitignore`に必ず追加してください。
- 初回認証時はブラウザが開き、Googleアカウントでの認証が必要です。
- 認証トークンは自動的に更新されますが、長期間使用しない場合は再認証が必要になる場合があります。
- エラー通知はGmailで送信されます。通知先のメールアドレスは適切に設定してください。

---

## ライセンス

MIT License

