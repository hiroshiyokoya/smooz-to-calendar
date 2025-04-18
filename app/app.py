# app/app.py

import os
from flask import Flask, request
from fetch_reservations import fetch_reservations
from calendar_sync import sync_calendar

app = Flask(__name__)

@app.route("/run", methods=["POST"])
def run():
    try:
        print("▶️ 処理開始")
        reservations = fetch_reservations()
        print(f"📝 取得した予約数: {len(reservations)} 件")
        sync_calendar(reservations, debug=False)
        print("✅ 処理完了")
        return "Success", 200
    except Exception as e:
        print(f"❌ エラー発生: {e}")
        return f"Error: {str(e)}", 500

@app.route("/", methods=["GET"])
def health_check():
    return "Smooz fetcher is running.", 200

@app.route("/files", methods=["GET"])
def list_files():
    files = os.listdir(".")  # カレントディレクトリ
    all_files = "\n".join(files)
    return f"📂 /app/src の中身:\n{all_files}", 200