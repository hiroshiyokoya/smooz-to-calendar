# main.py
import subprocess
import sys

# 定数の定義
PYTHON_EXECUTABLE = "python"
FETCH_RESERVATIONS_SCRIPT = "fetch_reservations.py"
CALENDAR_SYNC_SCRIPT = "calendar_sync.py"

def run_script(script_name, extra_args=None):
    """
    指定されたスクリプトを実行する。

    Args:
        script_name (str): 実行するスクリプト名。
        extra_args (list, optional): スクリプトに渡す追加の引数。Defaults to None.

    Returns:
        bool: スクリプトの実行が成功した場合は True、失敗した場合は False。
    """
    cmd = [PYTHON_EXECUTABLE, script_name]
    if extra_args:
        cmd += extra_args
    print(f"🚀 実行中: {cmd}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"❌ {script_name} の実行に失敗しました")
        return False
    print(f"✅ {script_name} の実行に成功しました")
    return True

def main():
    """
    Smooz予約情報の取得とGoogleカレンダーへの登録を行うメイン処理。

    コマンドライン引数:
        --debug: デバッグモードで実行する (カレンダー登録は1件のみ)。
        --no-clear: カレンダーの事前削除をスキップする。
    """
    debug = "--debug" in sys.argv
    clear = "--no-clear" not in sys.argv

    print("🔄 Smooz予約情報を取得中...")
    if not run_script(FETCH_RESERVATIONS_SCRIPT):
        return

    print("📅 Googleカレンダーに登録中...")
    args = ["--debug"] if debug else []
    if clear:
        args.append("--clear")
    run_script(CALENDAR_SYNC_SCRIPT, extra_args=args)

    print("✅ すべて完了！")

if __name__ == "__main__":
    main()
