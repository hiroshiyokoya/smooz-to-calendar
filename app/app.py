# app/app.py

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
    """予約情報の取得とカレンダーへの同期を行う共通処理。"""
    print("▶️ 処理開始")
    reservations = fetch_reservations()
    print(f"📝 取得した予約数: {len(reservations)} 件")
    sync_calendar(reservations, debug=False)
    print("✅ 処理完了")

def handle_error(e):
    """エラー処理を行う共通関数。"""
    print(f"❌ エラー発生: {e}")
    return f"Error: {str(e)}", 500

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
