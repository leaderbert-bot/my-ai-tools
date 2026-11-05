"""建立「產業循環位置」資料（10 年、每月）：stage_data.pkl
每個月 ym 的資料在「下個月 11 日後第一個交易日」avail(ym) 才可用（月營收公布日），季報用法定期限（5/15、8/14、11/14、3/31）。
產業 = 證交所產業別（dl/industry_map.json，中性）；族群 = 使用者 groups.csv（主題族群，有事後之見，另存）。
產業統計（成員 ≥ 6 檔）：rev3 = 近 3 月營收年增 % 的中位數、breadth = 成員年增 > 0 的比例、gm_d = 近 4 季毛利率 − 去年同期近 4 季毛利率（點）的中位數、
mom60 = 成員近 60 日相對 0050 報酬（點）的中位數。位置（預設門檻）：price 價漲期 = rev3 ≥ 10 且 gm_d ≥ 1.0；vol 量增 = rev3 ≥ 10 且 gm_d < 1.0；down 衰退 = rev3 < 0；flat 其他。
new_price = 這個月是 price、3 個月前不是。個股自己的位置 stock_stage 照 11/05 循環課測試的定義（累計季毛利率 vs 去年同季 ≥ 1.5 點）。"""
import json, pickle, bisect, collections, statistics, glob, os, csv
from datetime import date
px, cal, mk = pickle.load(open("px.pkl", "rb")); idx = {d: i for i, d in enumerate(cal)}
rev = collections.defaultdict(dict)
for ym, slot in json.load(open("dl/rev10.json"))["m"].items():
    for c, v in slot.items():
        if isinstance(v, (int, float)): rev[c][ym] = float(v)
IND = {c: v for c, v in json.load(open("dl/industry_map.json")).items() if len(c) == 4}
GRP = collections.defaultdict(list)
for r in list(csv.reader(open("dl/groups.csv", encoding="utf-8")))[1:]:
    if len(r) >= 2 and r[0] not in ("權值重點", "權值買權前10") and r[1] not in GRP or (len(r) >= 2 and r[0] not in GRP.get(r[1], [])):
        if len(r) >= 2 and r[0] not in ("權值重點", "權值買權前10"): GRP[r[1]].append(r[0])
F = collections.defaultdict(dict)
for f in glob.glob("mopsfin/mopsfin_*.json"):
    nm = os.path.basename(f)[:-5].split("_"); q = "%dQ%s" % (int(nm[2]) + 1911, nm[3])
    for c, r in json.load(open(f))["rows"].items(): F[c][q] = r
def ym_prev(ym, k):
    y, m = int(ym[:4]), int(ym[4:]); m -= k
    while m <= 0: m += 12; y -= 1
    return "%04d%02d" % (y, m)
def avail(ym):
    y, m = int(ym[:4]), int(ym[4:]); m += 1
    if m > 12: m -= 12; y += 1
    d = "%04d-%02d-11" % (y, m); i = bisect.bisect_left(cal, d)
    return cal[i] if i < len(cal) else None
def qprev(q, k=1):
    y, n = int(q[:4]), int(q[5]); n -= k
    while n <= 0: n += 4; y -= 1
    return "%dQ%d" % (y, n)
def num(x): return float(x) if isinstance(x, (int, float)) else None
def cum(c, q, k):
    r = F[c].get(q); return num(r.get(k)) if r else None
def ttm(c, q, k):
    a = cum(c, q, k); n = int(q[5])
    if a is None: return None
    if n == 4: return a
    y4 = cum(c, "%dQ4" % (int(q[:4]) - 1), k); ly = cum(c, qprev(q, 4), k)
    return None if (y4 is None or ly is None) else a + y4 - ly
def due(q):
    y, n = int(q[:4]), int(q[5]); return date(y + 1, 3, 31).isoformat() if n == 4 else [None, date(y, 5, 15), date(y, 8, 14), date(y, 11, 14)][n].isoformat()
ALLQ = sorted(set(q for c in F for q in F[c])); DUE = {q: due(q) for q in ALLQ}
def latest_q(c, d):
    best = None
    for q in ALLQ:
        if DUE[q] < d and q in F[c]: best = q
    return best
def gm_ttm(c, q):
    g, v = ttm(c, q, "gross"), ttm(c, q, "rev")
    return g / v * 100 if (g is not None and v) else None
def gm_cum(c, q):
    r = F[c].get(q)
    if not r: return None
    g, v = num(r.get("gross")), num(r.get("rev"))
    return g / v * 100 if (g is not None and v) else None
c50 = []; last = None
for d in cal:
    v = px.get("0050", {}).get(d); last = v[3] if v else last; c50.append(last)
yms = sorted(set(ym for c in rev for ym in rev[c]))
yms = [ym for ym in yms if ym >= "201601" and avail(ym)]
P = dict(price_rev=10.0, price_gm=1.0, min_n_ind=6, min_n_grp=3)
stock = {}; ind = {}; grp = {}
codes = [c for c in rev if c in px and len(c) == 4 and c.isdigit() and not c.startswith("00")]
print("月份", yms[0], "～", yms[-1], len(yms), "個月；有營收且有日 K 的股票", len(codes), "；有產業別", sum(1 for c in codes if c in IND), "；在族群表", sum(1 for c in codes if c in GRP))
for ym in yms:
    A = avail(ym); i = idx[A]
    rows = {}
    for c in codes:
        R = rev[c]; l3 = [R.get(ym_prev(ym, j)) for j in range(3)]; y3 = [R.get(ym_prev(ym, 12 + j)) for j in range(3)]
        if None in l3 or None in y3 or sum(y3) <= 0: continue
        r3 = (sum(l3) / sum(y3) - 1) * 100
        q = latest_q(c, A); gmd = gmc = None
        if q:
            a, b = gm_ttm(c, q), gm_ttm(c, qprev(q, 4))
            if a is not None and b is not None: gmd = a - b
            a2, b2 = gm_cum(c, q), gm_cum(c, qprev(q, 4))
            if a2 is not None and b2 is not None: gmc = a2 - b2
        mom = None
        if i >= 60:
            b1, b0 = px[c].get(A), px[c].get(cal[i - 60])
            if b1 and b0 and c50[i] and c50[i - 60]: mom = (b1[3] / b0[3] - 1) * 100 - (c50[i] / c50[i - 60] - 1) * 100
        st = "up" if (r3 >= 10 and gmc is not None and gmc >= 1.5) else ("vol" if r3 >= 10 else ("down" if r3 < 0 else "flat"))
        if gmc is None and r3 >= 10: st = "vol?"
        rows[c] = dict(r3=r3, gm_d=gmd, gm_c=gmc, mom60=mom, stage=st, q=q)
        stock[(c, ym)] = rows[c]
    def agg(members, mn):
        xs = [rows[c] for c in members if c in rows]
        if len(xs) < mn: return None
        r3s = [x["r3"] for x in xs]; g = [x["gm_d"] for x in xs if x["gm_d"] is not None]; m = [x["mom60"] for x in xs if x["mom60"] is not None]
        o = dict(n=len(xs), rev3=statistics.median(r3s), breadth=sum(1 for v in r3s if v > 0) / len(r3s),
                 gm_d=statistics.median(g) if len(g) >= max(3, mn // 2) else None, mom60=statistics.median(m) if m else None)
        if o["rev3"] >= P["price_rev"]:
            o["stage"] = "price" if (o["gm_d"] is not None and o["gm_d"] >= P["price_gm"]) else ("vol" if o["gm_d"] is not None else "vol?")
        elif o["rev3"] < 0: o["stage"] = "down"
        else: o["stage"] = "flat"
        return o
    by_ind = collections.defaultdict(list)
    for c in rows:
        if c in IND: by_ind[IND[c]].append(c)
    for k, mem in by_ind.items():
        o = agg(mem, P["min_n_ind"])
        if o: ind[(k, ym)] = o
    by_grp = collections.defaultdict(list)
    for c in rows:
        for g in GRP.get(c, []): by_grp[g].append(c)
    for k, mem in by_grp.items():
        o = agg(mem, P["min_n_grp"])
        if o: grp[(k, ym)] = o
for T in (ind, grp):
    for (k, ym), o in T.items():
        p = T.get((k, ym_prev(ym, 3)))
        o["new_price"] = bool(o["stage"] == "price" and p is not None and p["stage"] != "price")
        p1 = T.get((k, ym_prev(ym, 1)))
        o["prev_stage"] = p1["stage"] if p1 else None
AV = {ym: avail(ym) for ym in yms}
pickle.dump(dict(yms=yms, avail=AV, IND=IND, GRP=dict(GRP), ind=ind, grp=grp, stock=stock, params=P), open("stage_data.pkl", "wb"))
# 檢查
inds = sorted(set(k for k, _ in ind)); print("產業數", len(inds), "；族群數", len(set(k for k, _ in grp)))
cnt = collections.Counter(o["stage"] for o in ind.values()); print("產業×月 位置分佈", dict(cnt), "；new_price", sum(1 for o in ind.values() if o["new_price"]))
cnt2 = collections.Counter(o["stage"] for o in stock.values()); print("個股×月 位置分佈", dict(cnt2))
sym = {"price": "P", "vol": "v", "vol?": "?", "down": "d", "flat": "."}
for k in ["航運業", "半導體業", "電子零組件業", "光電業", "鋼鐵工業", "塑膠工業", "生技醫療業", "建材營造", "觀光餐旅", "電腦及週邊設備業", "通信網路業", "電機機械"]:
    line = []
    for y in range(2016, 2027):
        s = "".join(sym.get(ind.get((k, "%d%02d" % (y, m)), {}).get("stage", " "), " ") for m in range(1, 13))
        line.append("%d %s" % (y % 100, s))
    print("%-10s" % k, " | ".join(line))
C = pickle.load(open("cands.pkl", "rb"))
def ym_at(d):
    i = bisect.bisect_right([AV[y] for y in yms], d) - 1
    return yms[i] if i >= 0 else None
hit = sum(1 for c in C if c["code"] in IND and (IND[c["code"]], ym_at(c["d"])) in ind); print("★ 候選 %d 筆，查得到產業位置 %d（%.0f%%）" % (len(C), hit, 100 * hit / len(C)))
