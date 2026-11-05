# -*- coding: utf-8 -*-
"""
季報意外獲利「公告隔天收盤買」版，放進 0050 小帳戶（10 槽 × 10%，閒錢放 0050 含息）算年化、回撤，
跟原本「期限後第 2 個交易日買」版、和只抱 0050 比。接在 fin_pub_recheck.py 後面（同一套訊號、同一套出場）。

  A 期限後第 2 個交易日收盤買（雷達現在的規則）
  B 實際公布後第一個收盤買（13:30 前公布＝當天，否則隔天）
  C 公布後下一個交易日收盤買（看到公告隔天買；建議上線用這版）
  另外算：C ＋ 信用交易恢復（期限後第 1 天買、第 6 天開盤賣）合在一個 0050 小帳戶（季報 10%、信用恢復 5%）＝「事件小帳戶 A」

資料：跟 fin_pub_recheck.py 一樣（fin10、fin_history、k10y、fin_pub10.json.gz），加 data/exdiv.json（0050 配息）。
用法：雙擊「季報公告日版帳戶模擬.bat」，或 python xlev_pool_recheck.py [--since 2016-04-06] [--slots 10] [--frac 0.10]
結果寫到 季報公告日版帳戶模擬.md（2～5 分鐘）。這是歷史回測，不是投資建議。
"""
import os, sys, json, bisect, argparse, statistics, collections
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

COST_STK = 0.0047      # 股票來回
COST_50 = 0.0015       # 0050 單邊
DIV_MANUAL = {"2016-10-26": 0.85, "2017-02-08": 1.70, "2017-07-31": 0.70, "2018-01-29": 2.20, "2018-07-23": 0.70, "2019-01-22": 2.30, "2019-07-19": 0.70,
              "2020-01-31": 2.90, "2020-07-21": 0.70, "2021-01-22": 3.05, "2021-07-21": 0.35, "2022-01-21": 3.20, "2022-07-18": 1.80, "2023-01-30": 2.60, "2023-07-18": 1.90}


def tr0050(R, M):
    """0050 含息單位淨值（配息再投入、2025-06 一拆四還原）；回傳 list 對齊 M.cal"""
    div = dict(DIV_MANUAL)
    try:
        ex = R._jload(os.path.join(R.DATA_DIR, "exdiv.json"), {}) or {}
        for r in (ex.get("by") or {}).get("0050", []) or []:
            if str(r.get("d", "")) >= "2024-01-01" and r.get("tot"):
                div[r["d"]] = float(r["tot"])
    except Exception:
        pass
    divs = {}
    for d, v in div.items():
        i = bisect.bisect_left(M.cal, d)
        if i < len(M.cal):
            divs[M.cal[i]] = divs.get(M.cal[i], 0) + v
    c = []; last = None
    for d in M.cal:
        b = M.bar("0050", d); last = float(b[3]) if b and b[3] else last; c.append(last)
    for i in range(1, len(c)):
        if c[i] and c[i - 1] and c[i] / c[i - 1] < 0.6:
            ratio = round(c[i - 1] / c[i])
            for j in range(i):
                if c[j]: c[j] /= ratio
            for d in list(divs):
                if d < M.cal[i]: divs[d] /= ratio
    units = 1.0; tr = []
    for i, d in enumerate(M.cal):
        if d in divs and c[i]: units *= (1 + divs[d] / c[i])
        tr.append(units * c[i] if c[i] else None)
    # 補 None
    last = None
    for i in range(len(tr)):
        if tr[i] is None: tr[i] = last
        else: last = tr[i]
    return tr


def build_trades(F, M, S, pub, a):
    """三種進場的 xlev 交易，和 cr（A 版）交易。每筆 dict(strat, code, buy, buy_px, sell, sell_px)"""
    out = {"A": [], "B": [], "C": [], "cr": []}
    for s in S["xlev"]:
        c, q = s[0], s[1]
        if F.due_date(q).isoformat() < a.since:
            continue
        E = F.entry_days(M, q, pub.get((c, q)))
        days = {"A": M.first_td_after(E["due"], 2), "B": E.get("B"), "C": E.get("C")}
        for v, d_in in days.items():
            if not d_in or not M.liquid(c, d_in):
                continue
            r20 = M.run20(c, d_in)
            if r20 is not None and r20 >= 10:
                continue
            d_out = M.shift(d_in, 16)
            bi, bo = M.bar(c, d_in), M.bar(c, d_out) if d_out else None
            if not bi or not bo:
                continue
            out[v].append(dict(strat="xlev", code=c, buy=d_in, buy_px=float(bi[3]), sell=d_out, sell_px=float(bo[3])))
    for s in S["cr"]:
        c, q = s[0], s[1]
        if F.due_date(q).isoformat() < a.since:
            continue
        d_in = M.first_td_after(F.due_date(q), 1)
        if not d_in or not M.liquid(c, d_in):
            continue
        d_out = M.shift(d_in, 5)
        bi, bo = M.bar(c, d_in), M.bar(c, d_out) if d_out else None
        if not bi or not bo or not bo[0]:
            continue
        out["cr"].append(dict(strat="cr", code=c, buy=d_in, buy_px=float(bi[3]), sell=d_out, sell_px=float(bo[0])))
    return out


def run_pool(M, tr, trades, start, end, slots=10, frac=0.10, priority=("xlev", "cr")):
    byday = collections.defaultdict(list)
    for t in trades:
        byday[t["buy"]].append(t)
    i0 = bisect.bisect_left(M.cal, start); i1 = min(bisect.bisect_right(M.cal, end) - 1, len(M.cal) - 1)
    while tr[i0] is None: i0 += 1
    units50 = 1.0 / tr[i0]; pos = []; eq = []; done = []; blocked = collections.Counter()
    for i in range(i0, i1 + 1):
        d = M.cal[i]
        keep = []
        for p in pos:
            if p["sell"] == d or i == i1:
                spx = p["sell_px"] if p["sell"] == d else (float((M.bar(p["code"], d) or [0, 0, 0, p["buy_px"]])[3]))
                proceeds = p["sh"] * spx * (1 - COST_STK / 2)
                units50 += proceeds * (1 - COST_50) / tr[i]
                done.append(dict(p, ret=(spx / p["buy_px"] - 1) * 100 - COST_STK * 100))
            else:
                keep.append(p)
        pos = keep
        mv = lambda: sum(p["sh"] * float((M.bar(p["code"], d) or [0, 0, 0, p["buy_px"]])[3]) for p in pos)
        equity = units50 * tr[i] + mv()
        cands = sorted(byday.get(d, []), key=lambda t: priority.index(t["strat"]) if t["strat"] in priority else 9)
        for t in cands:
            if any(p["code"] == t["code"] for p in pos):
                blocked["dup"] += 1; continue
            if len(pos) >= slots:
                blocked[t["strat"]] += 1; continue
            fr = frac if not isinstance(frac, dict) else frac.get(t["strat"], 0.10)
            amt = equity * fr
            avail = units50 * tr[i] * (1 - COST_50)
            if avail < amt * 0.5:
                blocked[t["strat"] + "_cash"] += 1; continue
            amt = min(amt, avail); need = amt / (1 - COST_50)
            units50 -= need / tr[i]
            pos.append(dict(t, sh=amt * (1 - COST_STK / 2) / t["buy_px"]))
        eq.append((d, units50 * tr[i] + mv()))
    yrs = (i1 - i0) / 245.0; cagr = (eq[-1][1] / eq[0][1]) ** (1 / yrs) - 1
    peak = 0; mdd = 0
    for _, e in eq:
        peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    ye = {}
    for d, e in eq: ye[d[:4]] = e
    yr = {}; base = eq[0][1]
    for y in sorted(ye): yr[y] = (ye[y] / base - 1) * 100; base = ye[y]
    return dict(cagr=cagr * 100, mdd=mdd * 100, n=len(done), avg=(statistics.mean(t["ret"] for t in done) if done else 0),
                win=(100 * sum(1 for t in done if t["ret"] > 0) / len(done)) if done else 0, blocked=dict(blocked), yr=yr,
                by=dict(collections.Counter(t["strat"] for t in done)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2016-04-06")
    ap.add_argument("--slots", type=int, default=10)
    ap.add_argument("--frac", type=float, default=0.10)
    ap.add_argument("--out", default=os.path.join(HERE, "季報公告日版帳戶模擬.md"))
    a = ap.parse_args()
    import tw_radar as R
    import fin_pub_dl as FP
    import fin_pub_recheck as F
    FP.R = R
    L = ["# 季報意外獲利：公告日版 vs 期限日版，放進 0050 小帳戶（%s）" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    P = lambda s: (print(s), L.append(s))
    pub, msg = F.load_pub(R, FP)
    P("- 公布時間：%s" % msg)
    if not pub:
        return 1
    fin = F.load_fin(R)
    px, cal = F.load_px(R, a.since)
    M = F.Mkt(px, cal)
    tr = tr0050(R, M)
    S = F.signals(fin, a.since)
    T = build_trades(F, M, S, pub, a)
    end = cal[-1]
    P("- 期間 %s ～ %s；%d 槽 × %.0f%%；股票來回 %.2f%%、0050 單邊 %.2f%%" % (a.since, end, a.slots, a.frac * 100, COST_STK * 100, COST_50 * 100))
    P("- 交易數：A %d、B %d、C %d；信用交易恢復 %d" % (len(T["A"]), len(T["B"]), len(T["C"]), len(T["cr"])))
    P("")
    rows = [("只抱 0050 含息", []), ("A 期限後第 2 天買（雷達現在）", T["A"]), ("B 公布後第一個收盤買", T["B"]), ("C 公布後隔天收盤買", T["C"])]
    res = {}
    P("| 做法 | 年化 | 最大回撤 | 筆數 | 每筆 | 勝率 | 被擠掉 |")
    P("|---|---|---|---|---|---|---|")
    for nm, tl in rows:
        r = run_pool(M, tr, tl, a.since, end, a.slots, a.frac); res[nm] = r
        P("| %s | %.1f%% | %.1f%% | %d | %+.2f%% | %.0f%% | %s |" % (nm, r["cagr"], r["mdd"], r["n"], r["avg"], r["win"], r["blocked"] or "—"))
    # 事件小帳戶 A：C ＋ 信用恢復（季報 10%、信用恢復 5%）
    r = run_pool(M, tr, T["C"] + T["cr"], a.since, end, 20, {"xlev": 0.10, "cr": 0.05}, ("cr", "xlev")); res["AC"] = r
    P("| 事件小帳戶 A：C ＋ 信用恢復（共 20 槽；季報 10%%、信用恢復 5%%） | %.1f%% | %.1f%% | %d %s | %+.2f%% | %.0f%% | %s |" % (r["cagr"], r["mdd"], r["n"], r["by"], r["avg"], r["win"], r["blocked"] or "—"))
    r = run_pool(M, tr, T["A"] + T["cr"], a.since, end, 20, {"xlev": 0.10, "cr": 0.05}, ("cr", "xlev")); res["AA"] = r
    P("| 對照：A ＋ 信用恢復（同上） | %.1f%% | %.1f%% | %d %s | %+.2f%% | %.0f%% | %s |" % (r["cagr"], r["mdd"], r["n"], r["by"], r["avg"], r["win"], r["blocked"] or "—"))
    P("")
    ys = sorted(set(y for r in res.values() for y in r["yr"]))
    P("逐年報酬（%）：")
    P("| 做法 | " + " | ".join(ys) + " | 贏 0050 的年數 |")
    P("|---|" + "---|" * (len(ys) + 1))
    base = res["只抱 0050 含息"]["yr"]
    for nm, r in res.items():
        win = sum(1 for y in ys if r["yr"].get(y, 0) > base.get(y, 0))
        P("| %s | " % nm + " | ".join("%+.0f" % r["yr"].get(y, 0) for y in ys) + " | %d/%d |" % (win, len(ys)))
    L += ["", "註：同一套訊號、同一套出場（抱 16 個交易日收盤賣），只差進場日。B 假設看到公告能在收盤前掛單，C 是隔天才買。",
          "C 版的訊號會散在整個公布期間（例如 5 月初到 5/15），不像 A 版擠在同一天，所以被擠掉的筆數通常比較少。",
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
