"""MGK「股價先漲、營收第一次跳升」當獨立策略：2016～2026，k10y＋rev10。
訊號：某月營收 yoy ≥ 30% 且 ≥ 前 23 個月最高（跳升）、近 12 個月內第一次；公布後（隔月 11 日起）第一個交易日，
      該股近 60 日漲幅比 0050 多 20 點以上；均量 ≥ 500 張、價 ≥ 10、當天沒鎖漲停。收盤買、抱 60 個交易日收盤賣。
帳戶：10 槽 × 10%，閒錢放 0050 含息；隨機 30 次。"""
import json, pickle, bisect, random, statistics, collections
px, cal, mk = pickle.load(open("px.pkl", "rb")); idx = {d: i for i, d in enumerate(cal)}
tr50, divs = pickle.load(open("tr50.pkl", "rb"))
rev = collections.defaultdict(dict)
for ym, slot in json.load(open("dl/rev10.json"))["m"].items():
    for c, v in slot.items():
        if isinstance(v, (int, float)): rev[c][ym] = float(v)
def ym_prev(ym, k):
    y, m = int(ym[:4]), int(ym[4:]); m -= k
    while m <= 0: m += 12; y -= 1
    return "%04d%02d" % (y, m)
def avail(ym):
    y, m = int(ym[:4]), int(ym[4:]); m += 1
    if m > 12: m -= 12; y += 1
    d = "%04d-%02d-11" % (y, m); i = bisect.bisect_left(cal, d)
    return cal[i] if i < len(cal) else None
COST = 0.0047; COST50 = 0.0015; HOLD = 60
c50 = []; last = None
for d in cal:
    v = px["0050"].get(d); last = v[3] if v else last; c50.append(last)
sig = []
for c, R in rev.items():
    if c not in px or c.startswith("00"): continue
    yms = sorted(R); jumps = set()
    for ym in yms:
        v = R[ym]; ly = R.get(ym_prev(ym, 12))
        m24 = [R.get(ym_prev(ym, k)) for k in range(1, 24)]; h = [x for x in m24 if x is not None]
        if not (ly and ly > 0 and v / ly - 1 >= 0.30 and len(h) >= 18 and v >= max(h)): continue
        if any(ym_prev(ym, k) in jumps for k in range(1, 13)):
            jumps.add(ym); continue
        jumps.add(ym)
        d = avail(ym)
        if not d or d < "2016-06-01": continue
        s = px[c]; i = idx[d]
        if i < 60: continue
        bar = s.get(d); b60 = s.get(cal[i - 60])
        if not bar or not b60 or not c50[i] or not c50[i - 60]: continue
        r60x = (bar[3] / b60[3] - 1) * 100 - (c50[i] / c50[i - 60] - 1) * 100
        vols = [s[x][4] for x in cal[i - 20:i] if x in s]
        if len(vols) < 15 or sum(vols) / 20 < 500 or bar[3] < 10: continue
        pb = s.get(cal[i - 1])
        if pb and bar[3] >= pb[3] * 1.094 and bar[3] >= bar[1] * 0.999: continue
        sig.append(dict(code=c, d=d, px=bar[3], r60x=r60x, yoy=(v / ly - 1) * 100))
print("跳升訊號（第一次）", len(sig), "；其中先漲 >20 點的", sum(1 for s in sig if s["r60x"] > 20))
def close_near(code, d):
    i = idx[d]
    for j in range(i, max(-1, i - 10), -1):
        v = px.get(code, {}).get(cal[j])
        if v: return v[3]
    return None
def run(S, seed=None, slots=10, frac=0.10, start="2016-06-01", end=cal[-1]):
    byday = collections.defaultdict(list)
    for s in S: byday[s["d"]].append(s)
    rng = random.Random(seed) if seed is not None else None
    i0 = bisect.bisect_left(cal, start); i1 = idx[end]
    units = 1.0 / tr50[i0]; pos = []; eq = []; done = []
    for i in range(i0, i1 + 1):
        d = cal[i]; keep = []
        for p in pos:
            if p["out"] == d or i == i1:
                c = close_near(p["code"], d) or p["in"]
                units += p["sh"] * c * (1 - COST / 2) * (1 - COST50) / tr50[i]; done.append((c / p["in"] - 1) * 100 - COST * 100)
            else: keep.append(p)
        pos = keep
        mv = sum(p["sh"] * (close_near(p["code"], d) or p["in"]) for p in pos); e = units * tr50[i] + mv
        L = list(byday.get(d, []))
        if rng: rng.shuffle(L)
        else: L.sort(key=lambda s: -s["r60x"])
        for s in L:
            if any(p["code"] == s["code"] for p in pos) or len(pos) >= slots or i + HOLD > i1: continue
            amt = min(e * frac, units * tr50[i] * (1 - COST50))
            if amt <= 0: continue
            units -= amt / (1 - COST50) / tr50[i]
            pos.append(dict(code=s["code"], sh=amt * (1 - COST / 2) / s["px"], out=cal[i + HOLD], **{"in": s["px"]}))
        mv = sum(p["sh"] * (close_near(p["code"], d) or p["in"]) for p in pos)
        eq.append((d, units * tr50[i] + mv))
    yrs = (i1 - i0) / 245.0; cagr = (eq[-1][1] / eq[0][1]) ** (1 / yrs) - 1
    peak = 0; mdd = 0
    for _, e in eq: peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    ye = {}
    for d, e in eq: ye[d[:4]] = e
    yr = {}; base = eq[0][1]
    for y in sorted(ye): yr[y] = (ye[y] / base - 1) * 100; base = ye[y]
    return dict(cagr=cagr * 100, mdd=mdd * 100, n=len(done), avg=statistics.mean(done) if done else 0, win=100 * sum(1 for x in done if x > 0) / max(1, len(done)), yr=yr)
b = run([]); print("0050 含息：年化 %.1f%% 回撤 %.1f%%" % (b["cagr"], b["mdd"]))
for nm, S in (("MGK 先漲 >20 點＋第一次跳升", [s for s in sig if s["r60x"] > 20]), ("第一次跳升（不管先漲）", sig), ("先漲 >20 點，再加 0050 季線上", [s for s in sig if s["r60x"] > 20 and idx[s["d"]] >= 60 and c50[idx[s["d"]]] > sum(c50[idx[s["d"]] - 59: idx[s["d"]] + 1]) / 60])):
    r = run(S); rs = sorted(run(S, seed=k)["cagr"] for k in range(30))
    h1 = run(S, end="2021-06-30"); h2 = run(S, start="2021-07-01")
    print("%s：年化 %.1f%% 回撤 %.1f%% 筆數 %d 每筆 %+.2f%% 勝率 %.0f%%；隨機 30 次中位 %.1f%%（%.1f～%.1f）；前半 %.1f%% 後半 %.1f%%" % (nm, r["cagr"], r["mdd"], r["n"], r["avg"], r["win"], rs[15], rs[0], rs[-1], h1["cagr"], h2["cagr"]))
    print("   逐年 " + " ".join("%s %+.0f" % (y[2:], v) for y, v in r["yr"].items()) + "   贏 0050 的年數 %d/%d" % (sum(1 for y, v in r["yr"].items() if v > b["yr"].get(y, 0)), len(r["yr"])))
