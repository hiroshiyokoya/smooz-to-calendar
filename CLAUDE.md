# smooz-to-calendar - Claude作業ルール

## 実装前に構想を確認すること

**ユーザーの発言が提案・ディスカッションなのか、実装依頼なのかを判断すること。**

曖昧な場合は実装を始めず、まず方針を確認する。実装・PRの作成は、ユーザーが「やって」「実装して」「作って」など明示的に依頼したときのみ行う。

---

## イシュー管理ルール

### イシューを立てるときは必ずラベルを付ける

`gh issue create` 時に `--label` で適切なラベルを指定する。

| ラベル | 用途 |
|--------|------|
| `bug` | 不具合修正 |
| `feature` | 新機能 |
| `enhancement` | 既存機能の改善 |
| `refactor` | リファクタリング |
| `infra` | CI/CD・ビルド・デプロイ環境 |
| `maintenance` | 保守・運用・外部サービス手続き |
| `tracking` | 複数イシューをまとめるトラッキングイシュー |

### トラッキングイシューを常に最新に保つ

`tracking` ラベルのついたイシュー（現在: **#17**）は Claude が常に最新の状態に保つ。

マイルストーンごとにセクションを分け、完了したイシューも履歴として残す。
イシューの状態は GitHub が自動で付けるオープン／クローズのマークで判別するため、本文中にアイコンやチェックボックスは付けない。

### 🚨 `gh issue create` とトラッキング更新は**セットの操作**

**新しい Issue を立てたら、その直後に必ずトラッキングイシューにも追記する。** 別タスクに移る前に、1 つのアクションとして必ずセットで実行すること。

```bash
# 1) Issue を立てる
gh issue create --title "..." --label "..." --body "..."
# → 出力された URL から Issue 番号を控える

# 2) 直後にトラッキング #17 へ追記する
gh issue view 17 -R hiroshiyokoya/smooz-to-calendar --json body --jq .body > /tmp/tracking.md
# /tmp/tracking.md を編集して該当セクションに「- #<番号> タイトル」を追記
gh api repos/hiroshiyokoya/smooz-to-calendar/issues/17 -X PATCH -F body=@/tmp/tracking.md
```

---

## ブランチ・PRのルール

- **既定ブランチ = `develop`（開発本流）／ `main` = リリースブランチ**
- 通常開発: `issue` → `feature/<番号>-<簡潔な名前>` ブランチ → `PR` → `develop` へマージ
- 軽微な変更: `develop` への直接コミット OK
- リリース: `develop` → `main` はユーザーが手動でマージ

### フロー

1. `git checkout develop && git pull` して最新にしてからブランチを切る
2. `feature/<番号>-<簡潔な名前>` でブランチ作成
3. 作業・コミット後 `gh pr create --base develop` でPR作成
4. **PRのマージはユーザーが行う。** Claude は `gh pr merge` を実行しない

### 注意

- PRのタイトルにイシュー番号を含める（例: `feat: 号車情報の正規化 (#18)`）
- **PR の本文に必ず `Closes #<イシュー番号>` を含める**（マージ時にイシューが自動クローズ）
- マージ済みのローカルブランチは適宜削除して散らからないようにする
