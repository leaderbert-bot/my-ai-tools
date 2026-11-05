"""★ 兩種排序的回撤分佈：舊（均量大先）vs 新（創新高優先、同級均量≥2000 先，同分隨機 30 次）vs 純隨機 30 次；
各跑「不加」與「本月淨值 −5% 停開新倉」兩版。6 槽、抱 20 天、每天最多 3 檔、成本 0.47%、閒錢不生息（star_rank 引擎）。"""
import sys, statistics, collections, bisect, random, pickle
PHI = sys.argv[1] if len(sys.argv) > 1 else "0.95"
sys.argv = ["star_rank.py", "cands.pkl", PHI]
exec(open("star_rank.py").read().split("def main():")[0])

def run2(keyfn=None, seed=None, cap=3, slots=SLOTS, start=None, end=None, mstop=None):
    rng = random.Random(seed) if seed is not None else None
    cash = 1.0; pos = []; eq_curve = []; trades = []
    d0 = start or days[0]; d1 = end or cal[-1]
    i0 = bisect.bisect_left(cal, d0); i1 = min(bisect.bisect_right(cal, d1) - 1, len(cal) - 1)
    m_start = None; cur_m = None
    for i in range(i0, i1 + 1):
        d = cal[i]
        keep = []
        for p in pos:
            if p["out"] == d or i == i1:
                c = close_near(p["code"], d) or p["last"]
                cash += p["sh"] * c * (1 - COST / 2)
                trades.append(dict(ret=(c / p["in"] - 1) * 100 - COST * 100, d=p["d"], code=p["code"]))
            else:
                keep.append(p)
        pos = keep
        eq = cash + sum(p["sh"] * (close_near(p["code"], d) or p["last"]) for p in pos)
        if d[:7] != cur_m:
            cur_m = d[:7]; m_start = eq_curve[-1][1] if eq_curve else eq
        eq_curve.append((d, eq))
        if mstop is not None and eq / m_start - 1 <= mstop:
            continue
        L = list(byday.get(d, []))
        if not L: continue
        if rng is not None and keyfn is None: rng.shuffle(L)
        elif rng is not None:
            rng.shuffle(L); L.sort(key=keyfn)
        else: L.sort(key=keyfn)
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

def dd_info(eq):
    peak = -1; pk_d = None; mdd = 0; trough = None; pk_at = None
    for d, e in eq:
        if e > peak: peak, pk_d = e, d
        dd = e / peak - 1
        if dd < mdd: mdd, trough, pk_at = dd, d, pk_d
    return mdd * 100, pk_at, trough

OLD = lambda c: -c["v20"]
NEW = lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1)
out = []
for lab, kf, seeds in (("舊：均量大先", OLD, [None]), ("新：創新高優先、同級均量大先（同分隨機）", NEW, list(range(1000, 1030))), ("純隨機", None, list(range(30)))):
    for ms_lab, ms in (("不加", None), ("本月 −5% 停開新倉", -0.05)):
        R = []
        for s in seeds:
            eq, tr = run2(keyfn=kf, seed=s, mstop=ms) if not (kf is None and s is None) else run2(mstop=ms)
            st = stats(eq, tr); m, pk, tg = dd_info(eq)
            R.append((st["cagr"], m, pk, tg, st["n"]))
        cg = sorted(r[0] for r in R); md = sorted(r[1] for r in R)
        troughs = collections.Counter(r[3][:7] for r in R)
        print("phi%s %-34s %-14s 年化中位 %5.1f%%（%5.1f～%5.1f） 回撤中位 %6.1f%%（最差 %6.1f、最好 %6.1f） 筆數 %d  谷底月份 %s" % (
            PHI, lab, ms_lab, cg[len(cg)//2], cg[0], cg[-1], md[len(md)//2], md[0], md[-1], R[0][4], dict(troughs.most_common(3))))
