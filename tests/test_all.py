"""手引きの部品の動作確認。python3 tests/test_all.py で実行する(Linux。memguard の確認には systemd-run を使う)。
外部と通信しない。一時フォルダの中だけで作業する。
"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = os.path.join(HERE, "..", "files")
sys.path.insert(0, FILES)
ok = ng = 0


def check(name, cond):
    global ok, ng
    print(("OK " if cond else "NG ") + name)
    ok, ng = ok + bool(cond), ng + (not cond)


# --- フック: Claude Code が渡すのと同じ形(標準入力の JSON)で流す -----------------------
HOOK = os.path.join(FILES, "hooks", "block_dangerous.py")


def hook(cmd):
    payload = {"session_id": "t", "hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_input": {"command": cmd, "description": "test"}}
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True)
    return r.returncode


STOP = ["rm -rf ./x", "rm -fr ./x", "rm -Rf ./x", "rm -r -f ./x", "rm --recursive --force x", "rm --force -r x",
        "/bin/rm -rf x", "cd /tmp && rm -rf build", "git reset --hard", "git reset --hard HEAD~1",
        "git checkout -f", "git checkout -- .", "git clean -fd", "git push --force origin main"]
PASS = ["ls -la", "git status", "git push origin main", "git checkout main", "rm file.txt", "rm -r emptydir",
        "echo 'rm -rf is dangerous'", "grep -rf patterns.txt .", "git reset HEAD file.py", "python3 train.py"]
for c in STOP:
    check(f"フック 止める: {c}", hook(c) == 2)
for c in PASS:
    check(f"フック 通す:   {c}", hook(c) == 0)

# --- safe_find: 輪があっても暴走しない・輪を見つける・輪を作らない -------------------------
from safe_find import find_files, find_cyclic_links, safe_symlink
with tempfile.TemporaryDirectory() as t:
    os.makedirs(f"{t}/data/a/b")
    open(f"{t}/data/a/b/x.parquet", "w").write("x")
    os.symlink(f"{t}/data", f"{t}/data/a/b/loop")      # 親を指す輪(事故と同じ形)
    os.makedirs(f"{t}/other"); os.symlink(f"{t}/other", f"{t}/data/ok_link")  # 輪でないリンク
    found = list(find_files(f"{t}/data", suffix=".parquet"))
    check("safe_find 輪があっても1件だけ見つける", len(found) == 1)
    cyc = find_cyclic_links(f"{t}/data")
    check("safe_find 輪を1件見つける(輪でないリンクは数えない)", len(cyc) == 1 and cyc[0][0].endswith("loop"))
    try:
        safe_symlink(f"{t}/data", f"{t}/data/a/new_loop"); made = True
    except ValueError:
        made = False
    check("safe_find 親を指すリンクは作らない", not made and not os.path.lexists(f"{t}/data/a/new_loop"))
    safe_symlink(f"{t}/other", f"{t}/data/a/to_other")
    check("safe_find 輪にならないリンクは作る", os.path.islink(f"{t}/data/a/to_other"))

# --- memguard: 上限なしなら拒否、上限ありなら通す、想定超えで止まる -----------------------------
MG = f"import sys; sys.path.insert(0, {FILES!r}); import memguard; "
r = subprocess.run([sys.executable, "-c", MG + "memguard.require_limit(); print('started')"], capture_output=True, text=True)
check("memguard 上限なしでは起動しない", r.returncode != 0 and "started" not in r.stdout)
r = subprocess.run([sys.executable, "-c", MG + "import time; memguard.require_limit_or_watch(40, 0.3); b=bytearray(600_000_000); time.sleep(3); print('survived')"],
                   capture_output=True, text=True)
check("memguard 上限がない環境では見張りに切り替わり、想定を超えたら止まる", r.returncode == 97 and "survived" not in r.stdout and "警告" in r.stderr)
r = subprocess.run([sys.executable, "-c", MG + "memguard.limit_address_space(1)\ntry:\n    b=bytearray(3_000_000_000); print('allocated')\nexcept MemoryError:\n    print('blocked')"],
                   capture_output=True, text=True)
check("memguard 仮想メモリの上限(1GB)で、3GBの確保は失敗する", "blocked" in r.stdout)

cap = ["systemd-run", "--user", "--scope", "--quiet", "-p", "MemoryMax=2G", "-p", "MemorySwapMax=0"]
try:
    has_scope = subprocess.run(cap + ["true"], capture_output=True, timeout=30).returncode == 0
except (OSError, subprocess.TimeoutExpired):
    has_scope = False
if not has_scope:
    print("-- 飛ばした: この環境では systemd-run --user --scope が使えない(WSL で systemd が無効など)。"
          "上限の確認には require_limit_or_watch か limit_address_space を使う")
else:
    r = subprocess.run(cap + [sys.executable, "-c", MG + "memguard.require_limit(max_gb=4); print('started')"], capture_output=True, text=True)
    check("memguard 上限2GBの下では起動する", r.returncode == 0 and "started" in r.stdout)
    r = subprocess.run(cap + [sys.executable, "-c", MG + "memguard.require_limit(max_gb=1); print('started')"], capture_output=True, text=True)
    check("memguard 上限が許される最大より大きければ起動しない", r.returncode != 0 and "started" not in r.stdout)
    r = subprocess.run(cap + [sys.executable, "-c", MG + "import time; memguard.watch_rss(0.3, interval=0.2); b=bytearray(600_000_000); time.sleep(3); print('survived')"],
                       capture_output=True, text=True)
    check("memguard 想定(0.3GB)を超えたら待たずに止まる", r.returncode == 97 and "survived" not in r.stdout)
    r = subprocess.run(cap + [sys.executable, "-c", MG + "memguard.require_limit_or_watch(4, 1); print('started')"], capture_output=True, text=True)
    check("memguard 上限がある環境では require_limit_or_watch も上限を確かめて起動する", r.returncode == 0 and "started" in r.stdout and "警告" not in r.stderr)

# --- holdout_guard: 期間の混入で止まる・開いた回数を数える・使い切ったら開けない ------------------
from holdout_guard import Holdout, HoldoutError
with tempfile.TemporaryDirectory() as t:
    H = Holdout(start="2025-05-11", ledger=f"{t}/ledger.json", max_opens=1)
    try:
        H.assert_before("2025-05-10"); passed = True
    except HoldoutError:
        passed = False
    check("holdout 答え合わせ期間より前のデータは通す", passed)
    try:
        H.assert_before("2025-06-01"); stopped = False
    except HoldoutError:
        stopped = True
    check("holdout 答え合わせ期間のデータが混ざっていたら止まる", stopped)
    rows = [{"date": "2025-05-10", "y": 1}, {"date": "2025-05-11", "y": 0}, {"date": "2025-07-01", "y": 1}]
    got = H.open(rows, "date", purpose="最終確認: 案A")
    check("holdout 1回目は答え合わせ期間だけを返す", len(got) == 2 and H.opens() == 1)
    try:
        H.open(rows, "date", purpose="もう一度"); reopened = True
    except HoldoutError:
        reopened = False
    check("holdout 使い切ったら2回目は開けない", not reopened)

# --- extract_user_messages: 人間の発言だけを取り出す ------------------------------------------------
from extract_user_messages import user_texts
with tempfile.TemporaryDirectory() as t:
    lines = [
        {"type": "user", "timestamp": "2026-07-14T00:01", "message": {"role": "user", "content": "検証してほしいことが3つある。1つ目は..."}},
        {"type": "assistant", "timestamp": "2026-07-14T00:02", "message": {"role": "assistant", "content": [{"type": "text", "text": "了解"}]}},
        {"type": "user", "timestamp": "2026-07-14T00:03", "message": {"role": "user", "content": [{"type": "tool_result", "content": "ls の結果"}]}},
        {"type": "user", "timestamp": "2026-07-14T00:04", "message": {"role": "user", "content": [{"type": "text", "text": "OK"}]}},
    ]
    open(f"{t}/s.jsonl", "w").write("\n".join(json.dumps(x, ensure_ascii=False) for x in lines))
    got = list(user_texts(f"{t}/s.jsonl"))
    check("会話の記録 人間の発言2件だけ(ツールの結果とAIの発言は除く)", [x for _, x in got] == ["検証してほしいことが3つある。1つ目は...", "OK"])

# --- install_hook: 設定を壊さず書き足す・控えを残す・二重に登録しない・読めない設定には触らない ------------
with tempfile.TemporaryDirectory() as t:
    IH = [sys.executable, os.path.join(FILES, "install_hook.py"), t]
    os.makedirs(f"{t}/.claude")
    json.dump({"permissions": {"deny": ["Bash(rm -rf *)"]}, "hooks": {"PreToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": "echo x"}]}]}},
              open(f"{t}/.claude/settings.json", "w"))
    r = subprocess.run(IH, capture_output=True, text=True)
    st = json.load(open(f"{t}/.claude/settings.json"))
    pre = st["hooks"]["PreToolUse"]
    check("install_hook 既存の設定(deny と別のフック)を残して書き足す", st["permissions"]["deny"] == ["Bash(rm -rf *)"] and len(pre) == 2 and pre[0]["matcher"] == "Edit")
    check("install_hook 元の設定の控えを残す", any(f.startswith("settings.json.bak_") for f in os.listdir(f"{t}/.claude")))
    check("install_hook フック本体を .claude/hooks/ に写す", os.path.exists(f"{t}/.claude/hooks/block_dangerous.py"))
    subprocess.run(IH, capture_output=True, text=True)
    check("install_hook 2回実行しても二重に登録しない", len(json.load(open(f"{t}/.claude/settings.json"))["hooks"]["PreToolUse"]) == 2)
with tempfile.TemporaryDirectory() as t:
    os.makedirs(f"{t}/.claude"); open(f"{t}/.claude/settings.json", "w").write("{ 壊れた設定")
    r = subprocess.run([sys.executable, os.path.join(FILES, "install_hook.py"), t], capture_output=True, text=True)
    check("install_hook 読めない設定には触らずに止まる", r.returncode != 0 and open(f"{t}/.claude/settings.json").read() == "{ 壊れた設定")

# --- capped: 上限をかけて動かす(systemd-run が使える環境だけ) ------------------------------------------
CAP = os.path.join(FILES, "capped")
r = subprocess.run([CAP, "八", "true"], capture_output=True, text=True)
check("capped 上限が数字でなければ止まる", r.returncode == 2)
if has_scope:
    r = subprocess.run([CAP, "1", sys.executable, "-c", MG + "print(round(memguard.current_limit_gb(), 1))"], capture_output=True, text=True)
    check("capped 1GB の上限の下で命令が動く", r.returncode == 0 and r.stdout.strip() == "1.0")
    r = subprocess.run([CAP, "1", sys.executable, "-c", "b=bytearray(3_000_000_000); print('survived')"], capture_output=True, text=True)
    check("capped 上限(1GB)を超えた命令は止められる", r.returncode != 0 and "survived" not in r.stdout)

print(f"\n結果: OK {ok} / NG {ng}")
sys.exit(1 if ng else 0)
