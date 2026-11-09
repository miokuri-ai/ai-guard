"""holdout_guard.py — 答え合わせ用のデータ(ホールドアウト)を、プログラムで封印する。

    from holdout_guard import Holdout
    H = Holdout(start="2025-05-11", ledger="holdout_ledger.json", max_opens=1)
    H.assert_before(df["date"].max())      # 探す・選ぶ段階: 答え合わせ期間のデータが混ざっていたら止まる
    test = H.open(df, "date", purpose="最終確認: 案Aの1回きりの採点")  # 開いた回数を台帳に記録。使い切ったら開けない

規則を「書く」代わりに、プログラムが自分で止まるようにする。日付は "YYYY-MM-DD" の文字列で比べる。
台帳(JSON)は人が読める形で残し、何の目的で開いたかを後から確かめられるようにする。外部と通信しない。標準ライブラリだけ。
"""
import datetime
import json
import os


class HoldoutError(RuntimeError):
    pass


class Holdout:
    def __init__(self, start, ledger, max_opens=1):
        self.start = str(start)[:10]   # この日以降が答え合わせ用
        self.ledger = ledger
        self.max_opens = max_opens

    def assert_before(self, latest_date):
        """探す・選ぶ段階で使うデータの最新日が、答え合わせ期間に入っていないことを確かめる。"""
        if str(latest_date)[:10] >= self.start:
            raise HoldoutError(f"答え合わせ用の期間({self.start}以降)のデータが混ざっている: 最新日 {latest_date}")

    def _read(self):
        if not os.path.exists(self.ledger):
            return []
        return json.load(open(self.ledger, encoding="utf-8"))

    def opens(self):
        return len(self._read())

    def open(self, rows, date_key, purpose):
        """答え合わせ用の期間だけを取り出す。開くたびに台帳へ記録し、max_opens を超えたら拒否する。

        rows は「行の並び(辞書など)」か、pandas の DataFrame。date_key は日付の列名。
        """
        log = self._read()
        if len(log) >= self.max_opens:
            raise HoldoutError(f"答え合わせ用の期間は、もう {len(log)} 回開いている(上限 {self.max_opens} 回)。"
                               f"新しく貯まったデータを待つこと。これまで: {[e['purpose'] for e in log]}")
        if not purpose.strip():
            raise HoldoutError("何のために開くのか(purpose)を書くこと")
        log.append({"at": datetime.datetime.now().isoformat(timespec="seconds"), "purpose": purpose})
        json.dump(log, open(self.ledger, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if hasattr(rows, "loc"):  # pandas
            return rows.loc[rows[date_key].astype(str).str[:10] >= self.start]
        return [r for r in rows if str(r[date_key])[:10] >= self.start]
