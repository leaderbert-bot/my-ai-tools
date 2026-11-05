# -*- coding: utf-8 -*-
"""
用「財報實際公布時間」（data/fin_pub10.json.gz，下載財報公布日.bat 抓的）重驗兩個上線策略：
  1. 季報意外獲利（快樂操盤人）：單季 EPS 轉虧為盈或意外大賺、公布前 20 個交易日沒先漲 10%；收盤買、抱 16 個交易日收盤賣。
  2. 信用交易恢復（陳信宏）：上一季每股淨值 5～10、這一季 ≥ 10；收盤買、第 6 個交易日開盤賣。

原本的十年回測都是「申報期限（5/15、8/14、11/14、隔年 3/31）後第 1 或第 2 個交易日一起買」。
看好爆發那份已經證明期限日一起買會把報酬算錯（+1% 其實是 +0.02%）。這支把兩種進場並列：
  A 期限後（原本的算法）        B 實際公布後第一個可以買到的收盤（公布時間 13:30 前且是交易日＝當天，否則下一個交易日）
  C 更保守：公布後下一個交易日收盤（不管幾點公布）
同一批訊號、同一套出場，只差進場日，所以差距就是「期限日假設」值多少。

資料：data/fin10.json（十年季報）＋ data/fin_history.json（新的）、data/k10y（十年日 K）、data/fin_pub10.json.gz。
用法：雙擊「財報公布日重驗.bat」，或 python fin_pub_recheck.py [--since 2016-01-01] [--cost 0.0047]
結果寫到 財報公布日重驗.md（1～3 分鐘）。這是歷史回測，不是投資建議。
"""
import os, sys, re, json, gzip, bisect, argparse, statistics, collections
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

DUE = {"1": (0, 5, 15), "2": (0, 8, 14), "3": (0, 11, 14), "4": (1, 3, 31)}
_QW = {"一": 1, "二": 2, "三": 3, "四": 4, "1": 1, "2": 2, "3": 3, "4": 4, "１": 1, "２": 2, "３": 3, "４": 4}


def due_date(q):
    y, n = int(q[:4]), q[5]
    dy, m, d = DUE[n]
    return date(y + dy, m, d)


def qprev(q):
    y, n = int(q[:4]), int(q[5])
    return "%dQ4" % (y - 1) if n == 1 else "%dQ%d" % (y, n - 1)


# ---------------------------------------------------------------- 公布時間
_DT_RE = re.compile(r"(\d{2,4})[/\-.年](\d{1,2})[/\-.月](\d{1,2})[日]?(?:\D{0,3}(\d{1,2}):(\d{2}))?")


def parse_dt(s):
    """'105/05/13 15:21:33'、'2016-05-13 15:21'、'105年5月13日' → (date, 'HH:MM' or '')"""
    m = _DT_RE.search(str(s or ""))
    if not m:
        return None, ""
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 1911:
        y += 1911
    try:
        dd = date(y, mo, d)
    except Exception:
        return None, ""
    hm = ("%02d:%s" % (int(m.group(4)), m.group(5))) if m.group(4) else ""
    return dd, hm


def load_pub(R, FP):
    """(代號, 'YYYYQn') → (公布日 date, 'HH:MM', 來源)。觀測站公告和電子書上傳都有的取較早的。"""
    p = os.path.join(R.DATA_DIR, "fin_pub10.json.gz")
    if not os.path.exists(p):
        return {}, "找不到 data/fin_pub10.json.gz（先雙擊「下載財報公布日.bat」）"
    with gzip.open(p, "rt", encoding="utf-8") as f:
        st = json.load(f)
    out = {}

    def put(c, q, dd, hm, src):
        k = (c, q)
        if dd is None:
            return
        if k not in out or (dd, hm) < (out[k][0], out[k][1]):
            out[k] = (dd, hm, src)
    n_m = n_d = 0
    for row in st.get("mops") or []:
        try:
            dd_s, tt, c, mk, subj = row[0], row[1], row[2], row[3], row[4]
        except Exception:
            continue
        if not FP.is_report(subj):
            continue
        q = FP.quarter_of(subj, dd_s)
        if not q:
            continue
        try:
            dd = date.fromisoformat(dd_s)
        except Exception:
            continue
        put(str(c), q, dd, str(tt or "")[:5], "mops"); n_m += 1
    for row in st.get("doc") or []:
        try:
            c, y, lab, det, t = row[0], row[1], row[2], row[3], row[4]
        except Exception:
            continue
        if "英文" in str(det or ""):
            continue
        m = re.search(r"(\d+)\s*年\s*第\s*([一二三四1-4１-４])\s*季", str(lab or ""))
        if not m:
            continue
        yy = int(m.group(1)); yy = yy + 1911 if yy < 1911 else yy
        q = "%dQ%d" % (yy, _QW[m.group(2)])
        dd, hm = parse_dt(t)
        if dd is None:
            continue
        lag = (dd - due_date(q)).days
        if lag < -120 or lag > 150:      # 上傳時間離期限太遠的（補件、重編）不算
            continue
        put(str(c), q, dd, hm, "doc"); n_d += 1
    return out, "觀測站 %d 則、電子書 %d 筆 → %d 個（公司×季）有實際公布時間" % (n_m, n_d, len(out))


# ---------------------------------------------------------------- 財報
def load_fin(R):
    """{代號: {季: {"eps": 累計 EPS, "bvps": 每股淨值}}}；fin_history 比 fin10 新，同一季以它為準。"""
    fin = {}
    f10 = (R._jload(os.path.join(R.DATA_DIR, "fin10.json"), {}) or {}).get("q") or {}
    for q, slot in f10.items():
        if not (isinstance(q, str) and len(q) == 6 and q[4] == "Q" and isinstance(slot, dict)):
            continue
        for c, rec in slot.items():
            if isinstance(rec, dict):
                fin.setdefault(str(c), {})[q] = {"eps": rec.get("eps"), "bvps": rec.get("bvps")}
    try:
        fh = R.load_fin_history() or {}
    except Exception:
        fh = {}
    for c, slot in fh.items():
        if not isinstance(slot, dict):
            continue
        for q, rec in slot.items():
            if isinstance(q, str) and len(q) == 6 and q[4] == "Q" and isinstance(rec, dict):
                cur = fin.setdefault(str(c), {}).setdefault(q, {})
                if isinstance(rec.get("eps"), (int, float)):
                    cur["eps"] = rec["eps"]
                if isinstance(rec.get("bvps"), (int, float)):
                    cur["bvps"] = rec["bvps"]
    return fin


def eps_single(f, q):
    e = (f.get(q) or {}).get("eps")
    if not isinstance(e, (int, float)):
        return None
    if q[5] == "1":
        return float(e)
    p = (f.get(qprev(q)) or {}).get("eps")
    if not isinstance(p, (int, float)):
        return None
    return float(e) - float(p)


# ---------------------------------------------------------------- 日 K
def load_px(R, since):
    px = {}; cal = set()
    d0 = date.fromisoformat(since) - timedelta(days=60)
    cur = date(d0.year, d0.month, 1); today = date.today()
    while cur <= today:
        ym = "%04d-%02d" % (cur.year, cur.month)
        m = R.k10_load_month(ym, cache=False)
        for d, row in (m.get("px") or {}).items():
            cal.add(d)
            for c, v in row.items():
                if len(c) == 4 and c.isdigit() and isinstance(v, list) and len(v) >= 5 and v[3]:
                    px.setdefault(c, {})[d] = v
        cur = date(cur.year + (1 if cur.month == 12 else 0), 1 if cur.month == 12 else cur.month + 1, 1)
    return px, sorted(cal)


class Mkt:
    def __init__(self, px, cal):
        self.px, self.cal = px, cal
        self.idx = dict((d, i) for i, d in enumerate(cal))

    def first_td_after(self, d, k=1):
        """d（date）之後第 k 個交易日（k=1 就是下一個）"""
        i = bisect.bisect_right(self.cal, d.isoformat())
        j = i + k - 1
        return self.cal[j] if j < len(self.cal) else None

    def on_or_next(self, d):
        i = bisect.bisect_left(self.cal, d.isoformat())
        return self.cal[i] if i < len(self.cal) else None

    def shift(self, dstr, k):
        i = self.idx.get(dstr)
        if i is None:
            return None
        j = i + k
        return self.cal[j] if 0 <= j < len(self.cal) else None

    def bar(self, c, d):
        return (self.px.get(c) or {}).get(d)

    def liquid(self, c, d):
        """進場日前 20 個交易日均量 ≥ 500 張、收盤 ≥ 10；進場日收盤沒鎖漲停"""
        i = self.idx.get(d)
        if i is None or i < 21:
            return False
        s = self.px.get(c) or {}
        vs = [s[x][4] for x in self.cal[i - 20:i] if x in s]
        if len(vs) < 15 or sum(float(v or 0) for v in vs) / 20.0 < 500:
            return False
        b = s.get(d); pb = s.get(self.cal[i - 1])
        if not b or float(b[3]) < 10:
            return False
        if pb and float(b[3]) >= float(pb[3]) * 1.094 and float(b[3]) >= float(b[1]) * 0.999:
            return False
        return True

    def ret_close(self, c, d_in, n, cost):
        d_out = self.shift(d_in, n)
        a, b = self.bar(c, d_in), self.bar(c, d_out) if d_out else None
        if not a or not b:
            return None, None
        return (float(b[3]) / float(a[3]) - 1) * 100 - cost * 100, d_out

    def ret_open(self, c, d_in, n, cost):
        d_out = self.shift(d_in, n)
        a, b = self.bar(c, d_in), self.bar(c, d_out) if d_out else None
        if not a or not b or not b[0]:
            return None, None
        return (float(b[0]) / float(a[3]) - 1) * 100 - cost * 100, d_out

    def run20(self, c, d_ref):
        """d_ref 前 20 個交易日的漲幅（%）：季報意外獲利的「公告前先漲 10% 不買」"""
        i = self.idx.get(d_ref)
        if i is None or i < 21:
            return None
        s = self.px.get(c) or {}
        a, b = s.get(self.cal[i - 21]), s.get(self.cal[i - 1])
        if not a or not b:
            return None
        return (float(b[3]) / float(a[3]) - 1) * 100


# ---------------------------------------------------------------- 訊號
def signals(fin, since):
    """回傳 {"xlev": [(code, q, kind)], "cr": [(code, q)]}"""
    xl, cr = [], []
    y0 = int(since[:4])
    for c, f in fin.items():
        if not (len(c) == 4 and c.isdigit()) or c.startswith("00"):
            continue
        for q in sorted(f):
            if int(q[:4]) < y0 - 1:
                continue
            e = eps_single(f, q)
            if e is not None:
                pq = []
                qq = q
                for _ in range(4):
                    qq = qprev(qq)
                    v = eps_single(f, qq)
                    if v is not None:
                        pq.append(v)
                if len(pq) >= 2:
                    a4 = sum(pq) / len(pq)
                    if e >= 0.1 and pq[0] <= 0 and a4 <= 0.05:
                        xl.append((c, q, "轉虧為盈"))
                    elif e >= 0.5 and e >= 2 * max(a4, 0.15):
                        xl.append((c, q, "意外大賺"))
            bp, bq = (f.get(qprev(q)) or {}).get("bvps"), (f.get(q) or {}).get("bvps")
            if isinstance(bp, (int, float)) and isinstance(bq, (int, float)) and 5 <= bp < 10 and bq >= 10:
                cr.append((c, q))
    return {"xlev": xl, "cr": cr}


def entry_days(M, q, pub):
    """三種進場日：A 期限後第 k 個交易日（呼叫端決定 k）；B 公布後第一個可買到的收盤；C 公布後下一個交易日"""
    due = due_date(q)
    out = {"due": due}
    if pub:
        dd, hm, src = pub
        same = (hm and hm < "13:30") and (dd.isoformat() in M.idx)
        out["B"] = dd.isoformat() if same else M.first_td_after(dd, 1)
        out["C"] = M.first_td_after(dd, 1)
        out["lag"] = (due - dd).days
    return out


def stat(rs):
    v = [r for r in rs if r is not None]
    if not v:
        return "—"
    return "n=%d 平均%+.2f%% 中位%+.2f%% 勝率%.0f%%" % (len(v), statistics.mean(v), statistics.median(v), 100 * sum(1 for x in v if x > 0) / len(v))


def by_year(rows):
    Y = collections.defaultdict(list)
    for d, r in rows:
        Y[d[:4]].append(r)
    return "、".join("%s %+.1f(%d)" % (y, statistics.mean(v), len(v)) for y, v in sorted(Y.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2016-01-01")
    ap.add_argument("--cost", type=float, default=0.0047)
    ap.add_argument("--out", default=os.path.join(HERE, "財報公布日重驗.md"))
    a = ap.parse_args()
    import tw_radar as R
    import fin_pub_dl as FP
    FP.R = R
    L = ["# 用財報實際公布日重驗：季報意外獲利、信用交易恢復（%s）" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    P = lambda s: (print(s), L.append(s))
    pub, msg = load_pub(R, FP)
    P("- 公布時間：%s" % msg)
    if not pub:
        return 1
    fin = load_fin(R)
    px, cal = load_px(R, a.since)
    M = Mkt(px, cal)
    P("- 財報：%d 家；日 K：%d 檔、%s ～ %s；成本每趟來回 %.2f%%" % (len(fin), len(px), cal[0], cal[-1], a.cost * 100))
    S = signals(fin, a.since)
    # 公布時間 vs 期限：分佈
    lags = [(due_date(q) - v[0]).days for (c, q), v in pub.items() if q >= a.since[:4]]
    if lags:
        lags.sort()
        P("- 實際公布比期限早幾天（%d 筆）：中位 %d 天；早 ≥ 5 天的 %.0f%%、期限當天或之後的 %.0f%%" % (
            len(lags), lags[len(lags) // 2], 100 * sum(1 for x in lags if x >= 5) / len(lags), 100 * sum(1 for x in lags if x <= 0) / len(lags)))
    P("")
    for key, title, k_due, hold, how in (("xlev", "季報意外獲利（收盤買、抱 16 個交易日收盤賣）", 2, 16, "close"),
                                        ("cr", "信用交易恢復（收盤買、第 6 個交易日開盤賣）", 1, 5, "open")):
        sig = [s for s in S[key] if due_date(s[1]).isoformat() >= a.since]
        P("## %s" % title)
        P("- 訊號 %d 個（公司×季），其中 %d 個找得到實際公布時間" % (len(sig), sum(1 for s in sig if (s[0], s[1]) in pub)))
        res = {"A": [], "B": [], "C": []}; n_pre = {"A": 0, "B": 0}; n_ill = 0
        rowsA, rowsB = [], []
        for s in sig:
            c, q = s[0], s[1]
            E = entry_days(M, q, pub.get((c, q)))
            dA = M.first_td_after(E["due"], k_due)
            days = {"A": dA, "B": E.get("B"), "C": E.get("C")}
            for v, d_in in days.items():
                if not d_in:
                    continue
                if not M.liquid(c, d_in):
                    if v == "A": n_ill += 1
                    continue
                if key == "xlev":
                    r20 = M.run20(c, d_in)
                    if r20 is not None and r20 >= 10:
                        if v in n_pre: n_pre[v] += 1
                        continue
                r, d_out = (M.ret_close if how == "close" else M.ret_open)(c, d_in, hold, a.cost)
                if r is None:
                    continue
                res[v].append(r)
                if v == "A": rowsA.append((d_in, r))
                if v == "B": rowsB.append((d_in, r))
        P("- A 期限後第 %d 個交易日買（原本）：%s" % (k_due, stat(res["A"])))
        P("- B 實際公布後第一個收盤買：%s" % stat(res["B"]))
        P("- C 公布後下一個交易日收盤買：%s" % stat(res["C"]))
        if key == "xlev":
            P("- 「前 20 個交易日先漲 ≥ 10%% 不買」擋掉：A %d 筆、B %d 筆；流動性不足／鎖漲停剔除 %d 筆" % (n_pre["A"], n_pre["B"], n_ill))
        # 只比兩種都有的同一批（公平比較）
        both = [s for s in sig if (s[0], s[1]) in pub]
        pa, pb = [], []
        for s in both:
            c, q = s[0], s[1]
            E = entry_days(M, q, pub[(c, q)])
            dA, dB = M.first_td_after(E["due"], k_due), E.get("B")
            if not dA or not dB or not M.liquid(c, dA) or not M.liquid(c, dB):
                continue
            if key == "xlev":
                ra, rb = M.run20(c, dA), M.run20(c, dB)
                if (ra is not None and ra >= 10) or (rb is not None and rb >= 10):
                    continue
            f = M.ret_close if how == "close" else M.ret_open
            x, _ = f(c, dA, hold, a.cost); y, _ = f(c, dB, hold, a.cost)
            if x is None or y is None:
                continue
            pa.append(x); pb.append(y)
        if pa:
            d = [y - x for x, y in zip(pa, pb)]
            P("- 同一批 %d 筆、兩種都買得到：A %+.2f%% vs B %+.2f%%，每筆差 %+.2f 個百分點（B 比較好的 %.0f%%）" % (
                len(pa), statistics.mean(pa), statistics.mean(pb), statistics.mean(d), 100 * sum(1 for z in d if z > 0) / len(d)))
        P("- 逐年（A）：%s" % by_year(rowsA))
        P("- 逐年（B）：%s" % by_year(rowsB))
        P("")
    L += ["註：同一套訊號、同一套出場，只差進場日。B 的「13:30 前公布＝當天收盤買」假設你看到公告就能在收盤前掛單；C 是看到隔天才買。",
          "原本十年報告的筆數可能跟這裡不同（這裡的流動性條件：進場前 20 日均量 ≥ 500 張、收盤 ≥ 10、進場日沒鎖漲停）。",
          "這是歷史回測，不是投資建議。"]
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
