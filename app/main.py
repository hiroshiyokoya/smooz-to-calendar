# main.py
"""
Smooz予約情報の取得とGoogleカレンダーへの登録を行うローカル実行用スクリプト。

実装関数一覧：
- run_script(): 指定されたスクリプトを実行
- main(): メイン処理（予約情報の取得とカレンダー登録）

依存している自作関数一覧：
- fetch_reservations.py: fetch_reservations()
- calendar_sync.py: sync_calendar()
"""

import subprocess
import sys
import os

# 定数の定義
PYTHON_EXECUTABLE = "python"
FETCH_RESERVATIONS_SCRIPT = "fetch_reservations.py"
CALENDAR_SYNC_SCRIPT = "calendar_sync.py"

def run_script(script_name, extra_args=None):
    """指定されたスクリプトを実行する。

    Args:
        script_name (str): 実行するスクリプト名。
        extra_args (list, optional): スクリプトに渡す追加の引数。Defaults to None.

    Returns:
        bool: スクリプトの実行が成功した場合は True、失敗した場合は False。

    Raises:
        FileNotFoundError: スクリプトファイルが見つからない場合。
        subprocess.SubprocessError: スクリプトの実行に失敗した場合。
    """
    if not os.path.exists(script_name):
        raise FileNotFoundError(f"スクリプトファイルが見つかりません: {script_name}")

    cmd = [PYTHON_EXECUTABLE, script_name]
    if extra_args:
        cmd += extra_args
    print(f"🚀 実行中: {cmd}")
    try:
        result = subprocess.run(cmd, check=True)
        print(f"✅ {script_name} の実行に成功しました")
        return True
    except subprocess.SubprocessError as e:
        print(f"❌ {script_name} の実行に失敗しました: {e}")
        return False

def main():
    """Smooz予約情報の取得とGoogleカレンダーへの登録を行うメイン処理。

    コマンドライン引数:
        --debug: デバッグモードで実行する (カレンダー登録は1件のみ)。
        --no-clear: カレンダーの事前削除をスキップする。

    Raises:
        FileNotFoundError: 必要なスクリプトファイルが見つからない場合。
        subprocess.SubprocessError: スクリプトの実行に失敗した場合。
    """
    debug = "--debug" in sys.argv
    clear = "--no-clear" not in sys.argv

    print("🔄 Smooz予約情報を取得中...")
    if not run_script(FETCH_RESERVATIONS_SCRIPT):
        sys.exit(1)

    print("📅 Googleカレンダーに登録中...")
    args = ["--debug"] if debug else []
    if clear:
        args.append("--clear")
    if not run_script(CALENDAR_SYNC_SCRIPT, extra_args=args):
        sys.exit(1)

    print("✅ すべて完了！")

if __name__ == "__main__":
    main()
