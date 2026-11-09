"""safe_find.py — フォルダの「輪」(自分の親を指すシンボリックリンク)で暴走しない、ファイル探索と近道づくり。

    from safe_find import find_files, find_cyclic_links, safe_symlink
    for p in find_files("data", suffix=".parquet", min_bytes=20_000_000): ...
    print(find_cyclic_links("data"))          # 親を指すリンクの一覧(0件が正常)
    safe_symlink("/real/data/a", "work/a")    # 親を指すリンクなら作らずに例外

glob.glob('**', recursive=True) はディレクトリへのリンクをたどるため、輪があると道筋が際限なく増える。
ここでは os.walk(followlinks=False)を使い、リンクの先には入らない。外部と通信しない。標準ライブラリだけ。
"""
import os


def find_files(root, suffix="", min_bytes=0, max_entries=1_000_000):
    """root 以下のファイルを、リンクをたどらずに列挙する。数が max_entries を超えたら止める(暴走の保険)。"""
    n = 0
    for d, dirs, files in os.walk(root, followlinks=False):
        for f in files:
            n += 1
            if n > max_entries:
                raise RuntimeError(f"{root} の下に {max_entries} を超える項目がある。探し方か置き場所を見直すこと")
            if not f.endswith(suffix):
                continue
            p = os.path.join(d, f)
            try:
                if os.path.getsize(p) >= min_bytes:
                    yield p
            except OSError:
                pass


def _is_ancestor(target, link):
    """target が link 自身の親(またはそれより上)のフォルダなら True。"""
    t = os.path.realpath(target)
    parent = os.path.realpath(os.path.dirname(os.path.abspath(link)))
    return parent == t or parent.startswith(t + os.sep)


def find_cyclic_links(root):
    """root 以下で、自分の親を指しているディレクトリへのリンクを列挙する。"""
    bad = []
    for d, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = os.path.join(d, name)
            if os.path.islink(p) and os.path.isdir(p) and _is_ancestor(p, p):
                bad.append((p, os.readlink(p)))
    return bad


def safe_symlink(target, link):
    """親を指すリンク(輪になる)なら作らずに例外を出す。そうでなければリンクを作る。"""
    if os.path.isdir(target) and _is_ancestor(target, link):
        raise ValueError(f"{link} -> {target} は自分の親を指すので作らない(フォルダに輪ができる)")
    os.makedirs(os.path.dirname(os.path.abspath(link)), exist_ok=True)
    os.symlink(target, link)


if __name__ == "__main__":
    import sys
    bad = find_cyclic_links(sys.argv[1] if len(sys.argv) > 1 else ".")
    for p, t in bad:
        print(f"輪: {p} -> {t}")
    print(f"親を指すリンク: {len(bad)}件")
