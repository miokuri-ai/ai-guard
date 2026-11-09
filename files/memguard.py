"""memguard.py — 計算を始める前に「メモリの上限がかかっているか」を確かめ、なければ止める。

使い方(計算プログラムの先頭に2行):
    import memguard
    memguard.require_limit(max_gb=40)   # 上限がない/40GBより大きいなら、ここで終了する
    memguard.watch_rss(limit_gb=8)      # 任意: 想定(8GB)を超えたら、待たずに自分を止める

上限のかけ方(Linux, systemd):
    systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0 python3 your_script.py

systemd-run が使えない環境(systemd が無効の WSL など)では:
    memguard.require_limit_or_watch(max_gb=40, watch_gb=8)   # 上限があれば確かめ、なければ見張りで代わりをする
    memguard.limit_address_space(8)                           # GPU を使わない計算なら、仮想メモリに上限をかける

外部と通信しない。標準ライブラリだけを使う。Linux(WSL2 を含む)専用。上限の確認は cgroup v2 前提。
"""
import os
import sys
import threading
import time

GB = 1024 ** 3  # systemd の「G」と同じ数え方(1GB = 1024×1024×1024 バイト)


def _cgroup_dirs():
    """自分のプロセスが属する cgroup と、その祖先のディレクトリを、近い順に返す。"""
    try:
        line = open("/proc/self/cgroup").read().strip().splitlines()[0]
    except OSError:
        return []
    path = line.split("::", 1)[-1]  # cgroup v2 は "0::/user.slice/..." の1行
    dirs = []
    while True:
        dirs.append("/sys/fs/cgroup" + path)
        if path in ("/", ""):
            break
        path = os.path.dirname(path)
    return dirs


def current_limit_gb():
    """自分(と祖先)にかかっているメモリ上限のうち、最も小さいもの(GB)。上限がなければ None。"""
    limits = []
    for d in _cgroup_dirs():
        try:
            v = open(os.path.join(d, "memory.max")).read().strip()
        except OSError:
            continue
        if v != "max":
            limits.append(int(v) / GB)
    return min(limits) if limits else None


def require_limit(max_gb=None):
    """上限がかかっていなければ(または max_gb より大きければ)、理由を出して終了する。"""
    lim = current_limit_gb()
    if lim is None:
        sys.exit("[memguard] メモリの上限がかかっていないので起動しない。"
                 "systemd-run --user --scope -p MemoryMax=<GB>G -p MemorySwapMax=0 で起動し直すこと")
    if max_gb is not None and lim > max_gb:
        sys.exit(f"[memguard] 上限 {lim:.1f}GB は許される最大 {max_gb}GB を超えているので起動しない")
    print(f"[memguard] OK: 上限 {lim:.1f}GB", file=sys.stderr)
    return lim


def rss_gb():
    """自分のプロセスがいま使っている実メモリ(GB)。"""
    for line in open("/proc/self/status"):
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024 / GB  # VmRSS は kB 単位
    return 0.0


def watch_rss(limit_gb, interval=5):
    """裏で見張り、使用量が limit_gb を超えたら、理由を出して自分を止める(待たない)。"""
    def _watch():
        while True:
            used = rss_gb()
            if used > limit_gb:
                print(f"[memguard] 想定 {limit_gb}GB を超えた({used:.1f}GB)ので止める", file=sys.stderr, flush=True)
                os._exit(97)
            time.sleep(interval)
    threading.Thread(target=_watch, daemon=True).start()


def require_limit_or_watch(max_gb, watch_gb):
    """OS の上限があれば require_limit と同じく確かめる。なければ警告を出し、見張り(watch_rss)で代わりをする。

    見張りは OS の上限より弱い(見張りの間隔のあいだに一気に膨らむと間に合わない)。使えるなら OS の上限を使うこと。
    """
    lim = current_limit_gb()
    if lim is not None:
        return require_limit(max_gb)
    print(f"[memguard] 警告: OS のメモリ上限が見つからない。代わりに見張り({watch_gb}GB を超えたら止める)で動かす",
          file=sys.stderr)
    watch_rss(watch_gb, interval=1)
    return None


def limit_address_space(gb):
    """このプロセスが確保できる仮想メモリに上限をかける(超えると MemoryError になる)。

    GPU(CUDA)を使う計算には向かない。CUDA や PyTorch は、実際に使う量よりずっと大きな仮想メモリを
    最初に確保するため、この上限にすぐ当たって起動できないことがある。GPU を使わない計算に限って使う。
    """
    import resource
    b = int(gb * GB)
    resource.setrlimit(resource.RLIMIT_AS, (b, b))


if __name__ == "__main__":
    # そのまま実行すると、いまの上限を表示する(確認用)
    lim = current_limit_gb()
    print("上限なし" if lim is None else f"上限 {lim:.1f}GB")
