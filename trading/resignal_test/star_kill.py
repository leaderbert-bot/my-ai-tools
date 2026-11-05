"""★ 新排序（創新高優先、同級均量≥2000 先，同分隨機）＋「本月淨值 −5% 停開新倉到月底」：100 種買進順序的
年化、回撤、滾動 30 筆勝率／平均、最長連虧、滾動 12 個月落後 0050 含息，拿來重定停用線。對照：舊排序（均量大先）同規則。"""
import sys, statistics, collections, bisect, random, pickle
PHI = sys.argv[1] if len(sys.argv) > 1 else "0.95"
_ARGV = list(sys.argv)
NSEED = int(sys.argv[2]) if len(sys.argv) > 2 else 100
sys.argv = ["star_rank.py", "cands.pkl", PHI]
exec(open("star_rank.py").read().split("def main():")[0])
tr50, _divs = pickle.load(open("tr50.pkl", "rb"))

def run3(keyfn=None, seed=None, cap=3, slots=SLOTS, mstop=-0.05):
    rng = random.Random(seed) if seed is not None else None
    cash = 1.0; pos = []; eq_curve = []; trades = []
    i0 = bisect.bisect_left(cal, days[0]); i1 = len(cal) - 1
    m_start = None; cur_m = None; stopped = False
    for i in range(i0, i1 + 1):
        d = cal[i]; keep = []
        for p in pos:
            if p["out"] == d or i == i1:
                c = close_near(p["code"], d) or p["last"]
                cash += p["sh"] * c * (1 - COST / 2)
                trades.append(dict(ret=(c / p["in"] - 1) * 100 - COST * 100, d=p["d"], x=d, code=p["code"]))
            else:
                keep.append(p)
        pos = keep
        eq = cash + sum(p["sh"] * (close_near(p["code"], d) or p["last"]) for p in pos)
        if d[:7] != cur_m:
            cur_m = d[:7]; m_start = eq_curve[-1][1] if eq_curve else eq; stopped = False
        eq_curve.append((d, eq))
        if mstop is not None and (stopped or eq / m_start - 1 <= mstop):
            stopped = True; continue
        L = list(byday.get(d, []))
        if not L: continue
        if rng is not None:
            rng.shuffle(L)
        if keyfn is not None:
            L.sort(key=keyfn)
        held = set(p["code"] for p in pos); buys = 0
        for c in L:
            if c["code"] in held: continue
            if len(pos) >= slots or (cap and buys >= cap): break
            amt = min(cash, eq / slots)
            if amt <= 1e-9: break
            if i + HOLD > i1: continue
            pxin = c["px"]; sh = amt / (pxin * (1 + COST / 2)); cash -= amt
            pos.append(dict(code=c["code"], sh=sh, out=cal[i + HOLD], d=d, last=pxin, **{"in": pxin})); held.add(c["code"]); buys += 1
    return eq_curve, trades

def metrics(eq, tr):
    st = stats(eq, tr)
    peak = -1; mdd = 0; trough = None
    for d, e in eq:
        peak = max(peak, e); dd = e / peak - 1
        if dd < mdd: mdd, trough = dd, d
    T = sorted(tr, key=lambda t: (t["x"], t["d"]))
    R = [t["ret"] for t in T]
    w30 = [sum(1 for r in R[k - 30:k] if r > 0) / 30 * 100 for k in range(30, len(R) + 1)]
    a30 = [statistics.mean(R[k - 30:k]) for k in range(30, len(R) + 1)]
    streak = mx = 0
    for r in R:
        streak = streak + 1 if r <= 0 else 0; mx = max(mx, streak)
    ix = {d: k for k, d in enumerate(cal)}
    lag = []
    E = dict(eq); dl = [d for d, _ in eq]
    for k in range(245, len(dl)):
        d1, d0 = dl[k], dl[k - 245]
        a = E[d1] / E[d0] - 1; b = tr50[ix[d1]] / tr50[ix[d0]] - 1
        lag.append((a - b) * 100)
    return dict(cagr=st["cagr"], mdd=mdd * 100, trough=trough, n=st["n"], w30=w30, a30=a30, streak=mx, lag=lag)

def pct(xs, p):
    xs = sorted(xs); return xs[max(0, min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1)))))]

NEW = lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1)
OLD = lambda c: -c["v20"]
MS = None if (len(_ARGV) > 3 and _ARGV[3] == "none") else -0.05
for lab, kf, seeds in (("新排序" + ("（不加月停）" if MS is None else "＋本月 −5% 停開新倉"), NEW, list(range(1000, 1000 + NSEED))), ("純隨機" + ("（不加月停）" if MS is None else "＋月停"), None, list(range(NSEED))), ("舊排序（均量大先）" + ("（不加月停）" if MS is None else "＋月停"), OLD, [None])):
    M = [metrics(*run3(keyfn=kf, seed=s, mstop=MS)) for s in seeds]
    cg = sorted(m["cagr"] for m in M); md = sorted(m["mdd"] for m in M)
    print("\n==== phi %s %s（%d 種買進順序）" % (PHI, lab, len(M)))
    print("年化：中位 %.1f%%、5%% 分位 %.1f、最低 %.1f、最高 %.1f；筆數中位 %d" % (pct(cg, 50), pct(cg, 5), cg[0], cg[-1], int(statistics.median(m["n"] for m in M))))
    print("最大回撤：中位 %.1f%%、80%% 的順序好於 %.1f、95%% 好於 %.1f、最差 %.1f、最好 %.1f；谷底月份 %s" % (
        pct(md, 50), pct(md, 20), pct(md, 5), md[0], md[-1], dict(collections.Counter(m["trough"][:7] for m in M).most_common(4))))
    for key, nm in (("w30", "滾動 30 筆勝率 %"), ("a30", "滾動 30 筆平均每筆 %"), ("lag", "滾動 12 個月 − 0050 含息（點）")):
        mins = sorted(min(m[key]) for m in M); pooled = [x for m in M for x in m[key]]
        print("%s：每條路徑的最低值 中位 %.1f、最差 %.1f；所有時間點合起來 5%% 分位 %.1f、1%% 分位 %.1f" % (nm, pct(mins, 50), mins[0], pct(pooled, 5), pct(pooled, 1)))
    sk = sorted(m["streak"] for m in M)
    print("最長連虧：中位 %d 筆、95%% 分位 %d、最多 %d" % (pct(sk, 50), pct(sk, 95), sk[-1]))
