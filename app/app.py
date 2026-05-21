# app/app.py

"""
Smooz予約情報を取得し、Googleカレンダーに同期するFlaskアプリケーション。

実装関数一覧：
- health_check(): liveness 用の軽量ルート
- healthz(): 依存関係(chromium / login.txt / Google認証情報)をチェックする readiness ルート
- run(): 予約情報の取得とカレンダーへの同期を行うメイン処理
- fetch_and_update(): Gmailトリガーによる予約情報の取得と同期

依存している自作関数一覧：
- fetch_reservations.py: fetch_reservations(), LOGIN_FILE
- calendar_sync.py: sync_calendar()
- authorize_once.py: load_credentials()
"""

import os
import shutil
from flask import Flask, jsonify
from fetch_reservations import fetch_reservations, LOGIN_FILE
from calendar_sync import sync_calendar
from authorize_once import load_credentials

app = Flask(__name__)

# 定数の定義
HEALTH_CHECK_MESSAGE = "Smooz fetcher is running."
SUCCESS_MESSAGE = "Success"
GMAIL_TRIGGER_MESSAGE = "Triggered by Gmail"
CHROME_BIN = os.environ.get("CHROME_BIN", "/usr/bin/chromium")

def handle_reservations_and_sync():
    """予約情報の取得とカレンダーへの同期を行う共通処理。

    Returns:
        None

    Raises:
        Exception: 予約情報の取得またはカレンダー同期中にエラーが発生した場合。
    """
    print("▶️ 処理開始")
    try:
        reservations = fetch_reservations()
        print(f"📝 取得した予約数: {len(reservations)} 件")
        sync_calendar(reservations, debug=False)
        print("✅ 処理完了")
    except Exception as e:
        print(f"❌ 処理中にエラーが発生しました: {e}")
        raise

def handle_error(e):
    """エラー処理を行う共通関数。

    Args:
        e (Exception): 発生したエラー。

    Returns:
        tuple: エラーメッセージとHTTPステータスコード。
    """
    error_message = f"Error: {str(e)}"
    print(f"❌ エラー発生: {error_message}")
    return error_message, 500

@app.route("/", methods=["GET"])
def health_check():
    """
    Liveness 用の軽量ヘルスチェック。プロセスが応答できるかだけを確認する。

    Returns:
        str: "Smooz fetcher is running." というメッセージ
        int: HTTPステータスコード 200 (OK)
    """
    return HEALTH_CHECK_MESSAGE, 200


def _check_chromium():
    path = shutil.which(CHROME_BIN) or (CHROME_BIN if os.path.isfile(CHROME_BIN) else None)
    if path:
        return {"ok": True, "path": path}
    return {"ok": False, "error": f"chromium binary not found at {CHROME_BIN}"}


def _check_login_file():
    if not os.path.isfile(LOGIN_FILE):
        return {"ok": False, "error": f"{LOGIN_FILE} not found"}
    return {"ok": True}


def _check_google_credentials():
    try:
        creds = load_credentials()
    except Exception as e:
        return {"ok": False, "error": f"failed to load credentials: {e}"}
    if creds is None:
        return {"ok": False, "error": "token.json not found"}
    if creds.valid:
        return {"ok": True, "status": "valid"}
    if creds.expired and creds.refresh_token:
        return {"ok": True, "status": "expired-but-refreshable"}
    return {"ok": False, "error": "credentials are invalid and not refreshable"}


@app.route("/healthz", methods=["GET"])
def healthz():
    """
    Readiness 用の詳細ヘルスチェック。chromium / ログイン情報 / Google認証情報を確認する。

    Returns:
        json: 各依存の状態を含む JSON
        int: すべて OK なら 200、いずれか NG なら 503
    """
    checks = {
        "chromium": _check_chromium(),
        "login_file": _check_login_file(),
        "google_credentials": _check_google_credentials(),
    }
    all_ok = all(c["ok"] for c in checks.values())
    status_code = 200 if all_ok else 503
    return jsonify({"status": "ok" if all_ok else "degraded", "checks": checks}), status_code

@app.route("/run", methods=["POST"])
def run():
    """
    予約情報の取得とカレンダーへの同期を行うメイン処理を実行するルート。

    Returns:
        str: 成功時は "Success"、エラー時は "Error: {エラーメッセージ}"
        int: 成功時は HTTPステータスコード 200 (OK)、エラー時は 500 (Internal Server Error)
    """
    try:
        handle_reservations_and_sync()
        return SUCCESS_MESSAGE, 200
    except Exception as e:
        return handle_error(e)

@app.route("/fetch_and_update", methods=["POST"])
def fetch_and_update():
    """
    Gmailのトリガーにより、予約情報の取得とカレンダーへの同期を行うルート。

    Returns:
        str: 成功時は "Triggered by Gmail"、エラー時は "Error: {エラーメッセージ}"
        int: 成功時は HTTPステータスコード 200 (OK)、エラー時は 500 (Internal Server Error)
    """
    try:
        print("📩 Gmailトリガーによる実行")
        handle_reservations_and_sync()
        print("✅ Gmailトリガー処理完了")
        return GMAIL_TRIGGER_MESSAGE, 200
    except Exception as e:
        print(f"❌ Gmailトリガー中にエラー発生: {e}")
        return handle_error(e)

