"""extract_user_messages.py — Claude Code の会話の記録(jsonl)から、人間の発言だけを時刻つきで取り出す。

会話が切れて再開するとき、引き継ぎの要約は直前の指示を落とすことがある。原文は会話の記録に残っている。
    python3 extract_user_messages.py --latest --last 10 --min-chars 80      ← 今いるフォルダの、いちばん新しい会話の記録を自動で探す
    python3 extract_user_messages.py --previous --last 10 --min-chars 80    ← Claude Code を起動し直したあとは、こちら(1つ前の会話)
    python3 extract_user_messages.py ~/.claude/projects/<フォルダ>/<セッションID>.jsonl --last 10 --min-chars 80
--min-chars で短い発言(「OK」など)を除き、長い指示だけを見られる。外部と通信しない。標準ライブラリだけ。

会話の記録の置き場所と形式は Claude Code の版によって変わりうる。動かないときは、1行目を開いて形を確かめること。
"""
import argparse
import glob
import json
import os
import re


def user_texts(path):
    for line in open(path, encoding="utf-8", errors="ignore"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("type") != "user" or d.get("isMeta"):
            continue
        msg = d.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):  # ツールの結果は人間の発言ではないので除く
            text = "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
        else:
            text = ""
        text = text.strip()
        if text and not text.startswith("<"):  # システムが差し込む <...> の行は除く
            yield d.get("timestamp", ""), text


def latest_transcript(cwd=None, nth=1):
    """今いるフォルダ(Claude Code を起動したフォルダ)の、いちばん新しい会話の記録を探す。

    Claude Code は ~/.claude/projects/ の下に、フォルダの道筋の英数字以外を「-」に置き換えた名前で記録を置く
    (2026年11月時点。版によって変わりうる)。
    """
    cwd = os.path.abspath(cwd or os.getcwd())
    base = os.path.expanduser("~/.claude/projects")
    name = re.sub(r"[^A-Za-z0-9]", "-", cwd)
    files = glob.glob(os.path.join(base, name, "*.jsonl"))
    if not files:
        raise SystemExit(f"このフォルダの会話の記録が見つからない: {os.path.join(base, name)}\n"
                         f"Claude Code を起動したフォルダに移ってから実行するか、記録のファイルを直接指定すること")
    files.sort(key=os.path.getmtime, reverse=True)
    if len(files) < nth:
        raise SystemExit("1つ前の会話の記録がない(このフォルダで Claude Code を使ったのは1回だけ)")
    return files[nth - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", nargs="?", help="会話の記録のファイル。--latest のときは不要")
    ap.add_argument("--latest", action="store_true", help="今いるフォルダの、いちばん新しい会話の記録を自動で探す")
    ap.add_argument("--previous", action="store_true", help="1つ前の会話の記録を探す(Claude Code を起動し直したあと、切れた会話を見たいとき)")
    ap.add_argument("--last", type=int, default=20, help="最後の何件を出すか")
    ap.add_argument("--min-chars", type=int, default=0, help="これより短い発言は出さない")
    a = ap.parse_args()
    if a.latest or a.previous:
        a.jsonl = latest_transcript(nth=2 if a.previous else 1)
        print(f"読んだ記録: {a.jsonl}\n")
    elif not a.jsonl:
        ap.error("記録のファイルを指定するか、--latest を付けること")
    rows = [(t, x) for t, x in user_texts(a.jsonl) if len(x) >= a.min_chars]
    for t, x in rows[-a.last:]:
        print(f"===== {t}\n{x}\n")


if __name__ == "__main__":
    main()
