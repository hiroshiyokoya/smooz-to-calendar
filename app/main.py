# main.py
import subprocess
import sys

def run_script(name, extra_args=None):
    cmd = ["python", name]
    if extra_args:
        cmd += extra_args
    print(f"🚀 実行中: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"❌ {name} の実行に失敗しました")
        return False
    return True

def main():
    debug = "--debug" in sys.argv
    no_clear = "--no-clear" in sys.argv
    clear = not no_clear  # デフォルトで clear 有効

    print("🔄 Smooz予約情報を取得中...")
    if not run_script("fetch_reservations.py"):
        return

    print("📅 Googleカレンダーに登録中...")
    args = []
    if debug:
        args.append("--debug")
    if clear:
        args.append("--clear")
    run_script("calendar_sync.py", extra_args=args)

    print("✅ すべて完了！")

if __name__ == "__main__":
    main()
