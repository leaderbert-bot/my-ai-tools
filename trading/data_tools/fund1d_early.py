# -*- coding: utf-8 -*-
"""
基本面 1／D（和 基本面版、★）的早年驗證：2003～2015，用 data/k00y（FinMind 日 K、月營收、季報 EPS、除權息、加權指數）。
規則照 2016～2026 十年版（雷達 live_signals）：
  點位 pt/ex ∈ 123567ABCD（800 根窗口、每天重算）；近 3 月平均營收創 12 個月新高；TTM EPS > 去年同期 TTM 且 > 0；
  20 日均量 ≥ 500 張、收盤 ≥ 10；收盤沒鎖漲停（2015-06 以前 7%：收 ≥ 昨收 ×1.065 且＝最高）；0050 在季線上（2003-09-22 前用加權指數季線）
  fundall＝任一點位；fund1D＝點位只限 1、D；fundhi＝再加 收盤 ≥ 近 250 日最高 95%
  帳戶：6 槽、每天最多 3 檔、收盤買、第 20 個交易日收盤賣、成本 0.47%
  資料處理照早年回測報告：上市日前（興櫃）的 K 棒不用；上櫃股 2006-11-25～2007-06-30 的訊號不用；除權息用 FinMind 結果還原；
  財報期限 2012 年度以前舊制（4/30、8/31、10/31、隔年 4/30），2013 起新制；月營收公布月 11 日起可用；FinMind EPS 是單季。
排序：原本「均量大先」、隨機 30 次、以及 11/05 排序測試選的「當天創新高優先、同級均量大先」（早年是它沒看過的資料，順便驗）。

用法：雙擊「基本面1D早年驗證.bat」，或 python fund1d_early.py [--since 2003-01-01] [--until 2015-12-31]
約 1～2 小時（候選名單會存成 fund1d_early_cands.pkl，第二次跑只要幾分鐘）。結果寫到 基本面1D早年驗證.md。這是歷史回測，不是投資建議。
"""
import os, sys, json, gzip, glob, bisect, pickle, random, argparse, statistics, collections, time
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
COST = 0.0047; HOLD = 20; SLOTS = 6; CAP = 3
OTC_GAP = ("2006-11-25", "2007-06-30")


# ---------------------------------------------------------------- 載入
def jgz(p):
    try:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_list(root):
    L = {}
    try:
        with open(os.path.join(root, "list.json"), encoding="utf-8") as f:
            for x in (json.load(f).get("codes") or []):
                L[str(x.get("c"))] = x
    except Exception:
        pass
    return L


def load_px(root, L):
    """{code: {d: [o,h,l,c,v張]}}；上市日前的不用；已下市的用「超過漲跌停」痕跡切；除權息還原。"""
    px = {}; cal = set()
    divs = {}
    for f in glob.glob(os.path.join(root, "div", "*.json.gz")):
        j = jgz(f)
        if j and j.get("r"):
            divs[str(j.get("c"))] = j["r"]
    for f in glob.glob(os.path.join(root, "px", "*.json.gz")):
        j = jgz(f)
        if not j:
            continue
        c = str(j.get("c") or os.path.basename(f)[:4])
        if not (len(c) == 4 and c.isdigit()):
            continue
        rows = []
        for r in j.get("b") or []:
            try:
                d, o, h, l, cl, vs = r[0], float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5] or 0)
            except Exception:
                continue
            if o > 0 and h > 0 and l > 0 and cl > 0 and l <= min(o, cl) and h >= max(o, cl):
                rows.append([d, o, h, l, cl, vs / 1000.0])
        if not rows:
            continue
        rows.sort(key=lambda r: r[0])
        meta = L.get(c) or {}
        start = str(meta.get("d") or "")[:10]
        if start and len(start) == 10 and start > "1990-01-01":
            rows = [r for r in rows if r[0] >= start]
        else:                                           # 沒有上市日（下市股）：最後一次「超過漲跌停」之後才算乾淨
            last_bad = -1
            for i in range(1, len(rows)):
                lim = 0.075 if rows[i][0] < "2015-06-01" else 0.105
                if abs(rows[i][4] / rows[i - 1][4] - 1) > lim:
                    last_bad = i
            if last_bad >= 0:
                rows = rows[last_bad + 1:]
        # 除權息還原：除權息日之前的價格乘 ref/before
        for ev in divs.get(c) or []:
            try:
                d0, before, ref = ev[0], float(ev[1] or 0), float(ev[3] or 0)
            except Exception:
                continue
            if before <= 0 or ref <= 0 or ref >= before:
                continue
            k = ref / before
            for r in rows:
                if r[0] < d0:
                    r[1] *= k; r[2] *= k; r[3] *= k; r[4] *= k
        slot = {}
        for r in rows:
            slot[r[0]] = r[1:]
            cal.add(r[0])
        if slot:
            px[c] = slot
    return px, sorted(cal)


def load_taiex(root):
    j = None
    try:
        with open(os.path.join(root, "taiex.json"), encoding="utf-8") as f:
            j = json.load(f)
    except Exception:
        return {}
    out = {}
    for r in j.get("b") or []:
        try:
            out[str(r[0])[:10]] = float(r[4])
        except Exception:
            pass
    return out


def load_rev(root):
    """{code: {YYYYMM: (revenue, 可用日期 ISO)}}；FinMind 的 date 是公布那個月，11 日起可用"""
    out = {}
    for f in glob.glob(os.path.join(root, "rev", "*.json.gz")):
        j = jgz(f)
        if not j:
            continue
        c = str(j.get("c")); m = {}
        for r in j.get("r") or []:
            try:
                y, mo, v, d = int(r[0]), int(r[1]), r[2], str(r[3])[:10]
            except Exception:
                continue
            if not isinstance(v, (int, float)):
                continue
            try:
                pd = date.fromisoformat(d)
            except Exception:
                pd = date(y + (1 if mo == 12 else 0), 1 if mo == 12 else mo + 1, 1)
            avail = date(pd.year, pd.month, 11).isoformat()
            m["%04d%02d" % (y, mo)] = (float(v), avail)
        if m:
            out[c] = m
    return out


def load_fin(root):
    """{code: {YYYYQn: 單季 EPS}}（FinMind type EPS 是單季）"""
    out = {}
    for f in glob.glob(os.path.join(root, "fin", "*.json.gz")):
        j = jgz(f)
        if not j:
            continue
        c = str(j.get("c")); m = {}
        for r in j.get("r") or []:
            try:
                d, t, v = str(r[0])[:10], str(r[1]), r[2]
            except Exception:
                continue
            if t != "EPS" or not isinstance(v, (int, float)):
                continue
            y, mo = int(d[:4]), int(d[5:7])
            q = "%dQ%d" % (y, (mo - 1) // 3 + 1)
            m[q] = float(v)
        if m:
            out[c] = m
    return out


def due(q):
    y, n = int(q[:4]), int(q[5])
    if y <= 2012:
        return [date(y, 4, 30), date(y, 8, 31), date(y, 10, 31), date(y + 1, 4, 30)][n - 1]
    return [date(y, 5, 15), date(y, 8, 14), date(y, 11, 14), date(y + 1, 3, 31)][n - 1]


def qprev(q, k=1):
    y, n = int(q[:4]), int(q[5])
    for _ in range(k):
        y, n = (y - 1, 4) if n == 1 else (y, n - 1)
    return "%dQ%d" % (y, n)


def ym_prev(ym, k):
    y, m = int(ym[:4]), int(ym[4:]); m -= k
    while m <= 0:
        m += 12; y -= 1
    return "%04d%02d" % (y, m)


def fund_tables(R, E):
    """每個營收月的 hi3；每季的 tg。回傳 (rows_m, rows_q, m_av, q_av)"""
    rows_m = {}
    for ym in sorted(R):
        v = R[ym][0]
        means = []
        for lag in range(0, 12):
            trio = [R.get(ym_prev(ym, lag + j)) for j in range(3)]
            means.append(sum(x[0] for x in trio) / 3 if None not in trio else None)
        prev = [x for x in means[1:] if x is not None]
        rows_m[ym] = (means[0] is not None and len(prev) >= 9 and means[0] >= max(prev))
    rows_q = {}
    for q in sorted(E):
        t0 = [E.get(qprev(q, k)) for k in range(4)]
        t1 = [E.get(qprev(q, k)) for k in range(4, 8)]
        if None in t0 or None in t1:
            rows_q[q] = None
        else:
            rows_q[q] = (sum(t0) > sum(t1) and sum(t0) > 0)
    m_av = sorted((R[ym][1], ym) for ym in rows_m)
    q_av = sorted((due(q).isoformat(), q) for q in rows_q)
    return rows_m, rows_q, m_av, q_av


def latest(av, d, strict):
    best = None
    for a, k in av:
        if (a < d) if strict else (a <= d):
            best = k
        else:
            break
    return best


# ---------------------------------------------------------------- 候選
def build_cands(Rd, px, cal, taiex, rev, fin, L, since, until, log):
    idx = dict((d, i) for i, d in enumerate(cal))
    # 大盤季線：0050 從 2003-09-22 起，之前加權指數
    c50 = []; last = None
    for d in cal:
        v = (px.get("0050") or {}).get(d); last = v[3] if v else last; c50.append(last)
    tx = []; last = None
    for d in cal:
        last = taiex.get(d, last); tx.append(last)
    mkt_ok = [False] * len(cal)
    for i in range(59, len(cal)):
        use50 = cal[i] >= "2003-09-22" and all(c50[i - 59:i + 1])
        w = c50[i - 59:i + 1] if use50 else tx[i - 59:i + 1]
        if None not in w and w[-1]:
            mkt_ok[i] = w[-1] > sum(w) / 60
    KCtx, KScan = Rd.KCtx, Rd.KScan
    cands = []; t0 = time.time(); n_scan = 0
    codes = sorted(c for c in px if c != "0050" and not c.startswith("00"))
    for ci, c in enumerate(codes):
        if c not in rev or c not in fin:
            continue
        rows_m, rows_q, m_av, q_av = fund_tables(rev[c], fin[c])
        s = px[c]; ds = sorted(s)
        if len(ds) < 400:
            continue
        bars = [(date.fromisoformat(d), s[d][0], s[d][1], s[d][2], s[d][3]) for d in ds]
        cl = [s[d][3] for d in ds]; vol = [s[d][4] for d in ds]
        is_otc = "tpex" in str((L.get(c) or {}).get("t") or "").lower() or "otc" in str((L.get(c) or {}).get("t") or "").lower()
        for k in range(399, len(ds)):
            d = ds[k]
            if d < since or d > until or d not in idx or not mkt_ok[idx[d]]:
                continue
            if is_otc and OTC_GAP[0] <= d <= OTC_GAP[1]:
                continue
            if cl[k] < 10:
                continue
            v20 = sum(vol[k - 19:k + 1]) / 20.0
            if v20 < 500:
                continue
            lim = 1.065 if d < "2015-06-01" else 1.094
            if cl[k] >= cl[k - 1] * lim and cl[k] >= bars[k][2] * 0.999:
                continue
            ym = latest(m_av, d, False); q = latest(q_av, d, True)
            if not ym or not q or not rows_m.get(ym):
                continue
            tg = rows_q.get(q)
            if tg is None:                               # 缺季：沿用上一季
                qq = qprev(q); tg = rows_q.get(qq)
            if not tg:
                continue
            n_scan += 1
            sub = bars[max(0, k - 799):k + 1]
            sc = KScan(KCtx(sub), max_segments=40).run()
            tag = (sc.mc[0] or sc.me[0] or "").strip("$")
            if not tag or tag not in "123567ABCD":
                continue
            hi = max(cl[k - 249:k + 1]); phi = cl[k] / hi
            cands.append(dict(d=d, code=c, tag=tag, phi=phi, v20=v20, px=cl[k]))
        if ci % 100 == 0:
            el = time.time() - t0
            log("  %4d/%d %s  候選 %d  掃描 %d  %.0f 分（估計還要 %.0f 分）" % (ci, len(codes), c, len(cands), n_scan, el / 60, el / 60 / max(1, ci) * (len(codes) - ci)))
    return cands


# ---------------------------------------------------------------- 帳戶模擬
def simulate(cands, px, cal, since, until, keyfn=None, seed=None, cap=CAP):
    idx = dict((d, i) for i, d in enumerate(cal))
    byday = collections.defaultdict(list)
    for c in cands:
        byday[c["d"]].append(c)
    rng = random.Random(seed) if seed is not None else None

    def close_near(code, d):
        i = idx[d]
        for j in range(i, max(-1, i - 10), -1):
            v = (px.get(code) or {}).get(cal[j])
            if v: return v[3]
        return None
    i0 = bisect.bisect_left(cal, since); i1 = min(bisect.bisect_right(cal, until) - 1, len(cal) - 1)
    cash = 1.0; pos = []; eq = []; trades = []
    for i in range(i0, i1 + 1):
        d = cal[i]; keep = []
        for p in pos:
            if p["out"] == d or i == i1:
                c = close_near(p["code"], d) or p["last"]
                cash += p["sh"] * c * (1 - COST / 2)
                trades.append(dict(ret=(c / p["in"] - 1) * 100 - COST * 100, d=p["d"]))
            else:
                keep.append(p)
        pos = keep
        e = cash + sum(p["sh"] * (close_near(p["code"], d) or p["last"]) for p in pos)
        eq.append((d, e))
        Lc = list(byday.get(d, []))
        if not Lc:
            continue
        if rng is not None:
            rng.shuffle(Lc)
        if keyfn is not None:
            Lc.sort(key=keyfn)
        held = set(p["code"] for p in pos); buys = 0
        for c in Lc:
            if c["code"] in held: continue
            if len(pos) >= SLOTS or (cap and buys >= cap): break
            if i + HOLD > i1: continue
            amt = min(cash, e / SLOTS)
            if amt <= 1e-9: break
            sh = amt / (c["px"] * (1 + COST / 2)); cash -= amt
            pos.append(dict(code=c["code"], sh=sh, out=cal[i + HOLD], d=d, last=c["px"], **{"in": c["px"]})); held.add(c["code"]); buys += 1
    return stats(eq, trades, idx)


def stats(eq, tr, idx):
    d0, e0 = eq[0]; d1, e1 = eq[-1]
    yrs = (idx[d1] - idx[d0]) / 245.0
    cagr = (e1 / e0) ** (1 / yrs) - 1 if yrs > 0 and e1 > 0 else -1
    peak = -1; mdd = 0
    for d, e in eq:
        peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    last_e = {}
    for d, e in eq: last_e[d[:4]] = e
    yr = {}; base = e0
    for y in sorted(last_e): yr[y] = (last_e[y] / base - 1) * 100; base = last_e[y]
    return dict(cagr=cagr * 100, mdd=mdd * 100, n=len(tr), win=100 * sum(1 for t in tr if t["ret"] > 0) / max(1, len(tr)),
                avg=statistics.mean(t["ret"] for t in tr) if tr else 0, yr=yr)


def bench(series, cal, since, until):
    idx = dict((d, i) for i, d in enumerate(cal))
    eq = [(d, series[i]) for i, d in enumerate(cal) if since <= d <= until and series[i]]
    if len(eq) < 2:
        return None
    return stats(eq, [], idx)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2003-01-01")
    ap.add_argument("--until", default="2015-12-31")
    ap.add_argument("--root", default=None)
    ap.add_argument("--out", default=os.path.join(HERE, "基本面1D早年驗證.md"))
    a = ap.parse_args()
    import tw_radar as Rd
    root = a.root or os.path.join(Rd.DATA_DIR, "k00y")
    L = ["# 基本面 1／D 早年驗證（2003～2015，%s）" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    def log(s): print(s, flush=True)
    def P(s): print(s); L.append(s)
    Lst = load_list(root)
    px, cal = load_px(root, Lst)
    taiex = load_taiex(root); rev = load_rev(root); fin = load_fin(root)
    P("- 資料：日 K %d 檔、%d 個交易日（%s ～ %s）；月營收 %d 檔、季報 %d 檔、加權指數 %d 天" % (len(px), len(cal), cal[0] if cal else "", cal[-1] if cal else "", len(rev), len(fin), len(taiex)))
    if not px or not rev or not fin:
        P("  k00y 資料不齊（要先在雷達抓完 2000～2015 早年資料）。"); return 1
    cache = os.path.join(HERE, "fund1d_early_cands.pkl")
    cands = None
    if os.path.exists(cache):
        try:
            ck = pickle.load(open(cache, "rb"))
            if ck.get("since") == a.since and ck.get("until") == a.until and ck.get("n_px") == len(px):
                cands = ck["cands"]; log("  用上次存的候選名單（%d 筆）" % len(cands))
        except Exception:
            cands = None
    if cands is None:
        log("  重算候選名單（每一天重跑循環點，約 1～2 小時）…")
        cands = build_cands(Rd, px, cal, taiex, rev, fin, Lst, a.since, a.until, log)
        pickle.dump({"since": a.since, "until": a.until, "n_px": len(px), "cands": cands}, open(cache, "wb"))
    P("- 候選（任一點位＋營收創高＋TTM EPS 成長＋流動性＋大盤季線上）：%d 筆、%d 天" % (len(cands), len(set(c["d"] for c in cands))))
    # 大盤對照
    tx = []; last = None
    for d in cal: last = taiex.get(d, last); tx.append(last)
    c50 = []; last = None
    for d in cal:
        v = (px.get("0050") or {}).get(d); last = v[3] if v else last; c50.append(last)
    bt = bench(tx, cal, a.since, a.until); b5 = bench(c50, cal, max(a.since, "2003-07-01"), a.until)
    P("- 加權指數（不含息）年化 %.1f%%、回撤 %.1f%%；0050（2003-07 起、已含除權息還原）年化 %s、回撤 %s" % (
        bt["cagr"] if bt else 0, bt["mdd"] if bt else 0, ("%.1f%%" % b5["cagr"]) if b5 else "—", ("%.1f%%" % b5["mdd"]) if b5 else "—"))
    P("")
    VAR = [("基本面版 fundall（任一點位）", lambda c: True), ("基本面 1／D fund1D（點位 1、D）", lambda c: c["tag"] in "1D"),
           ("★ fundhi（再加收盤 ≥ 一年高 95%）", lambda c: c["phi"] >= 0.95), ("★ 99% 版", lambda c: c["phi"] >= 0.99),
           ("1／D 再加一年高 95%", lambda c: c["tag"] in "1D" and c["phi"] >= 0.95)]
    ORD = [("均量大先（原本）", lambda c: -c["v20"]), ("創新高優先，同級均量大先（11/05 新規則）", lambda c: (0 if c["phi"] >= 0.9999 else 1, -c["v20"]))]
    P("| 策略 | 排序 | 年化 | 最大回撤 | 筆數 | 勝率 | 每筆 | 虧損年數 | 最差一年 |")
    P("|---|---|---|---|---|---|---|---|---|")
    allres = {}
    for vn, vf in VAR:
        C = [c for c in cands if vf(c)]
        for on, of in ORD:
            s = simulate(C, px, cal, a.since, a.until, keyfn=of); allres[(vn, on)] = s
            neg = sum(1 for v in s["yr"].values() if v < 0); worst = min(s["yr"].values()) if s["yr"] else 0
            P("| %s | %s | %.1f%% | %.1f%% | %d | %.0f%% | %+.2f%% | %d/%d | %+.1f%% |" % (vn, on, s["cagr"], s["mdd"], s["n"], s["win"], s["avg"], neg, len(s["yr"]), worst))
        rs = sorted(simulate(C, px, cal, a.since, a.until, seed=k)["cagr"] for k in range(30))
        P("| %s | 隨機 30 次 | 中位 %.1f%%（最低 %.1f、最高 %.1f） | | | | | | |" % (vn, rs[15], rs[0], rs[-1]))
        allres[(vn, "隨機中位")] = rs[15]
    P("")
    ys = sorted(set(y for (vn, on), s in allres.items() if isinstance(s, dict) for y in s["yr"]))
    P("逐年（%，均量大先）：")
    P("| 策略 | " + " | ".join(ys) + " |")
    P("|---|" + "---|" * len(ys))
    if bt:
        P("| 加權指數 | " + " | ".join("%+.0f" % bt["yr"].get(y, 0) for y in ys) + " |")
    for vn, _ in VAR:
        s = allres[(vn, "均量大先（原本）")]
        P("| %s | " % vn + " | ".join("%+.0f" % s["yr"].get(y, 0) for y in ys) + " |")
    L += ["", "註：跟早年回測報告對照——那份 ★（fundhi）2003～2015 年化 +14.3%／回撤 −24.6%、基本面版 +7.1%／−36.8%。這裡的資料處理（興櫃切法、除權息）是近似版，數字會有差，但同一支程式裡各策略之間的比較是公平的。",
          "判斷 1／D 能不能用：照你的標準，早年要跟近年同向（近年 1／D 27%、回撤最小），而且不能只靠一兩年。", "這是歷史回測，不是投資建議。"]
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("  已寫到 %s" % a.out)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中斷。"); sys.exit(130)
    except Exception as e:
        import traceback; traceback.print_exc()
        print("\n失敗：%s" % str(e)[:300]); sys.exit(1)
