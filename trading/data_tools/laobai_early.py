# -*- coding: utf-8 -*-
"""
老白「修正乖離」早年驗證（2003～2015）＋近十年重現（2016～2026）。
規則照 老白五招_回測.md：
  進場（訊號日收盤買）：當天漲幅全市場前 20 名（只算 20 日均量 ≥ 500 張、價 ≥ 10）、前一天收盤比月線(MA21)低 ≥ 10%、
    紅 K、MACD(12,26,9) 柱狀圖負值第一次收斂、前 5 天量縮（5 日均量 < 20 日均量）。
  出場（課程）：停損＝前 20 天低點（最多 −10%）；賺 5% 停損移到 +1%，賺 10% 移到 +2%，之後每多 10% 再上移 1%；
    黑 K 且 MACD 正值收斂、或爆量（> 2× 20 日均量）黑 K 出；理由消失（隔天柱狀圖又轉弱）出。最多抱 120 天。
  另一版：固定 −7% / +15%。
  大盤偏弱：A 大盤收盤 < 60 日線；B 收盤 < 20 日線；C 大盤 MACD 柱 < 0。大盤＝0050（2003-06-30 起），之前用加權指數。
  帳戶：只在大盤偏弱時做，閒錢放大盤（0050；0050 還沒上市那段用加權指數代替，不含息），每檔 10%，最多 10 檔。

用法（在 00money 資料夾）：
  python laobai_early.py                 # 早年 data/k00y（2003～2015）
  python laobai_early.py --k10y          # 近十年 data/k10y（2016～2026），用來跟原報告對照
  python laobai_early.py --since 2003-01-01 --until 2015-12-31
結果印在畫面並寫到 老白弱勢盤_早年驗證.md。
"""
import os, sys, json, gzip, glob, argparse, statistics, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
COST = 0.0047


# ------------------------------------------------------------------ 載入
def load_k00y(root):
    px = {}; cal = set()
    files = glob.glob(os.path.join(root, "px", "*.json.gz"))
    for f in files:
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                j = json.load(fh)
        except Exception:
            continue
        c = str(j.get("c") or os.path.basename(f)[:4])
        if not (len(c) == 4 and c.isdigit()):
            continue
        slot = {}
        for r in j.get("b") or []:
            try:
                d, o, h, l, cl, vs = r[0], float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5] or 0)
            except Exception:
                continue
            if o and h and l and cl:
                slot[d] = [o, h, l, cl, vs / 1000.0]
                cal.add(d)
        if slot:
            px[c] = slot
    mkt = None
    p = os.path.join(root, "taiex.json")
    if os.path.exists(p):
        tj = json.load(open(p, encoding="utf-8"))
        mkt = {r[0]: float(r[4]) for r in tj.get("b") or [] if r and r[4]}
    print("  k00y：%d 檔、%d 個交易日" % (len(px), len(cal)))
    return px, sorted(cal), mkt


def load_k10y(root):
    px = {}; cal = set()
    for f in sorted(glob.glob(os.path.join(root, "k10_*.json.gz"))):
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                j = json.load(fh)
        except Exception:
            continue
        for d, row in (j.get("px") or {}).items():
            cal.add(d)
            for c, v in row.items():
                if (len(c) == 4 and c.isdigit() or c == "0050") and isinstance(v, list) and len(v) >= 5:
                    px.setdefault(c, {})[d] = v
    print("  k10y：%d 檔、%d 個交易日" % (len(px), len(cal)))
    return px, sorted(cal), None


# ------------------------------------------------------------------ 指標
def ema(x, n):
    out = np.full_like(x, np.nan); a = 2 / (n + 1); prev = np.nan
    for i, val in enumerate(x):
        if np.isnan(val):
            out[i] = np.nan; continue
        prev = val if np.isnan(prev) else prev + a * (val - prev); out[i] = prev
    return out


def sma(x, n):
    out = np.full_like(x, np.nan); cs = np.nancumsum(np.nan_to_num(x)); cnt = np.cumsum(~np.isnan(x))
    for i in range(n - 1, len(x)):
        if cnt[i] - (cnt[i - n] if i >= n else 0) == n:
            out[i] = (cs[i] - (cs[i - n] if i >= n else 0)) / n
    return out


def ffill(x):
    x = x.copy()
    for i in range(1, len(x)):
        if np.isnan(x[i]): x[i] = x[i - 1]
    return x


# ------------------------------------------------------------------ 主程式
def run(px, cal, mkt_idx, since, until, out_md):
    idx = {d: i for i, d in enumerate(cal)}; N = len(cal)

    def arr(code):
        s = px[code]; o = np.full(N, np.nan); h = o.copy(); l = o.copy(); c = o.copy(); v = o.copy()
        for d, row in s.items():
            i = idx.get(d)
            if i is None: continue
            try:
                if row[0] and row[1] and row[2] and row[3]:
                    o[i], h[i], l[i], c[i], v[i] = float(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4] or 0)
            except Exception:
                pass
        return o, h, l, c, v

    # 大盤：0050 有的日子用 0050，沒有的用加權指數（只用來判斷偏弱／當底倉）
    m = np.full(N, np.nan)
    if "0050" in px:
        for d, row in px["0050"].items():
            if d in idx and row[3]: m[idx[d]] = float(row[3])
    if mkt_idx:
        for d, val in mkt_idx.items():
            if d in idx and np.isnan(m[idx[d]]): m[idx[d]] = val
    # 0050 2025-06 一拆四：跟前一個有值的收盤比 < 0.6 視為拆分（拆分前兩天停牌，所以不能只看前一天）
    last = None
    for i in range(N):
        if np.isnan(m[i]): continue
        if last is not None and m[i] / m[last] < 0.6:
            ratio = round(m[last] / m[i]); m[:i] = m[:i] / ratio
        last = i
    # 0050 和加權指數接起來：以第一天有 0050 的那天把加權指數換算成 0050 的尺度
    if "0050" in px and mkt_idx:
        first = next((i for i in range(N) if cal[i] in px["0050"] and px["0050"][cal[i]][3]), None)
        if first is not None and cal[first] in mkt_idx and mkt_idx[cal[first]]:
            k = float(px["0050"][cal[first]][3]) / mkt_idx[cal[first]]
            for i in range(first):
                if cal[i] in mkt_idx: m[i] = mkt_idx[cal[i]] * k
    m = ffill(m)
    ma60 = sma(m, 60); ma20 = sma(m, 20); hist_m = ema(m, 12) - ema(m, 26); hist_m = hist_m - ema(hist_m, 9)
    WEAK = {"A 大盤<60日線": m < ma60, "B 大盤<20日線": m < ma20, "C 大盤MACD柱<0": hist_m < 0}

    codes = [c for c in px if len(c) == 4 and c.isdigit() and len(px[c]) > 300]
    D = {}; ret_day = np.full((len(codes), N), np.nan); v20 = np.full((len(codes), N), np.nan); closes = np.full((len(codes), N), np.nan)
    for k, code in enumerate(codes):
        o, h, l, c, v = arr(code); D[code] = (o, h, l, c, v)
        with np.errstate(invalid="ignore", divide="ignore"):
            ret_day[k] = c / np.concatenate([[np.nan], c[:-1]]) - 1
        v20[k] = sma(v, 20); closes[k] = c
    liq = (v20 >= 500) & (closes >= 10)
    rank_ok = np.zeros((len(codes), N), bool)
    for i in range(N):
        col = np.where(liq[:, i], ret_day[:, i], np.nan)
        if np.sum(~np.isnan(col)) < 20: continue
        rank_ok[np.argsort(-np.nan_to_num(col, nan=-9))[:20], i] = True
    i_since = next((i for i in range(N) if cal[i] >= since), 30); i_until = max(i for i in range(N) if cal[i] <= until)
    SIG = []; IND = {}
    for k, code in enumerate(codes):
        o, h, l, c, v = D[code]; ma21 = sma(c, 21); dif_ = ema(c, 12) - ema(c, 26); hist = dif_ - ema(dif_, 9); v5 = sma(v, 5)
        IND[code] = (hist, v20[k])
        for i in range(max(30, i_since), min(i_until, N - 1)):
            if not rank_ok[k, i] or np.isnan(ma21[i - 1]) or np.isnan(hist[i - 2]): continue
            if not (c[i - 1] <= ma21[i - 1] * 0.90 and c[i] > o[i]): continue
            if not (hist[i] < 0 and hist[i] > hist[i - 1] and hist[i - 1] <= hist[i - 2]): continue
            if not (v5[i] < v20[k][i]): continue
            SIG.append((code, i))

    def trade(code, i, mode):
        o, h, l, c, v = D[code]; hist, v20_ = IND[code]
        entry = c[i]; stop = max(np.nanmin(l[i - 20:i + 1]), entry * 0.90) if mode == "course" else entry * 0.93
        peak = 0.0
        for j in range(i + 1, min(i + 121, N)):
            if np.isnan(c[j]): continue
            g = c[j] / entry - 1; peak = max(peak, g)
            if mode == "fixed":
                if c[j] <= stop or g >= 0.15: return j, (c[j] / entry - 1) * 100 - COST * 100
                continue
            if peak >= 0.10: stop = max(stop, entry * (1.02 + 0.01 * int((peak - 0.10) // 0.10)))
            elif peak >= 0.05: stop = max(stop, entry * 1.01)
            if c[j] <= stop: return j, (c[j] / entry - 1) * 100 - COST * 100
            black = c[j] < o[j]
            if black and hist[j] > 0 and hist[j] < hist[j - 1]: return j, (c[j] / entry - 1) * 100 - COST * 100
            if black and v[j] > 2 * v20_[j]: return j, (c[j] / entry - 1) * 100 - COST * 100
            if j == i + 1 and hist[j] < hist[j - 1]: return j, (c[j] / entry - 1) * 100 - COST * 100
        j = min(i + 120, N - 1); return j, (c[j] / entry - 1) * 100 - COST * 100

    def S(xs):
        return "n=%d 平均%+.2f%% 中位%+.2f%% 勝率%.0f%%" % (len(xs), statistics.mean(xs), statistics.median(xs), 100 * sum(1 for x in xs if x > 0) / len(xs)) if xs else "—"

    lines = ["# 老白「修正乖離」回測 %s～%s" % (cal[i_since], cal[i_until]), "", "訊號 %d 筆。大盤＝0050（沒有的日子用加權指數）。" % len(SIG), ""]
    def P(s): print(s); lines.append(s)
    results = {}
    for mode in ("course", "fixed"):
        T = [(code, i) + trade(code, i, mode) for code, i in SIG]
        P("## 出場：%s" % ("課程規則" if mode == "course" else "固定 −7%／+15%"))
        P("- 全部：%s，平均抱 %.1f 天" % (S([t[3] for t in T]), statistics.mean(t[2] - t[1] for t in T) if T else 0))
        ys = collections.defaultdict(list)
        for t in T: ys[cal[t[1]][:4]].append(t[3])
        P("- 逐年正的年數 %d/%d：%s" % (sum(1 for y in ys if statistics.mean(ys[y]) > 0), len(ys), "、".join("%s %+.1f" % (y, statistics.mean(ys[y])) for y in sorted(ys))))
        for nm, w in WEAK.items():
            a = [t[3] for t in T if w[t[1]]]; b = [t[3] for t in T if not w[t[1]]]
            ya = collections.defaultdict(list)
            for t in T:
                if w[t[1]]: ya[cal[t[1]][:4]].append(t[3])
            P("- %s：偏弱 %s（年正 %d/%d）｜偏多 %s" % (nm, S(a), sum(1 for y in ya if statistics.mean(ya[y]) > 0), len(ya), S(b)))
        results[mode] = T
        # 帳戶：只在偏弱做、閒錢放大盤、每檔 10%、最多 10 檔
        for nm, w in WEAK.items():
            units = 1.0 / m[i_since]; pos = []; eq0 = 1.0; eq = []
            byday = collections.defaultdict(list)
            for t in T:
                if w[t[1]]: byday[t[1]].append(t)
            for i in range(i_since, i_until + 1):
                keep = []
                for p in pos:
                    if p["out"] == i:
                        units += p["sh"] * D[p["code"]][3][i] * (1 - COST) / m[i]
                    else: keep.append(p)
                pos = keep
                equity = units * m[i] + sum(p["sh"] * (D[p["code"]][3][i] if not np.isnan(D[p["code"]][3][i]) else p["px"]) for p in pos)
                for t in byday.get(i, []):
                    if len(pos) >= 10: continue
                    amt = min(equity * 0.10, units * m[i] * 0.997)
                    if amt <= 0: continue
                    units -= amt / 0.997 / m[i]
                    pos.append(dict(code=t[0], sh=amt * (1 - COST) / D[t[0]][3][i], out=t[2], px=D[t[0]][3][i]))
                eq.append(units * m[i] + sum(p["sh"] * (D[p["code"]][3][i] if not np.isnan(D[p["code"]][3][i]) else p["px"]) for p in pos))
            yrs = (i_until - i_since) / 245.0
            cagr = (eq[-1] / eq[0]) ** (1 / yrs) - 1; bench = (m[i_until] / m[i_since]) ** (1 / yrs) - 1
            peak = 0; mdd = 0
            for e in eq:
                peak = max(peak, e); mdd = min(mdd, e / peak - 1)
            P("- 帳戶（%s 偏弱才做，閒錢放大盤）：年化 %.1f%%、最大回撤 %.1f%%；大盤（不含息）年化 %.1f%%" % (nm, cagr * 100, mdd * 100, bench * 100))
        P("")
    lines += ["註：大盤含息沒有算（0050 配息、加權指數股息都沒加回），所以「閒錢放大盤」的年化偏低 2～4 個百分點，策略和大盤都一樣少，比較差距時影響小。",
              "這是歷史回測，不是投資建議。"]
    with open(out_md, "w", encoding="utf-8") as f: f.write("\n".join(lines) + "\n")
    print("  已寫到 %s" % out_md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k10y", action="store_true", help="用近十年 data/k10y 跑（對照原報告）")
    ap.add_argument("--root", default=None, help="資料夾（預設 data/k00y 或 data/k10y）")
    ap.add_argument("--since", default=None); ap.add_argument("--until", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.k10y:
        px, cal, mkt = load_k10y(a.root or os.path.join(DATA, "k10y"))
        since, until = a.since or "2016-01-01", a.until or "2026-12-31"
        out = a.out or os.path.join(HERE, "老白弱勢盤_近十年重現.md")
    else:
        px, cal, mkt = load_k00y(a.root or os.path.join(DATA, "k00y"))
        since, until = a.since or "2003-01-01", a.until or "2015-12-31"
        out = a.out or os.path.join(HERE, "老白弱勢盤_早年驗證.md")
    if not cal:
        print("  沒有資料。"); return 1
    run(px, cal, mkt, since, until, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
