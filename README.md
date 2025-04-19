# Smooz 自動予約カレンダー登録スクリプト

このリポジトリは、Smooz予約サイトから予約情報を自動取得し、Google Calendar に定期的に登録する仕組みを Cloud Run 上で動作させることを目的としています。

---

## 必要なファイル

実行前に以下のファイルを `app/` フォルダ直下に配置してください：

### `login.txt`
- Smoozログイン情報を記述します。
- フォーマット（1行ずつ）：
  ```
  メールアドレス
  パスワード
  ```
- ⚠️ セキュリティのため、Gitには絶対にコミットしないように `.gitignore` に追加してください。

---

### `credentials.json`
- Google Calendar API の認証情報。
- Google Cloud Console から **OAuth 2.0クライアントID** を作成してダウンロードしたファイルです。

#### 取得手順：
1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 「APIとサービス」→「認証情報」へ進む
3. 「OAuth 2.0 クライアントIDを作成」
4. アプリケーションの種類：**デスクトップアプリ**
5. ダウンロードして `credentials.json` という名前で保存

---

### `token.json`
- 初回のOAuth認証後に自動生成されるファイルです。
- `credentials.json` を使って一度ローカルでスクリプトを実行すると作成されます。
- 認証トークンとして、Google Calendar API へのアクセスに使用されます。

---

## ディレクトリ構成（例）

```
Dockerfile           # 本番用Docker設定（Cloud Run向け）
Dockerfile.dev       # 開発用Docker設定（compose.yamlで使用）
compose.yaml         # ローカル開発用Docker Compose構成
requirements.txt     # Python依存パッケージ一覧
.gcloudignore        # Cloud Build用の除外設定
.gitignore           # Git用の除外設定
LICENSE              # MITライセンス

app/
├── app.py               # Flaskエントリーポイント（Cloud Run用）
├── main.py              # ローカル実行用（デバッグ時）
├── fetch_reservations.py  # Smooz予約の取得処理
├── calendar_sync.py     # Googleカレンダーへの登録処理
├── authorize_once.py    # Google OAuth認証用スクリプト
├── __init__.py         # Pythonパッケージ定義
├── login.txt            # Smoozログイン情報（メール＋パスワード）
├── credentials.json     # Google API認証情報（OAuthクライアントID）
├── token.json           # GoogleのOAuthトークン（初回認証で生成）

gas/
└── main.gs              # Gmailトリガー用のGoogle Apps Script
```

---

## Cloud Run デプロイ手順（本番環境）

### 1. 必要なAPIを有効化
```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com cloudscheduler.googleapis.com
```

### 2. イメージをビルドしてGCPにpush
```bash
gcloud builds submit --tag gcr.io/$(gcloud config get-value project)/smooz-runner
```

### 3. Cloud Run にデプロイ（1GiBメモリ、認証あり）
```bash
gcloud run deploy smooz-runner \
  --image gcr.io/$(gcloud config get-value project)/smooz-runner \
  --platform managed \
  --region asia-northeast1 \
  --memory 1Gi \
  --allow-unauthenticated
```

### 4. Cloud Run に呼び出し権限を付与（Schedulerからアクセスさせる）
```bash
gcloud run services add-iam-policy-binding smooz-runner \
  --region asia-northeast1 \
  --member="serviceAccount:cloud-run-invoker@$(gcloud config get-value project).iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

### 5. Cloud Scheduler ジョブを作成（15分ごとにPOST）
```bash
gcloud scheduler jobs create http smooz-schedule \
  --schedule "*/15 * * * *" \
  --uri https://[CLOUD_RUN_URL]/run \
  --http-method POST \
  --oidc-service-account-email cloud-run-invoker@$(gcloud config get-value project).iam.gserviceaccount.com \
  --location asia-northeast1 \
  --time-zone "Asia/Tokyo"
```

> `CLOUD_RUN_URL` は `gcloud run services describe smooz-runner --region asia-northeast1 --format="value(status.url)"` で確認


## Gmail通知をトリガーとした自動実行（イベント駆動）

Cloud Scheduler による定期実行とは別に、Gmail に Smooz から通知メールが届いたタイミングで Cloud Run を自動実行する構成も利用できます。これにより、無駄なリクエストを減らしつつ、変更があった場合にすばやく予約情報を反映できます。

### 仕組み概要

- Gmail の受信トリガーを Apps Script（GAS）で定期実行
- 件名に `【チケットレスサービス「Smooz」】` を含む新着メールを検知
- Cloud Run 上の `/fetch_and_update` エンドポイントを呼び出し、予約情報を再取得・同期

### GAS スクリプト例（`gas/main.gs`）

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

1. 上記スクリプトを Google Apps Script に貼り付け
2. トリガーとして `checkSmoozMail` を 1分おき(または、5分おき)に設定
3. `YOUR_CLOUD_RUN_URL` を実際の Cloud Run エンドポイントに置換
4. 初回は `resetLastThreadId()` を実行しておくとスムーズです

> 補足：Cloud Run のエンドポイントは `--allow-unauthenticated` オプション付きでデプロイする必要があります。

---

## .gitignore 例

以下のように `.gitignore` に記載して、機密情報をGitに含めないようにしてください：

```
login.txt
credentials.json
token.json
```

---

## .gcloudignore の注意点

Cloud Build (`gcloud builds submit`) を使ってデプロイする際、`.gcloudignore` が存在しない場合は `.gitignore` が自動的に使用されます。
そのため、以下のように `.gcloudignore` を明示的に作成して、`token.json` や `credentials.json` を**除外しないように明示的に含める**必要があります：

### 推奨 `.gcloudignore` 設定例
```
# 除外したいもの
*.pyc
__pycache__/
*.log
.git

# 明示的に含める
!app/login.txt
!app/token.json
!app/credentials.json
```

---

## ライセンス

MIT License

