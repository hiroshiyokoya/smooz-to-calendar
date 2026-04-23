# app/app.py

"""
Smooz予約情報を取得し、Googleカレンダーに同期するFlaskアプリケーション。

実装関数一覧：
- health_check(): ヘルスチェック用のルート
- run(): 予約情報の取得とカレンダーへの同期を行うメイン処理
- fetch_and_update(): Gmailトリガーによる予約情報の取得と同期
- list_files(): カレントディレクトリ内のファイル一覧を取得

依存している自作関数一覧：
- fetch_reservations.py: fetch_reservations()
- calendar_sync.py: sync_calendar()
"""

import os
from flask import Flask, request, jsonify
from fetch_reservations import fetch_reservations
from calendar_sync import sync_calendar

app = Flask(__name__)

# 定数の定義
HEALTH_CHECK_MESSAGE = "Smooz fetcher is running."
SUCCESS_MESSAGE = "Success"
GMAIL_TRIGGER_MESSAGE = "Triggered by Gmail"

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
    ヘルスチェック用のルート。

    Returns:
        str: "Smooz fetcher is running." というメッセージ
        int: HTTPステータスコード 200 (OK)
    """
    return HEALTH_CHECK_MESSAGE, 200

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

@app.route("/files", methods=["GET"])
def list_files():
    """
    カレントディレクトリ内のファイル一覧を取得して表示するルート。

    Returns:
        json: カレントディレクトリ内のファイル名一覧
        int: HTTPステータスコード 200 (OK)
    """
    files = os.listdir(".")  # カレントディレクトリ
    return jsonify({"files": files}), 200
