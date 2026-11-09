#!/usr/bin/env python3
"""block_dangerous.py — Claude Code の PreToolUse フック。取り返しのつかないコマンドを、実行の直前に止める。

Claude Code はフックに、実行しようとしているツールの入力を「標準入力の JSON」で渡す。
(環境変数では渡さない。ここを取り違えたフックは、何も止めない)
止めるときは、理由を標準エラーに書いて終了コード 2 で終わる。

登録(.claude/settings.json):
  {"hooks": {"PreToolUse": [{"matcher": "Bash",
     "hooks": [{"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/block_dangerous.py"}]}]}}

これは「網」であって「壁」ではない。python やシェルの書き方次第で、すり抜けは作れる。
拒否リスト(settings.json の permissions.deny)や、作業用フォルダの分離と組み合わせて使う。
外部と通信しない。標準ライブラリだけ。
"""
import json
import re
import sys

def _rm_recursive_force(cmd):
    """rm に「再帰」と「強制」の両方の指定があるか(-rf, -fr, -Rf, -r -f, --recursive --force など)。"""
    for seg in re.split(r"[;&|]+", cmd):
        words = seg.split()
        for i, w in enumerate(words):
            if w == "rm" or w.endswith("/rm"):
                opts = [a for a in words[i + 1:] if a.startswith("-")]
                short = "".join(a[1:] for a in opts if not a.startswith("--"))
                rec = "r" in short.lower() or "--recursive" in opts
                force = "f" in short or "--force" in opts
                if rec and force:
                    return True
    return False


# (理由, 判定)。判定は正規表現か関数。自分の事故に合わせて足し、足したら tests/test_hook.py にも1行足して確かめる
RULES = [
    ("再帰的な強制削除", _rm_recursive_force),
    ("作業中の変更を捨てる git", r"\bgit\s+(reset\s+--hard|checkout\s+(-f|--force|--\s+\.|\.)(\s|$)|clean\s+-[a-zA-Z]*f|restore\s+(--staged\s+)?\.(\s|$))"),
    ("履歴を書き換える push", r"\bgit\s+push\b.*(\s--force(-with-lease)?\b|\s-f\b)"),
    ("ディスク全体への書き込み", r"\b(mkfs(\.\w+)?|dd\s+.*\bof=/dev/)"),
]


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # 読めない入力では止めない(Claude Code 本体の動作を壊さないため)
    cmd = (data.get("tool_input") or {}).get("command", "")
    # 引用符の中の文字列(echo 'rm -rf は危険' など)は判定から外す
    bare = re.sub(r"'[^']*'|\"[^\"]*\"", "''", cmd)
    for reason, rule in RULES:
        if (rule(bare) if callable(rule) else re.search(rule, bare)):
            print(f"止めました({reason}): {cmd}\n必要なら、人間が手で実行してください。", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
