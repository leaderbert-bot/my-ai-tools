# -*- coding: utf-8 -*-
"""
當沖三招的盤中驗證（用 下載個股分K.bat 抓的 1 分 K；抓到多少算多少，報告會寫涵蓋率）。

  ① 鎖漲停隔天開高空（快樂操盤人）：昨天收盤鎖漲停、今天開高 ≥ 2% → 開盤空、收盤補。
     日 K 版十年每筆 +0.90%、11/11 年，但 33% 的單收盤又鎖漲停補不回來。這裡用 1 分 K 看：
     a. 開盤空、收盤補（收盤鎖漲停的用隔天開盤補，照實算）
     b. 加停損：盤中漲到開盤價 +4% 就補
     c. 加停利：盤中跌到開盤價 −5% 就補
     d. 停損 +4% ＋ 停利 −5%
     e. 10:00 以後才空（等第一波多空打完），收盤補
  ② 恐慌急殺隔天（快樂操盤人）：昨天是飆股 → 今天盤中從最高回落 3% 空、收盤補（日 K 版 +1.1%、10/11 年，但日 K 看不出先後）。
     a. 回落 3% 空、收盤補   b. 加停損：回到當日最高就補   c. 回落 5% 才空
  ③ 處置股（小梁）：處置期間每一天的盤中結構（描述統計，不是策略）：開盤→收盤、開低 2% 買→收盤賣、
     10:00 買→收盤賣、「爆量」那分鐘之後到收盤的報酬（量 ≥ 前 30 分鐘平均 5 倍，當天第一次）。
成本：現股當沖來回 0.32%（手續費 6 折＋當沖稅減半）。成交：觸價就算成交、不算滑價；同一分鐘先碰停損再碰停利算停損（保守）。
昨天鎖漲停、昨收、隔天開盤用 data/k10y 日 K。

用法：雙擊「當沖盤中驗證.bat」，或 python daytrade_1m.py [--since 2020-01-01] [--cost 0.0032]
結果寫到 當沖盤中驗證.md。這是歷史回測，不是投資建議。
"""
import os, sys, json, gzip, glob, bisect, argparse, statistics, collections
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load_1m(R):
    """合併所有電腦的檔：{(code, date): bars}, done 數"""
    bars = {}; done = 0; kinds = collections.Counter()
    for p in sorted(glob.glob(os.path.join(R.DATA_DIR, "stk1m", "stk1m_*.json.gz"))):
        try:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                j = json.load(f)
        except Exception:
            continue
        done += sum(1 for v in (j.get("done") or {}).values() if v != "no-contract")
        for c, days in (j.get("bars") or {}).items():
            for d, b in days.items():
                if len(b.get("t") or []) >= 30:
                    bars[(c, d)] = b
                    for k in b.get("k") or []:
                        kinds[k] += 1
    return bars, done, kinds


def load_daily(R, since):
    px = {}; cal = set()
    d0 = date.fromisoformat(since) - timedelta(days=40)
    cur = date(d0.year, d0.month, 1); today = date.today()
    while cur <= today:
        m = R.k10_load_month("%04d-%02d" % (cur.year, cur.month), cache=False)
        for d, row in (m.get("px") or {}).items():
            cal.add(d)
            for c, v in row.items():
                if len(c) == 4 and c.isdigit() and isinstance(v, list) and len(v) >= 5 and v[3]:
                    px.setdefault(c, {})[d] = v
        cur = date(cur.year + (1 if cur.month == 12 else 0), 1 if cur.month == 12 else cur.month + 1, 1)
    return px, sorted(cal)


def locked(bar, prev, d):
    lim = 1.065 if d < "2015-06-01" else 1.094
    return bool(bar and prev and bar[3] >= prev[3] * lim and bar[3] >= bar[1] * 0.999)


class DT:
    def __init__(self, px, cal):
        self.px, self.cal = px, cal; self.idx = dict((d, i) for i, d in enumerate(cal))

    def prev(self, c, d):
        i = self.idx.get(d)
        return (self.px.get(c) or {}).get(self.cal[i - 1]) if i else None

    def nxt_open(self, c, d):
        i = self.idx.get(d)
        if i is None or i + 1 >= len(self.cal): return None
        b = (self.px.get(c) or {}).get(self.cal[i + 1])
        return float(b[0]) if b and b[0] else None

    def day(self, c, d):
        return (self.px.get(c) or {}).get(d)


def short_trade(b, entry_i, entry_px, stop=None, tp=None, cost=0.0032):
    """從第 entry_i 根之後走到收盤：回傳 (報酬%, 出場方式)。報酬＝空單 (entry/exit − 1)。"""
    n = len(b["t"])
    for j in range(entry_i + 1, n):
        hi, lo = b["h"][j], b["l"][j]
        if stop is not None and hi >= entry_px * (1 + stop):
            return (entry_px / (entry_px * (1 + stop)) - 1) * 100 - cost * 100, "停損"
        if tp is not None and lo <= entry_px * (1 - tp):
            return (entry_px / (entry_px * (1 - tp)) - 1) * 100 - cost * 100, "停利"
    return (entry_px / b["c"][-1] - 1) * 100 - cost * 100, "收盤"


def stat(rows):
    v = [r[0] for r in rows]
    if not v: return "—"
    return "n=%d 平均%+.2f%% 中位%+.2f%% 勝率%.0f%%" % (len(v), statistics.mean(v), statistics.median(v), 100 * sum(1 for x in v if x > 0) / len(v))


def by_year(rows):
    Y = collections.defaultdict(list)
    for r in rows: Y[r[1][:4]].append(r[0])
    return "、".join("%s %+.2f(%d)" % (y, statistics.mean(v), len(v)) for y, v in sorted(Y.items())), sum(1 for v in Y.values() if statistics.mean(v) > 0), len(Y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2020-01-01")
    ap.add_argument("--cost", type=float, default=0.0032)
    ap.add_argument("--out", default=os.path.join(HERE, "當沖盤中驗證.md"))
    a = ap.parse_args()
    import tw_radar as R
    L = ["# 當沖三招：1 分 K 盤中驗證（%s）" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    P = lambda s: (print(s), L.append(s))
    bars, done, kinds = load_1m(R)
    px, cal = load_daily(R, a.since)
    D = DT(px, cal)
    P("- 1 分 K：%d 個（代號×日）有資料；事件種類 %s；成本每筆來回 %.2f%%" % (len(bars), dict(kinds), a.cost * 100))
    if not bars:
        P("  還沒有 1 分 K 資料（先跑「下載個股分K.bat」）。"); return 1
    cost = a.cost
    # ---------- ① 鎖漲停隔天 ----------
    res = collections.defaultdict(list); n_evt = 0; n_open = 0; n_relock = 0
    for (c, d), b in bars.items():
        if "lock+1" not in (b.get("k") or []) or d < a.since: continue
        prev = D.prev(c, d); pprev = None
        i = D.idx.get(d)
        if prev is None or i is None or i < 2: continue
        if not locked(prev, D.px.get(c, {}).get(D.cal[i - 2]), D.cal[i - 1]): continue   # 昨天真的鎖漲停
        n_evt += 1
        o = b["o"][0]
        if o < prev[3] * 1.02: continue                       # 沒開高 2%
        n_open += 1
        today = D.day(c, d)
        relock = locked(today, prev, d)
        if relock: n_relock += 1
        # a. 開盤空、收盤補（鎖漲停補不回來 → 隔天開盤補）
        if relock:
            no = D.nxt_open(c, d)
            ra = ((o / no - 1) * 100 - cost * 100) if no else None
        else:
            ra = (o / b["c"][-1] - 1) * 100 - cost * 100
        if ra is not None: res["a 開盤空收盤補（鎖住就隔天開盤補）"].append((ra, d))
        res["a0 開盤空收盤補（假設都補得回來）"].append(((o / b["c"][-1] - 1) * 100 - cost * 100, d))
        for nm, st, tp in (("b 停損 +4%", 0.04, None), ("c 停利 −5%", None, 0.05), ("d 停損 +4% ＋停利 −5%", 0.04, 0.05)):
            r, how = short_trade(b, 0, o, st, tp, cost)
            if how == "收盤" and relock:
                no = D.nxt_open(c, d)
                if no is None: continue
                r = (o / no - 1) * 100 - cost * 100
            res[nm].append((r, d))
        # e. 10:00 以後才空
        k10 = next((j for j, t in enumerate(b["t"]) if t >= "10:00"), None)
        if k10 is not None and k10 < len(b["t"]) - 5:
            e = b["o"][k10]
            r = (e / b["c"][-1] - 1) * 100 - cost * 100
            if relock:
                no = D.nxt_open(c, d); r = ((e / no - 1) * 100 - cost * 100) if no else None
            if r is not None: res["e 10:00 才空、收盤補"].append((r, d))
    P("")
    P("## ① 鎖漲停隔天開高空")
    P("- 昨天鎖漲停的事件日 %d 個，其中今天開高 ≥ 2%% 的 %d 個；收盤又鎖漲停（補不回來）的 %d 個（%.0f%%）" % (n_evt, n_open, n_relock, 100 * n_relock / max(1, n_open)))
    for nm in sorted(res):
        yr, pos, tot = by_year(res[nm])
        P("- %s：%s；正的年數 %d/%d；逐年 %s" % (nm, stat(res[nm]), pos, tot, yr))
    # ---------- ② 恐慌急殺隔天 ----------
    res2 = collections.defaultdict(list); n2 = 0
    for (c, d), b in bars.items():
        if "panic+1" not in (b.get("k") or []) or d < a.since: continue
        n2 += 1
        prev = D.prev(c, d); today = D.day(c, d); relock = locked(today, prev, d) if prev else False
        for nm, drop, stop_at_high in (("a 回落 3% 空、收盤補", 0.03, False), ("b 回落 3% 空、回到當日最高補（停損）", 0.03, True), ("c 回落 5% 才空、收盤補", 0.05, False)):
            hi = b["h"][0]; ent = None; ei = None
            for j in range(1, len(b["t"])):
                hi = max(hi, b["h"][j])
                if b["l"][j] <= hi * (1 - drop):
                    ent = hi * (1 - drop); ei = j; break
            if ent is None: continue
            r, how = None, "收盤"
            if stop_at_high:
                for j in range(ei + 1, len(b["t"])):
                    if b["h"][j] >= hi:
                        r = (ent / hi - 1) * 100 - cost * 100; how = "停損"; break
            if r is None:
                if relock:
                    no = D.nxt_open(c, d)
                    if no is None: continue
                    r = (ent / no - 1) * 100 - cost * 100
                else:
                    r = (ent / b["c"][-1] - 1) * 100 - cost * 100
            res2[nm].append((r, d))
    P("")
    P("## ② 恐慌急殺隔天")
    P("- 飆股隔天 %d 個事件日" % n2)
    for nm in sorted(res2):
        yr, pos, tot = by_year(res2[nm])
        P("- %s：%s（有觸發 %d／%d）；正的年數 %d/%d；逐年 %s" % (nm, stat(res2[nm]), len(res2[nm]), n2, pos, tot, yr))
    # ---------- ③ 處置股 ----------
    res3 = collections.defaultdict(list); n3 = 0
    for (c, d), b in bars.items():
        if "punish" not in (b.get("k") or []) or d < a.since: continue
        n3 += 1
        prev = D.prev(c, d)
        o, cl = b["o"][0], b["c"][-1]
        res3["開盤買→收盤賣"].append(((cl / o - 1) * 100 - cost * 100, d))
        if prev and o <= prev[3] * 0.98:
            res3["開低 ≥2% 買→收盤賣"].append(((cl / o - 1) * 100 - cost * 100, d))
        k10 = next((j for j, t in enumerate(b["t"]) if t >= "10:00"), None)
        if k10 is not None and k10 < len(b["t"]) - 5:
            res3["10:00 買→收盤賣"].append(((cl / b["o"][k10] - 1) * 100 - cost * 100, d))
        v = b["v"]
        for j in range(30, len(v) - 5):
            base = sum(v[j - 30:j]) / 30.0
            if base > 0 and v[j] >= 5 * base:
                res3["第一次爆量（≥前 30 分鐘 5 倍）那分鐘收盤買→收盤賣"].append(((cl / b["c"][j] - 1) * 100 - cost * 100, d))
                break
    P("")
    P("## ③ 處置股期間的盤中結構（描述，不是策略）")
    P("- 處置期間事件日 %d 個" % n3)
    for nm in sorted(res3):
        yr, pos, tot = by_year(res3[nm])
        P("- %s：%s；正的年數 %d/%d；逐年 %s" % (nm, stat(res3[nm]), pos, tot, yr))
    L += ["", "註：1 分 K 從 2020 起（永豐）。觸價就算成交、不算滑價；當沖空單要借得到券，這裡假設都借得到。",
          "判斷能不能用：照你的標準，每年都要正、而且「鎖住補不回來」照實算之後還要是正的。這是歷史回測，不是投資建議。"]
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("  已寫到 %s" % a.out)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        import traceback; traceback.print_exc()
        print("\n失敗：%s" % str(e)[:300]); sys.exit(1)
