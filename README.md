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
Dockerfile           # アプリ実行用のDocker設定
compose.yaml         # smooz-fetcherサービスの定義（ボリュームマウント含む）
requirements.txt     # Python依存パッケージ一覧

app/
├── main.py              # Flaskエントリーポイント（Cloud Run用）
├── fetch_reservations.py  # Smooz予約の取得処理
├── calendar_sync.py     # Googleカレンダーへの登録処理
├── login.txt            # Smoozログイン情報（メール＋パスワード）
├── credentials.json     # Google API認証情報（OAuthクライアントID）
├── token.json           # GoogleのOAuthトークン（初回認証で生成）
```

---

## .gitignore 例

以下のように `.gitignore` に記載して、機密情報をGitに含めないようにしてください：

```
login.txt
credentials.json
token.json
```

---

## ライセンス

MIT License
```

