"""install_hook.py — 危ないコマンドを止めるフックを、自分のプロジェクトに入れる(設定ファイルを手で書き換えなくてよい)。

    python3 ~/ai-guard/files/install_hook.py ~/my-project

やること:
  1. <プロジェクト>/.claude/hooks/block_dangerous.py にフックを写す
  2. <プロジェクト>/.claude/settings.json に、フックの登録を書き足す
     - すでに settings.json があれば、中身を壊さずに書き足す。元のファイルは settings.json.bak_<日時> として残す
     - すでに同じ登録があれば、何もしない
外部と通信しない。標準ライブラリだけ。
"""
import datetime
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMMAND = 'python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/block_dangerous.py'


def install(project):
    project = os.path.abspath(os.path.expanduser(project))
    if not os.path.isdir(project):
        sys.exit(f"フォルダが見つからない: {project}")
    hooks_dir = os.path.join(project, ".claude", "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    shutil.copy(os.path.join(HERE, "hooks", "block_dangerous.py"), os.path.join(hooks_dir, "block_dangerous.py"))
    print(f"写した: {os.path.join(hooks_dir, 'block_dangerous.py')}")

    path = os.path.join(project, ".claude", "settings.json")
    settings = {}
    if os.path.exists(path):
        try:
            settings = json.load(open(path, encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"{path} が JSON として読めないので、触らずに止めた({e})。中身を直してからもう一度実行すること")
        backup = path + ".bak_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy(path, backup)
        print(f"元の設定の控え: {backup}")

    pre = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
    for entry in pre:
        for h in entry.get("hooks", []):
            if h.get("command") == COMMAND:
                print("すでに登録されているので、設定は変えなかった")
                return
    pre.append({"matcher": "Bash", "hooks": [{"type": "command", "command": COMMAND}]})
    json.dump(settings, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"登録した: {path}")
    print("Claude Code を起動し直すと有効になる。起動したら /hooks と打って、登録が見えるかを確かめること")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("使い方: python3 install_hook.py <プロジェクトのフォルダ>")
    install(sys.argv[1])
