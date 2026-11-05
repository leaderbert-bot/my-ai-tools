"""★ 候選排序測試：同一批每日候選（cands.pkl），6 槽、抱 20 天收盤賣，只改「同一天候選比空位多時先買誰」。
基準＝雷達原本的「20 日均量大的先」；對照＝隨機 100 次（使用者自己的標準：看中位數）。"""
import pickle, random, statistics, collections, sys, json, bisect
COST = 0.0047; HOLD = 20; SLOTS = 6
px, cal, mk = pickle.load(open("px.pkl", "rb")); idx = {d: i for i, d in enumerate(cal)}
C = pickle.load(open(sys.argv[1] if len(sys.argv) > 1 else "cands.pkl", "rb"))
PHI_MIN = float(sys.argv[2]) if len(sys.argv) > 2 else 0.95
C = [c for c in C if c["phi"] >= PHI_MIN]
byday = collections.defaultdict(list)
for c in C: byday[c["d"]].append(c)
days = sorted(byday)

def close(code, d):
    v = px.get(code, {}).get(d)
    return float(v[3]) if v and v[3] else None

def close_near(code, d):
    """d 沒成交就往前找最近一根（停牌）"""
    i = idx[d]
    for j in range(i, max(-1, i - 10), -1):
        v = close(code, cal[j])
        if v: return v
    return None

ORDERS = {
    "均量大先（雷達原本）": lambda c: -c["v20"],
    "均量小先": lambda c: c["v20"],
    "離一年高近先（phi 大）": lambda c: -c["phi"],
    "phi 大先，同分均量大先": lambda c: (-round(c["phi"], 4), -c["v20"]),
    "phi 大先，同分低價先": lambda c: (-round(c["phi"], 4), c["px"]),
    "phi ≥ 0.99 優先，再均量大": lambda c: (0 if c["phi"] >= 0.99 else 1, -c["v20"]),
    "創新高（phi = 1）優先，再均量大": lambda c: (0 if c["phi"] >= 0.9999 else 1, -c["v20"]),
    "離一年高遠先（phi 小）": lambda c: c["phi"],
    "近 3 月營收年增大先": lambda c: -(c["r3"] if c["r3"] is not None else -999),
    "單月營收年增大先": lambda c: -(c["yoy"] if c["yoy"] is not None else -999),
    "20 日漲幅小先（拉回）": lambda c: c["ret20"],
    "20 日漲幅大先（動能）": lambda c: -c["ret20"],
    "60 日比 0050 強先": lambda c: -(c["ret60x"] if c["ret60x"] is not None else -999),
    "MGK 先漲後跳升先": lambda c: (0 if c["mgk"] else 1, -c["v20"]),
    "菲比斯 105／807 先": lambda c: (0 if (c["fei105"] or c["fei807"]) else 1, -c["v20"]),
    "四個基本面旗標都過先": lambda c: (0 if (c["hi12"] and c["eg"]) else 1, -c["v20"]),
    "EPS 連兩季上升先": lambda c: (0 if c["eps2up"] else 1, -c["v20"]),
    "低價先": lambda c: c["px"],
    "高價先": lambda c: -c["px"],
    "代號小先（同分時的預設順序）": lambda c: c["code"],
    "點位 B／D 先": lambda c: (0 if c["tag"] in "BD" else 1, -c["v20"]),
    "點位 1／5／A 先": lambda c: (0 if c["tag"] in "15A" else 1, -c["v20"]),
}

def run(keyfn=None, seed=None, cap=3, slots=SLOTS, start=None, end=None):
    rng = random.Random(seed) if seed is not None else None
    cash = 1.0; pos = []; eq_curve = []; trades = []
    d0 = start or days[0]; d1 = end or cal[-1]
    i0 = bisect.bisect_left(cal, d0); i1 = min(bisect.bisect_right(cal, d1) - 1, len(cal) - 1)
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
        eq_curve.append((d, eq))
        L = list(byday.get(d, []))
        if not L: continue
        if rng is not None and keyfn is None: rng.shuffle(L)
        elif rng is not None:
            rng.shuffle(L); L.sort(key=keyfn)          # 先打亂再排序：同分的順序是隨機的
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

def stats(eq, tr):
    d0, e0 = eq[0]; d1, e1 = eq[-1]
    yrs = (idx[d1] - idx[d0]) / 245.0
    cagr = (e1 / e0) ** (1 / yrs) - 1 if yrs > 0 else 0
    peak = -1; mdd = 0
    for d, e in eq:
        peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    last_e = {}
    for d, e in eq: last_e[d[:4]] = e
    yr = {}; base = e0
    for y in sorted(last_e):
        yr[y] = (last_e[y] / base - 1) * 100; base = last_e[y]
    return dict(cagr=cagr * 100, mdd=mdd * 100, n=len(tr), win=100 * sum(1 for t in tr if t["ret"] > 0) / max(1, len(tr)),
                avg=statistics.mean(t["ret"] for t in tr) if tr else 0, yr=yr)

def main():
    print("候選 %d 筆（phi ≥ %.2f）、%d 天有候選、%s ～ %s" % (len(C), PHI_MIN, len(days), days[0], days[-1]))
    nd = collections.Counter(len(v) for v in byday.values())
    print("一天候選數分佈：1 檔 %d 天、2 檔 %d、3 檔 %d、4～6 檔 %d、>6 檔 %d" % (nd[1], nd[2], nd[3], sum(nd[k] for k in (4, 5, 6)), sum(v for k, v in nd.items() if k > 6)))
    out = []
    for cap in (3, None):
        print("\n==== 每天最多 %s 檔 ====" % (cap if cap else "不限"))
        # 隨機 100 次
        rs = []
        for s in range(100):
            eq, tr = run(seed=s, cap=cap); rs.append(stats(eq, tr))
        cg = sorted(x["cagr"] for x in rs); md = sorted(x["mdd"] for x in rs)
        rand_med = cg[50]
        print("  隨機 100 次：年化 中位 %.1f%%（最低 %.1f、最高 %.1f）回撤中位 %.1f%%、最差 %.1f%%；筆數 %d" % (rand_med, cg[0], cg[-1], md[50], md[0], int(statistics.median(x["n"] for x in rs))))
        rows = []
        for nm, kf in ORDERS.items():
            eq, tr = run(keyfn=kf, cap=cap); s = stats(eq, tr)
            h1 = stats(*run(keyfn=kf, cap=cap, end="2021-12-31")); h2 = stats(*run(keyfn=kf, cap=cap, start="2022-01-03"))
            beat = 100 * (sum(1 for x in cg if s["cagr"] > x + 1e-9) + 0.5 * sum(1 for x in cg if abs(s["cagr"] - x) <= 1e-9)) / len(cg)
            rows.append((nm, s, h1, h2, beat))
            out.append(dict(cap=cap, order=nm, cagr=s["cagr"], mdd=s["mdd"], n=s["n"], win=s["win"], avg=s["avg"], beat_random=beat, h1=h1["cagr"], h2=h2["cagr"], yr=s["yr"]))
        rows.sort(key=lambda r: -r[1]["cagr"])
        print("  %-24s %7s %7s %5s %5s %7s %8s %8s %6s" % ("排序", "年化", "回撤", "筆數", "勝率", "每筆", "前半年化", "後半年化", "贏隨機"))
        for nm, s, h1, h2, beat in rows:
            print("  %-24s %6.1f%% %6.1f%% %5d %4.0f%% %+6.2f%% %7.1f%% %7.1f%% %5.0f%%" % (nm, s["cagr"], s["mdd"], s["n"], s["win"], s["avg"], h1["cagr"], h2["cagr"], beat))
        out.append(dict(cap=cap, order="隨機中位", cagr=rand_med, mdd=md[50], lo=cg[0], hi=cg[-1]))
        print("  同分隨機 30 次（規則只決定第一排序，同分打亂）：年化中位／最低／最高、贏純隨機中位的次數")
        TIE = {"創新高（phi = 1）優先": lambda c: 0 if c["phi"] >= 0.9999 else 1, "phi ≥ 0.99 優先": lambda c: 0 if c["phi"] >= 0.99 else 1,
               "phi 分 4 級（1／≥.99／≥.97／其他）": lambda c: 0 if c["phi"] >= 0.9999 else (1 if c["phi"] >= 0.99 else (2 if c["phi"] >= 0.97 else 3)),
               "低價先（分 3 級 <30／<100／其他）": lambda c: 0 if c["px"] < 30 else (1 if c["px"] < 100 else 2),
               "MGK 優先": lambda c: 0 if c["mgk"] else 1, "菲比斯 105／807 優先": lambda c: 0 if (c["fei105"] or c["fei807"]) else 1,
               "點位 B／D 優先": lambda c: 0 if c["tag"] in "BD" else 1, "點位 1／5／A 優先": lambda c: 0 if c["tag"] in "15A" else 1,
               "均量 ≥ 2000 張優先": lambda c: 0 if c["v20"] >= 2000 else 1,
               "創新高優先，同級低價先（候選規則）": lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["px"] < 30 else (1 if c["px"] < 100 else 2)),
               "創新高優先，同級均量大先": lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1)}
        for nm, kf in TIE.items():
            cs = sorted(stats(*run(keyfn=kf, seed=1000 + k, cap=cap))["cagr"] for k in range(30))
            print("    %-28s %5.1f%% / %5.1f / %5.1f   %2d/30" % (nm, cs[15], cs[0], cs[-1], sum(1 for x in cs if x > rand_med)))
            out.append(dict(cap=cap, order=nm + "（同分隨機）", cagr=cs[15], lo=cs[0], hi=cs[-1], beat_random_n=sum(1 for x in cs if x > rand_med)))
        # 逐年：基準、phi 類、隨機中位
        ys = sorted(set(y for x in rs for y in x["yr"]))
        rmed = dict((y, statistics.median([x["yr"].get(y, 0) for x in rs])) for y in ys)
        show = ["均量大先（雷達原本）", "離一年高近先（phi 大）", "phi 大先，同分均量大先", "phi ≥ 0.99 優先，再均量大", "低價先"]
        print("  逐年報酬（%）：" + " ".join("%6s" % y for y in ys))
        print("  %-26s" % "隨機中位" + " ".join("%+6.0f" % rmed[y] for y in ys))
        for nm, s_, h1, h2, beat in rows:
            if nm in show:
                print("  %-26s" % nm + " ".join("%+6.0f" % s_["yr"].get(y, 0) for y in ys) + "   贏隨機中位的年數 %d/%d" % (sum(1 for y in ys if s_["yr"].get(y, 0) > rmed[y]), len(ys)))
    json.dump(out, open("star_rank_out_%s.json" % str(PHI_MIN).replace(".", ""), "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
