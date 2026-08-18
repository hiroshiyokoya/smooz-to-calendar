# Smooz 自動予約カレンダー登録スクリプト

このリポジトリは、Smooz予約サイトから予約情報を自動取得し、Google Calendarに定期的に登録する仕組みをCloud Run上で動作させることを目的としています。

---

## 主な機能

- Smooz予約サイトからの予約情報の自動取得
- 複数座席の予約に対応（号車・座席情報の正規化）
- Google Calendarへの予約情報の自動登録
- エラー発生時のGmail通知
- Gmailトリガーによる自動実行

### 予約情報の処理

- 複数座席の予約に対応
  - 号車・座席情報をリスト形式で保持
  - 重複する号車は自動的に統合
  - 座席情報は個別に表示

- 予約情報の正規化
  - 全角カッコを半角に変換
  - スペースを削除
  - ステータス情報の重複を除去

## プロジェクト構造

```
.
├── app/                    # メインアプリケーションコード
│   ├── app.py             # Flaskエントリーポイント
│   ├── main.py            # ローカル実行用
│   ├── fetch_reservations.py  # Smooz予約の取得処理
│   ├── calendar_sync.py   # Googleカレンダーへの登録処理
│   ├── authorize_once.py  # Google OAuth認証用スクリプト
│   ├── __init__.py       # Pythonパッケージ定義
│   ├── login.txt         # Smoozログイン情報
│   ├── credentials.json  # Google API認証情報
│   ├── token.json        # GoogleのOAuthトークン
│   └── reservations.json # 予約情報のキャッシュ
├── gas/                   # Google Apps Script
│   └── main.gs           # Gmailトリガー用スクリプト
├── Dockerfile            # 本番用Docker設定
├── Dockerfile.dev        # 開発用Docker設定
├── compose.yaml          # ローカル開発用Docker Compose構成
├── requirements.txt      # Python依存パッケージ一覧
├── deploy.sh             # Cloud Runデプロイ
├── cleanup.sh            # 古いリビジョンとイメージの掃除
├── .gcp.env.example      # GCPプロジェクトIDの記入例(実ファイルはローカルのみ)
├── .gcloudignore        # Cloud Build用の除外設定
├── .gitignore           # Git用の除外設定
└── LICENSE              # MITライセンス
```

## 依存関係

### Pythonパッケージ
- Flask: Webアプリケーションフレームワーク
- google-auth-oauthlib: Google OAuth認証
- google-auth-httplib2: Google API認証
- google-api-python-client: Google APIクライアント
- requests: HTTPリクエスト
- python-dotenv: 環境変数管理

### Google API
- Google Calendar API
- Gmail API

### 外部サービス
- Smooz予約サイト
- Google Cloud Run
- Google Apps Script

## 環境変数

以下の環境変数を設定する必要があります：

### 必須環境変数
- `SMOOZ_EMAIL`: Smoozログイン用メールアドレス
- `SMOOZ_PASSWORD`: Smoozログイン用パスワード
- `NOTIFICATION_EMAIL`: エラー通知先メールアドレス
- `GOOGLE_CALENDAR_ID`: 予約を登録するGoogleカレンダーのID

### オプション環境変数
- `DEBUG`: デバッグモード（true/false）
- `LOG_LEVEL`: ログレベル（DEBUG/INFO/WARNING/ERROR）
- `PORT`: アプリケーションのポート番号（デフォルト: 8080）

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

## Cloud Run デプロイ手順

GCPプロジェクトID、Cloud Run URL、通知先メールなどのアカウント固有の値は **公開リポジトリに書かない**。ローカルの `.gcp.env` と GAS エディタ、実行時の環境変数だけで管理する。

### ローカル設定(`.gcp.env`)

```bash
cp .gcp.env.example .gcp.env
```

`.gcp.env` に `GCP_PROJECT_ID` を記入する。このファイルは `.gitignore` 済み。

#### GCPプロジェクトIDの確認方法

```bash
gcloud projects list
gcloud config get-value project
```

または [Google Cloud Console](https://console.cloud.google.com/cloud-resource-manager) でプロジェクト一覧を確認する。

Container Registry(`gcr.io`)は2025-03に終了しているため、Artifact Registry(`*-docker.pkg.dev`)を使用します。

### 推奨(スクリプト実行)

```bash
./deploy.sh
```

`deploy.sh` は `.gcp.env` の `GCP_PROJECT_ID` を読みます。環境変数 `GCP_PROJECT_ID` でも上書きできます。

デプロイ完了時に `deploy.sh` が表示する URL を、**Google Apps Script エディタ上の** `Config.CLOUD_RUN_URL` にだけ設定してください(publicリポジトリの `gas/main.gs` には本番URLをコミットしない)。

Cloud Run は未認証では呼べません。GAS からはサービスアカウントの IDトークンを付けて呼び出します。

### GASから認証付きで呼ぶ設定

1. デプロイ後に表示されるサービスアカウント向けに、鍵を**ローカルだけ**で作る

```bash
set -a && . ./.gcp.env && set +a
gcloud iam service-accounts keys create ./smooz-gas-invoker.json \
  --iam-account="smooz-gas-invoker@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --project="${GCP_PROJECT_ID}"
```

`smooz-gas-invoker.json` は `.gitignore` 済み。Git やチャットに貼らない。

2. Apps Script エディタで「プロジェクトの設定」→「スクリプト プロパティ」に `GCP_SA_KEY` を追加し、JSON ファイルの内容をそのまま貼る

3. `Config.CLOUD_RUN_URL` を本番 URL にする(エディタ上のみ)

4. `checkSmoozMail` を手動実行し、レスポンスコード 200 を確認する

鍵を作り直したら古い鍵は [サービスアカウントの鍵一覧](https://console.cloud.google.com/iam-admin/serviceaccounts) から削除する。

### Cloud Run URLの確認方法

本番URLはリポジトリに含めません。次のいずれかで確認し、GASでは `https://<確認したホスト>/fetch_and_update` の形式で設定します。

1. **デプロイ直後(推奨)**

```bash
./deploy.sh
# 末尾に表示される「GASエディタの Config.CLOUD_RUN_URL に次を設定」を参照
```

2. **gcloud**

```bash
# .gcp.env を読んだうえで実行する例
set -a && . ./.gcp.env && set +a
gcloud run services describe smooz-runner \
  --project="${GCP_PROJECT_ID}" \
  --region=asia-northeast1 \
  --format='value(status.url)'
```

表示された URL の末尾に `/fetch_and_update` を付けたものが `CLOUD_RUN_URL` です。

3. **Google Cloud Console**

[Cloud Run](https://console.cloud.google.com/run) で対象プロジェクトを選択し、サービス **`smooz-runner`** の URL を確認します。

### 手動(コマンド)

1. 必要なAPIを有効化

```bash
set -a && . ./.gcp.env && set +a
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  --project="${GCP_PROJECT_ID}"
```

2. Artifact Registryリポジトリを作成(初回のみ)

```bash
gcloud artifacts repositories create smooz-sync \
  --repository-format=docker \
  --location=asia-northeast1 \
  --project="${GCP_PROJECT_ID}"
```

3. イメージをビルドしてArtifact Registryにpush

```bash
REGION=asia-northeast1
REPO=smooz-sync
SERVICE=smooz-runner
TAG="$(date +%Y%m%d-%H%M%S)"

IMAGE="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${REPO}/${SERVICE}:${TAG}"
gcloud builds submit --tag "${IMAGE}" --project="${GCP_PROJECT_ID}"
gcloud artifacts docker tags add "${IMAGE}" "${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${REPO}/${SERVICE}:latest" \
  --project="${GCP_PROJECT_ID}"
```

4. Cloud Run にデプロイ(1GiBメモリ、認証必須)

```bash
gcloud run deploy smooz-runner \
  --image "${IMAGE}" \
  --platform managed \
  --region asia-northeast1 \
  --memory 1Gi \
  --no-allow-unauthenticated \
  --set-env-vars="PYTHONUNBUFFERED=1" \
  --project="${GCP_PROJECT_ID}"
```

続けて、GAS用サービスアカウントに `roles/run.invoker` を付与し、`allUsers` の呼び出し権限があれば外します。`./deploy.sh` がこの手順をまとめて実行します。

### 古いリビジョンとイメージのクリーンアップ

`deploy.sh` 実行後に自動で `cleanup.sh` を呼び出します(デフォルト: 非トラフィックの旧リビジョンと、未参照のARイメージを削除)。

手動実行する場合:

```bash
# 非トラフィックの旧リビジョンと未参照イメージをすべて削除
./cleanup.sh

# ロールバック用に旧リビジョンと未参照イメージを1つずつ残す
KEEP_REVISIONS=1 KEEP_IMAGE_TAGS=1 ./cleanup.sh

# 移行前の gcr.io イメージも削除する場合
CLEANUP_LEGACY_GCR=1 ./cleanup.sh
```

---

## エラー通知の設定

エラー発生時はGmailで通知が送信されます。通知先メールアドレスは環境変数 `NOTIFICATION_EMAIL` で設定してください(公開リポジトリには書かない)。

### 通知が送信される主なケース
- Google Calendar APIの認証エラー
- カレンダー同期処理のエラー
- イベント登録の失敗

### 設定方法
1. 実行環境に `NOTIFICATION_EMAIL` を設定する(Cloud Run ならサービス環境変数、ローカルならシェルの環境変数)
2. 初回認証を実行
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
   - 監視間隔: **5分間隔を推奨**（1分間隔はGmail APIの使用制限に達する可能性があります）

### トリガー設定の確認方法
1. Google Apps Scriptの管理画面を開く
2. 左側のメニューから「トリガー」を選択
3. 設定されているトリガーの一覧が表示されます
4. `checkSmoozMail`関数のトリガーを確認し、実行間隔が適切に設定されているか確認してください
   - 推奨: 15分間隔または20分間隔（10分間隔でも制限に達する可能性があります）
   - 1分間隔は推奨しません（Gmail APIの制限に達する可能性があります）

### 注意事項
- **Gmail APIの使用制限**: GASにはGmailサービスの1日あたりの使用制限があります。正確な制限数は公開されていませんが、10分間隔で実行しても制限に達する可能性があります。
- **推奨設定**: 10分間隔以上（15分間隔または20分間隔を推奨）に設定してください。
- **最適化内容**:
  - ラベル取得をグローバル変数にキャッシュして、2回目以降のAPI呼び出しを完全に回避
  - ラベル付きスレッドの更新チェックを強制実行時のみに制限
  - 検索結果を最新5件に制限
  - API呼び出し回数をログに記録して、使用状況を監視可能に
- **エラー発生時**: 制限に達した場合、24時間後に自動的にリセットされます。その間はスクリプトが正常に動作しません。
- **使用状況の確認**: 実行ログに「今回の実行でのGmail API呼び出し回数」と「本日の累計Gmail API呼び出し回数」が記録されます。この情報を確認して、制限に近づいていないか監視してください。

### 設定値のカスタマイズ
`gas/main.gs` の `Config` オブジェクトで以下の設定を変更できます：
- `LABEL_NAME`: Smoozメールに付与するラベル名
- `SMOOZ_MAIL_QUERY`: Smoozメールを検出するためのGmail検索クエリ
- `CLOUD_RUN_URL`: Cloud RunのエンドポイントURL (`https://YOUR_CLOUD_RUN_URL/fetch_and_update`)。**本番URLはGASエディタでのみ設定**し、リポジトリには書かない
- `FORCE_RUN_INTERVAL_HOURS`: 強制実行までの時間間隔（時間）
- `SKIP_START_HOUR`: Gmailチェックをスキップする開始時刻（時、デフォルト: 2）
- `SKIP_END_HOUR`: Gmailチェックをスキップする終了時刻（時、デフォルト: 6）

### 深夜時間帯のスキップ機能
深夜2時から6時の間は、Gmail APIの呼び出しを削減するため、Gmailチェックを自動的にスキップします。
この時間帯はSmoozからのメールが来る可能性が低いため、API呼び出し回数を削減できます。
スキップ時間帯は`Config`オブジェクトの`SKIP_START_HOUR`と`SKIP_END_HOUR`で変更可能です。

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
    muteHttpExceptions: true,
    headers: { Authorization: "Bearer <Cloud Run ID token>" }
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
2. トリガーとして `checkSmoozMail` を**5分おき**に設定（1分おきはGmail APIの制限に達する可能性があります）
3. `Config.CLOUD_RUN_URL` を GAS エディタ上で本番 URL にする(リポジトリには書かない)
4. Script Properties に `GCP_SA_KEY` を設定する
5. 初回は `resetLastThreadId()` を実行

> 補足: Cloud Run は `--no-allow-unauthenticated` でデプロイし、GAS から IDトークン付きで呼び出します。

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

- `login.txt`、`credentials.json`、`token.json`、`.gcp.env` は**すべて機密情報**です。
  誤ってもGitなどの公開リポジトリにアップロードしないよう、`.gitignore`に必ず追加してください。
- 初回認証時はブラウザが開き、Googleアカウントでの認証が必要です。
- 認証トークンは自動的に更新されますが、長期間使用しない場合は再認証が必要になる場合があります。
- エラー通知はGmailで送信されます。通知先のメールアドレスは適切に設定してください。

---

## ライセンス

MIT License

