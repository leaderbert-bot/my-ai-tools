# -*- coding: utf-8 -*-
"""
融資斷頭貨（巨人傑第二層）帳戶版：把雷達「融資維持率」頁回測裡的個股交易拿出來，放進 0050 小帳戶算年化、回撤。

雷達 cr10_build() 已經算好每一筆（V0～V6 × 抱 20／60 天：訊號日收盤後知道、隔天開盤買、第 N 天收盤賣、扣成本），
但只存統計不存逐筆。這支把它的程式碼原樣借來跑一次（多存逐筆），不改雷達本體，也不改 credit_bt.json 的內容。
然後：10 槽 × 10%、閒錢放 0050 含息、同一天訊號比空位多時照原順序／隨機 30 次。

用法：雙擊「融資斷頭貨帳戶模擬.bat」，或 python crash_pool.py [--slots 10] [--frac 0.10]
要 data/credit10（融資維持率回測.bat 抓的十年信用資料）、data/k10y、data/exdiv.json。約 3～6 分鐘。
結果寫到 融資斷頭貨帳戶模擬.md。這是歷史回測，不是投資建議。
"""
import os, sys, re, bisect, random, inspect, argparse, statistics, collections
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
COST_STK = 0.0047; COST_50 = 0.0015
ANCHOR = 'res["secs"] = round(time.time() - t0, 1)'


def get_trades(R):
    """借 cr10_build 的程式碼跑一次，把逐筆交易和日曆存下來。"""
    src = inspect.getsource(R.cr10_build)
    if src.count(ANCHOR) != 1:
        raise RuntimeError("tw_radar.cr10_build 版本跟預期不同（找不到存檔前那一行）")
    src = src.replace("def cr10_build(", "def _cr10_build_dump(", 1)
    src = src.replace(ANCHOR, ANCHOR + "; _CR_DUMP['trades'] = dict(('%s|%d' % k, v) for k, v in trades.items()); _CR_DUMP['days'] = list(days)", 1)
    R._CR_DUMP = {}
    exec(compile(src, "<cr10_build_dump>", "exec"), R.__dict__)
    R._cr10_build_dump()
    return R._CR_DUMP.get("trades") or {}, R._CR_DUMP.get("days") or []


def run_pool(M, tr, trades, start, end, slots, frac, seed=None):
    """trades: [dict(code, buy, buy_px, sell, ret)]；buy 當天開盤買（買價 buy_px），sell 當天收盤賣（報酬 ret 已扣成本）"""
    byday = collections.defaultdict(list)
    for t in trades:
        byday[t["buy"]].append(t)
    rng = random.Random(seed) if seed is not None else None
    i0 = bisect.bisect_left(M.cal, start); i1 = min(bisect.bisect_right(M.cal, end) - 1, len(M.cal) - 1)
    while tr[i0] is None: i0 += 1
    units50 = 1.0 / tr[i0]; pos = []; eq = []; done = []; blocked = collections.Counter()
    for i in range(i0, i1 + 1):
        d = M.cal[i]; keep = []
        for p in pos:
            if p["sell"] == d or i == i1:
                val = p["amt"] * (1 + p["ret"]) if p["sell"] == d else p["amt"] * (float((M.bar(p["code"], d) or [0, 0, 0, p["buy_px"]])[3]) / p["buy_px"])
                units50 += val * (1 - COST_50) / tr[i]
                done.append(dict(p, r=(p["ret"] if p["sell"] == d else 0) * 100))
            else:
                keep.append(p)
        pos = keep
        mv = lambda: sum(p["amt"] * float((M.bar(p["code"], d) or [0, 0, 0, p["buy_px"]])[3]) / p["buy_px"] for p in pos)
        equity = units50 * tr[i] + mv()
        L = list(byday.get(d, []))
        if rng is not None: rng.shuffle(L)
        for t in L:
            if any(p["code"] == t["code"] for p in pos):
                blocked["dup"] += 1; continue
            if len(pos) >= slots:
                blocked["full"] += 1; continue
            amt = equity * frac
            avail = units50 * tr[i] * (1 - COST_50)
            if avail < amt * 0.5:
                blocked["cash"] += 1; continue
            amt = min(amt, avail); units50 -= amt / (1 - COST_50) / tr[i]
            pos.append(dict(t, amt=amt))
        eq.append((d, units50 * tr[i] + mv()))
    yrs = (i1 - i0) / 245.0; cagr = (eq[-1][1] / eq[0][1]) ** (1 / yrs) - 1
    peak = 0; mdd = 0
    for _, e in eq:
        peak = max(peak, e); mdd = min(mdd, e / peak - 1)
    ye = {}
    for d, e in eq: ye[d[:4]] = e
    yr = {}; base = eq[0][1]
    for y in sorted(ye): yr[y] = (ye[y] / base - 1) * 100; base = ye[y]
    return dict(cagr=cagr * 100, mdd=mdd * 100, n=len(done), avg=(statistics.mean(x["r"] for x in done) if done else 0),
                win=(100 * sum(1 for x in done if x["r"] > 0) / len(done)) if done else 0, blocked=dict(blocked), yr=yr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slots", type=int, default=10)
    ap.add_argument("--frac", type=float, default=0.10)
    ap.add_argument("--out", default=os.path.join(HERE, "融資斷頭貨帳戶模擬.md"))
    a = ap.parse_args()
    import tw_radar as R
    import fin_pub_recheck as F
    import xlev_pool_recheck as X
    L = ["# 融資斷頭貨（巨人傑第二層）帳戶版：放進 0050 小帳戶（%s）" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    P = lambda s: (print(s), L.append(s))
    print("  借雷達 cr10_build 跑一次（1～3 分鐘）…")
    T, days = get_trades(R)
    if not T:
        P("  沒有拿到交易（data/credit10 還沒抓？先雙擊「融資維持率回測.bat」）。"); return 1
    dpos = dict((d, i) for i, d in enumerate(days))
    px, cal = F.load_px(R, "2016-01-01")
    M = F.Mkt(px, cal); tr = X.tr0050(R, M)
    start = max(days[0], cal[0]); end = min(days[-1], cal[-1])
    VAR = dict(R.CR_VAR)
    P("- 期間 %s ～ %s；%d 槽 × %.0f%%；閒錢放 0050 含息；股票來回 %.2f%%、0050 單邊 %.2f%%" % (start, end, a.slots, a.frac * 100, COST_STK * 100, COST_50 * 100))
    P("- 個股交易照雷達回測：訊號日收盤後知道、隔天開盤買、第 N 個交易日收盤賣；普通股、20 日均成交值 ≥ 0.3 億、20 天前融資餘額 ≥ 500 張、股價 ≥ 10")
    P("")
    base = run_pool(M, tr, [], start, end, a.slots, a.frac)
    P("| 做法 | 年化 | 最大回撤 | 筆數 | 每筆 | 勝率 | 被擠掉（槽滿／錢不夠／同檔） | 隨機 30 次年化中位（最低～最高） |")
    P("|---|---|---|---|---|---|---|---|")
    P("| 只抱 0050 含息 | %.1f%% | %.1f%% | — | — | — | — | — |" % (base["cagr"], base["mdd"]))
    res = {"0050": base}
    for key in ("V3|60", "V3|20", "V4|60", "V5|60", "V2|60"):
        lst = T.get(key)
        if not lst:
            continue
        var, N = key.split("|"); N = int(N)
        trades = []
        for day, c, ret, exr in lst:
            i = dpos.get(day)
            if i is None or i - N < 0:
                continue
            b_in = days[i - N]
            bar = M.bar(c, b_in)
            if not bar or not bar[0]:
                continue
            trades.append(dict(code=c, buy=b_in, buy_px=float(bar[0]), sell=day, ret=float(ret)))
        r = run_pool(M, tr, trades, start, end, a.slots, a.frac); res[key] = r
        rs = sorted(run_pool(M, tr, trades, start, end, a.slots, a.frac, seed=k)["cagr"] for k in range(30))
        bl = r["blocked"]
        P("| %s 抱 %d 天：%s | %.1f%% | %.1f%% | %d（訊號 %d） | %+.2f%% | %.0f%% | %d／%d／%d | %.1f%%（%.1f～%.1f） |" % (
            var, N, VAR.get(var, ""), r["cagr"], r["mdd"], r["n"], len(trades), r["avg"], r["win"], bl.get("full", 0), bl.get("cash", 0), bl.get("dup", 0), rs[15], rs[0], rs[-1]))
    P("")
    ys = sorted(set(y for r in res.values() for y in r["yr"]))
    P("逐年報酬（%）：")
    P("| 做法 | " + " | ".join(ys) + " | 贏 0050 的年數 |")
    P("|---|" + "---|" * (len(ys) + 1))
    for k, r in res.items():
        win = sum(1 for y in ys if r["yr"].get(y, 0) > base["yr"].get(y, 0))
        P("| %s | " % k + " | ".join("%+.0f" % r["yr"].get(y, 0) for y in ys) + " | %d/%d |" % (win, len(ys)))
    # 訊號集中度
    v3 = T.get("V3|60") or []
    if v3:
        byy = collections.Counter(day[:4] for day, c, ret, exr in v3)
        P("")
        P("- V3 抱 60 天的訊號逐年：%s（崩盤年才有量，其他年份幾乎沒訊號，所以帳戶大部分時間就是 0050）" % "、".join("%s %d" % (y, n) for y, n in sorted(byy.items())))
    L += ["", "註：每筆的進出跟雷達「融資維持率」頁的策略 ② 一模一樣，只是多了帳戶（槽位、閒錢放 0050）。隨機 30 次＝同一天訊號比空位多時隨機挑。",
          "這個策略十年只在崩盤時有訊號；帳戶年化主要看那幾次抓到多少，單一年份的數字不要當常態。這是歷史回測，不是投資建議。"]
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
