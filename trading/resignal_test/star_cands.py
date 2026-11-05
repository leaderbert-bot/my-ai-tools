"""重建 ★（fundhi）每一天的完整候選名單（含因為槽滿／每天 3 檔上限沒買到的），給「候選排序」測試用。
規則照雷達 live_signals／_fund_flags_all（子代理人整理）：
  點位 pt 或 ex ∈ 123567ABCD（800 根窗口、點位當天重算，跟 resignal.py 一樣）
  fb[1] 近 3 月平均營收創 12 個月新高（營收隔月 11 日起可用）
  fb[3] TTM EPS > 去年同期 TTM 且 > 0（季報申報期限後可用：5/15、8/14、11/14、隔年 3/31）
  收盤 / 近 250 日最高 ≥ 0.95；0050 收盤 > 60 日均；20 日均量 ≥ 500 張；收盤 ≥ 10；收盤沒鎖漲停
輸出 cands.pkl：list of dict(d, code, tag, phi, v20, px, r3, yoy, mom, hi12, eg, mgk, fei105, fei807, ret20, ret60, ret60x)
"""
import pickle, json, glob, sys, time, collections, kc
from datetime import date, timedelta

OUT = sys.argv[1] if len(sys.argv) > 1 else "cands.pkl"
ONLY = sys.argv[2].split(",") if len(sys.argv) > 2 else None
px, cal, mk = pickle.load(open("px.pkl", "rb")); idx = {d: i for i, d in enumerate(cal)}
# ---- 0050 季線
c50 = []; last = None
for d in cal:
    v = px["0050"].get(d); last = v[3] if v else last; c50.append(last)
b50 = [False] * len(cal)
for i in range(59, len(cal)):
    w = c50[i - 59:i + 1]
    if None not in w: b50[i] = c50[i] > sum(w) / 60
# ---- 營收：{code: {ym: val}}；ym 從隔月 11 日起可用
rev = collections.defaultdict(dict)
for ym, slot in json.load(open("dl/rev10.json"))["m"].items():
    for c, v in slot.items():
        if isinstance(v, (int, float)): rev[c][ym] = float(v)
def ym_prev(ym, k):
    y, m = int(ym[:4]), int(ym[4:]); m -= k
    while m <= 0: m += 12; y -= 1
    return "%04d%02d" % (y, m)
def ym_avail(ym):
    y, m = int(ym[:4]), int(ym[4:]); m += 1
    if m > 12: m -= 12; y += 1
    return date(y, m, 11)
# ---- 季報：{code: {q: cum_eps}}
eps = collections.defaultdict(dict)
for f in glob.glob("mopsfin/mopsfin_*.json"):
    nm = f.split("/")[-1][:-5].split("_"); roc, qn = int(nm[2]), nm[3]
    q = "%dQ%s" % (roc + 1911, qn)
    for c, r in json.load(open(f))["rows"].items():
        e = r.get("eps")
        if isinstance(e, (int, float)): eps[c][q] = float(e)
def due(q):
    y, n = int(q[:4]), q[5]
    return {"1": date(y, 5, 15), "2": date(y, 8, 14), "3": date(y, 11, 14), "4": date(y + 1, 3, 31)}[n]
def qprev(q, k=1):
    y, n = int(q[:4]), int(q[5])
    for _ in range(k):
        y, n = (y - 1, 4) if n == 1 else (y, n - 1)
    return "%dQ%d" % (y, n)
def ttm(E, q):
    if q[5] == "4": return E.get(q)
    a, b, c = E.get(q), E.get("%dQ4" % (int(q[:4]) - 1)), E.get("%dQ%s" % (int(q[:4]) - 1, q[5]))
    return None if None in (a, b, c) else a + b - c
def single(E, q):
    if q[5] == "1": return E.get(q)
    a, b = E.get(q), E.get(qprev(q))
    return None if None in (a, b) else a - b

def fund_tables(code):
    """每個營收月 / 每季算好旗標，之後按日期查最新可用的。"""
    R = rev.get(code) or {}; E = eps.get(code) or {}
    rows_m = {}
    for ym in sorted(R):
        v = R[ym]
        m12 = [R.get(ym_prev(ym, k)) for k in range(1, 12)]
        have = [x for x in m12 if x is not None]
        hi12 = (len(have) >= 9 and v >= max(have))
        means = []
        for lag in range(0, 12):
            trio = [R.get(ym_prev(ym, lag + j)) for j in range(3)]
            means.append(sum(trio) / 3 if None not in trio else None)
        prev = [x for x in means[1:] if x is not None]
        hi3 = (means[0] is not None and len(prev) >= 9 and means[0] >= max(prev))
        l3 = [R.get(ym_prev(ym, j)) for j in range(3)]; y3 = [R.get(ym_prev(ym, 12 + j)) for j in range(3)]
        r3 = ((sum(l3) / sum(y3) - 1) * 100) if (None not in l3 and None not in y3 and sum(y3) > 0) else None
        ly = R.get(ym_prev(ym, 12)); yoy = ((v / ly - 1) * 100) if ly else None
        pm = R.get(ym_prev(ym, 1)); mom = ((v / pm - 1) * 100) if pm else None
        m24 = [R.get(ym_prev(ym, k)) for k in range(1, 24)]; h24 = [x for x in m24 if x is not None]
        jump = (yoy is not None and yoy >= 30 and len(h24) >= 18 and v >= max(h24))
        rows_m[ym] = dict(hi12=hi12, hi3=hi3, r3=r3, yoy=yoy, mom=mom, jump=jump)
    # MGK「第一次跳升」：近 12 個月內沒有別的跳升月
    yms = sorted(rows_m)
    for i, ym in enumerate(yms):
        rows_m[ym]["first"] = rows_m[ym]["jump"] and not any(rows_m[x]["jump"] for x in yms[max(0, i - 12):i])
    rows_q = {}
    prev_tg = False
    for q in sorted(E):
        t0, t1 = ttm(E, q), ttm(E, qprev(q, 4))
        ly = E.get("%dQ%s" % (int(q[:4]) - 1, q[5]))
        eg = (ly is not None and E[q] > ly and E[q] > 0)
        if t0 is not None and t1 is not None:
            tg = (t0 > t1 and t0 > 0)
        elif ly is not None:
            tg = eg                      # 2015Q3 以前沒有季報檔，TTM 算不出來的用「累計 EPS 年增」備援
        else:
            tg = None                    # 缺季報檔（2019Q1 上市、2023Q1 上市、2023Q3 上櫃）：沿用上一季的判定
        s0, s1, s2 = single(E, q), single(E, qprev(q)), single(E, qprev(q, 2))
        eps2up = (None not in (s0, s1, s2) and s0 > s1 > s2)
        if tg is None:
            tg = prev_tg
        prev_tg = tg
        rows_q[q] = dict(tg=tg, eg=eg, eps2up=eps2up)
    m_av = sorted((ym_avail(ym), ym) for ym in rows_m)
    q_av = sorted((due(q), q) for q in rows_q)
    return rows_m, rows_q, m_av, q_av

def latest(av, d, strict):
    """av: sorted [(date, key)]；回 d 當天可用的最新 key（strict: 要 avail < d）"""
    best = None
    for a, k in av:
        if (a < d) if strict else (a <= d): best = k
        else: break
    return best

def bars_of(code):
    s = px.get(code, {}); out = []; vols = []
    for d in sorted(s):
        v = s[d]
        if not (isinstance(v, list) and len(v) >= 4): continue
        o, h, l, c = v[0], v[1], v[2], v[3]
        if not (o and h and l and c): continue
        if not (l <= min(o, c) and h >= max(o, c)): continue
        out.append((date.fromisoformat(d), float(o), float(h), float(l), float(c))); vols.append(float(v[4] or 0))
    return out, vols

def main():
    codes = [c for c in px if len(c) == 4 and c.isdigit() and not c.startswith("00")]
    if ONLY: codes = ONLY
    t0 = time.time(); cands = []; n_scan = 0
    for ci, code in enumerate(sorted(codes)):
        bars, vols = bars_of(code)
        if len(bars) < 400: continue
        rows_m, rows_q, m_av, q_av = fund_tables(code)
        if not rows_m or not rows_q: continue
        c = [b[4] for b in bars]
        c50i = None
        for k in range(399, len(bars)):
            d = bars[k][0]; ds = d.isoformat()
            if ds not in idx or not b50[idx[ds]]: continue
            if c[k] < 10: continue
            hi = max(c[k - 249:k + 1]); phi = c[k] / hi
            if phi < 0.95: continue
            v20 = sum(vols[k - 19:k + 1]) / 20.0
            if v20 < 500: continue
            if c[k] >= c[k - 1] * 1.094 and c[k] >= bars[k][2] * 0.999: continue      # 鎖漲停
            ym = latest(m_av, d, strict=False); q = latest(q_av, d, strict=True)
            if not ym or not q: continue
            fm, fq = rows_m[ym], rows_q[q]
            if not (fm["hi3"] and fq["tg"]): continue
            n_scan += 1
            sub = bars[max(0, k - 799):k + 1]
            sc = kc.KScan(kc.KCtx(sub), max_segments=40).run()
            tag = (sc.mc[0] or sc.me[0] or "").strip("$")
            if not tag or tag not in "123567ABCD": continue
            # 排序用特徵
            ret20 = (c[k] / c[k - 20] - 1) * 100; ret60 = (c[k] / c[k - 60] - 1) * 100
            i50 = idx[ds]; r60x = None
            if i50 >= 60 and c50[i50] and c50[i50 - 60]:
                r60x = ret60 - (c50[i50] / c50[i50 - 60] - 1) * 100
            mgk = bool(fm["first"] and r60x is not None and r60x > 20)
            fei105 = bool(fm["yoy"] is not None and fm["yoy"] > 20 and fm["mom"] is not None and fm["mom"] > 20 and fq["eps2up"] and c[k] < 100)
            fei807 = bool(c[k] < 20 and fm["yoy"] is not None and fm["yoy"] > 20 and fq["eps2up"])
            cands.append(dict(d=ds, code=code, tag=tag, phi=phi, v20=v20, px=c[k], r3=fm["r3"], yoy=fm["yoy"], mom=fm["mom"],
                              hi12=fm["hi12"], eg=fq["eg"], mgk=mgk, fei105=fei105, fei807=fei807, jump=fm["jump"], first=fm["first"],
                              ret20=ret20, ret60=ret60, ret60x=r60x, eps2up=fq["eps2up"]))
        if ci % 100 == 0:
            print("  %4d/%d %s  候選 %d  掃描 %d  %.0fs" % (ci, len(codes), code, len(cands), n_scan, time.time() - t0), flush=True)
            pickle.dump(cands, open(OUT + ".part", "wb"))
    pickle.dump(cands, open(OUT, "wb"))
    print("完成：候選 %d 筆、KScan %d 次、%.0f 秒" % (len(cands), n_scan, time.time() - t0))

if __name__ == "__main__":
    main()
