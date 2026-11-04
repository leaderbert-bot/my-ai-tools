"""帳戶模擬：★ 6 槽基準 vs 再訊號加碼變體。讀 ev.pkl（resignal.py 產生）與 px.pkl。"""
import pickle, collections, math, statistics, sys
COST = 0.0047; HOLD = 20; SLOTS = 6; DAYMAX = 3
px, cal, mk = pickle.load(open("px.pkl", "rb")); idx = {d: i for i, d in enumerate(cal)}
TR, EV = pickle.load(open("ev.pkl", "rb"))

def close(code, d):
    v = px.get(code, {}).get(d)
    return float(v[3]) if v and v[3] else None

def run(mode, block_ok=True, need_above=False, min_off=0, size_frac=1.0):
    """mode: 'base' 只做原本 489 筆；'add' 再訊號時若有空槽就再開一槽。
    block_ok=False：加碼單不能佈擋任何一筆原本的進場（先算原本的佔槽，20 天內都要有空位才加）。
    need_above：只在現價高於第一筆成本時加。size_frac：加碼單是一槽的幾分之幾。"""
    # 事件索引
    entries = collections.defaultdict(list)   # date -> trades
    for n, t in enumerate(TR): entries[t["sig"]].append(n)
    adds = collections.defaultdict(list)       # date -> events
    for e in EV:
        if need_above and not e["above_entry"]: continue
        if e["off"] < min_off: continue
        adds[e["d"]].append(e)
    # 原本的佔槽（for block_ok=False）
    occ = [0] * len(cal)
    for t in TR:
        for i in range(idx[t["sig"]], idx[t["out"]]): occ[i] += 1
    cash = 1.0; pos = []   # pos: dict(code, sh, out, kind, cost_px)
    eq_curve = []; trades = []; blocked = 0; n_add = 0
    start = idx[TR[0]["sig"]]; end = max(idx[t["out"]] for t in TR)
    for i in range(start, end + 1):
        d = cal[i]
        # 出場（收盤）
        keep = []
        for p in pos:
            if p["out"] == d:
                c = close(p["code"], d)
                if c is None: c = p["last"]
                cash += p["sh"] * c * (1 - COST / 2)
                trades.append(dict(kind=p["kind"], ret=(c / p["in"] - 1) * 100 - COST * 100, d=p["d"], code=p["code"]))
            else:
                keep.append(p)
        pos = keep
        # 權益（出場後、進場前）
        eq = cash + sum(p["sh"] * (close(p["code"], d) or p["last"]) for p in pos)
        buys = 0
        # 原本的進場
        for n in entries.get(d, []):
            t = TR[n]
            if len(pos) >= SLOTS or buys >= DAYMAX: blocked += 1; continue
            amt = min(cash, eq / SLOTS)
            if amt <= 0: blocked += 1; continue
            c = t["in_px"]; sh = amt / (c * (1 + COST / 2)); cash -= amt
            pos.append(dict(code=t["code"], sh=sh, out=t["out"], kind="base", **{"in": c}, d=d, last=c)); buys += 1
        # 加碼
        if mode == "add":
            for e in adds.get(d, []):
                if len(pos) >= SLOTS or buys >= DAYMAX: continue
                if not any(p["kind"] == "base" and p["code"] == e["code"] for p in pos): continue  # 原本那筆要還在手上
                if not block_ok:
                    # 20 天內原本的佔槽加上現有加碼單都要留得下這一槽
                    j_end = idx[e["out_d"]]
                    cur_adds = [p for p in pos if p["kind"] == "add"]
                    ok = True
                    for j in range(i, j_end):
                        n_adds_j = sum(1 for p in cur_adds if idx[p["out"]] > j)
                        if occ[j] + n_adds_j + 1 > SLOTS: ok = False; break
                    if not ok: continue
                amt = min(cash, eq / SLOTS * size_frac)
                if amt <= 0: continue
                c = e["px"]; sh = amt / (c * (1 + COST / 2)); cash -= amt
                pos.append(dict(code=e["code"], sh=sh, out=e["out_d"], kind="add", **{"in": c}, d=d, last=c)); buys += 1; n_add += 1
        for p in pos:
            c = close(p["code"], d)
            if c: p["last"] = c
        eq = cash + sum(p["sh"] * p["last"] for p in pos)
        eq_curve.append((d, eq))
    return eq_curve, trades, blocked, n_add

def stats(eq_curve, trades):
    d0, e0 = eq_curve[0]; d1, e1 = eq_curve[-1]
    yrs = (idx[d1] - idx[d0]) / 245.0
    cagr = (e1 / e0) ** (1 / yrs) - 1
    peak = -1; mdd = 0
    for d, e in eq_curve:
        peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    # 年報酬
    by_year = {}; prev = None; last_e = {}
    for d, e in eq_curve:
        y = d[:4]; last_e[y] = e
    ys = sorted(last_e); yr = {}
    base = e0
    for y in ys:
        yr[y] = (last_e[y] / base - 1) * 100; base = last_e[y]
    half1 = [t for t in trades if t["d"] < "2022-01-01"]; half2 = [t for t in trades if t["d"] >= "2022-01-01"]
    return dict(cagr=cagr * 100, mdd=mdd * 100, final=e1, n=len(trades), win=100 * sum(1 for t in trades if t["ret"] > 0) / max(1, len(trades)),
                avg=statistics.mean(t["ret"] for t in trades) if trades else 0, yr=yr,
                n_add=sum(1 for t in trades if t["kind"] == "add"),
                add_avg=statistics.mean([t["ret"] for t in trades if t["kind"] == "add"]) if any(t["kind"] == "add" for t in trades) else None)

if __name__ == "__main__":
    print("trades", len(TR), "events", len(EV))
    rows = []
    for nm, kw in [("基準：原本 6 槽", dict(mode="base")),
                   ("A1 再訊號補空槽（可擠掉原本進場）", dict(mode="add", block_ok=True)),
                   ("A2 再訊號補空槽（不擠掉原本進場）", dict(mode="add", block_ok=False)),
                   ("A3 同 A2，只在現價 > 第一筆成本", dict(mode="add", block_ok=False, need_above=True)),
                   ("A4 同 A2，只在進場 5 天後", dict(mode="add", block_ok=False, min_off=5)),
                   ("A5 同 A2，加碼單半槽", dict(mode="add", block_ok=False, size_frac=0.5)),
                   ("A6 同 A1，只在現價 > 第一筆成本", dict(mode="add", block_ok=True, need_above=True))]:
        eq, tr, blocked, n_add = run(**kw)
        s = stats(eq, tr)
        rows.append((nm, s, blocked, n_add))
        print("\n== %s" % nm)
        print("  年化 %.1f%%  最大回撤 %.1f%%  筆數 %d（加碼 %d）  勝率 %.1f%%  每筆 %+.2f%%  加碼單每筆 %s  被擠掉的原本進場 %d" % (
            s["cagr"], s["mdd"], s["n"], s["n_add"], s["win"], s["avg"], ("%+.2f%%" % s["add_avg"]) if s["add_avg"] is not None else "—", blocked))
        print("  逐年 " + "  ".join("%s %+.0f" % (y[2:], v) for y, v in s["yr"].items()))
    pickle.dump(rows, open("sim_rows.pkl", "wb"))
