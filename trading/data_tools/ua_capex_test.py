# -*- coding: utf-8 -*-
"""
優分析講義（CH1「上修資本支出＝最強徵象」、CH4 折舊／資本支出看位置）能量化的規則，用雷達已經抓好的財報細項 fin_ext.json 回測。
雲端那邊只有 10 年的損益表／資產負債表快取，沒有現金流量表，所以資本支出、折舊只能在你電腦上測（fin_ext 從 2020Q4 起，
資本支出年增要 8 季、折舊年增要 6 季 → 訊號大約從 2022 年中到現在，4 年多；結果只能當參考，不能當 10 年驗證）。

訊號（都在法定公布期限後第一個交易日收盤買，抱 60 天；同時看 120 天）：
  cap50   資本支出年增（近 4 季 vs 前 4 季）≥ 50%、營收 TTM 年增 > 0                         ＝ CH1「上修資本支出」的代理
  late    cap50 且 資本支出 ≥ 折舊 1.5 倍、折舊年增 < 15%                                   ＝ 雷達 ch4「價漲期後段（新產能在路上）」
  price   折舊年增 < 15%、營收 TTM 年增 ≥ 10%、毛利率（近 4 季 vs 前 4 季）升 ≥ 1.5 點、不是 late  ＝ 「價漲期（既有產能）」
  pre     折舊年增 < 15%、營收 TTM 年增 ≥ 10%、毛利率沒升                                   ＝ 「醞釀」
  vol1    折舊年增 ≥ 15%、毛利率升 ≥ 1.5 點                                                ＝ 「量增期・價量齊揚」
  vol2    折舊年增 ≥ 15%、毛利率 −1.5～+1.5 點                                             ＝ 「量增期・量增接棒」
  vol3    折舊年增 ≥ 15%、毛利率降 ≥ 1.5 點                                                ＝ 「量增期・量增價跌」（預期最差）
  lag     同族群（data/groups.csv）≥ 1/3 成員折舊年增 ≥ 15%，自己折舊年增 < 10%、單季營收年增 ≥ 10% ＝ 「落後受惠者 ★」
  each    另算「＋60 日比 0050 多 20 點（股價先動）」
基準＝同一天所有有財報細項的股票。帳戶模擬：10 槽 × 10%、閒錢 0050 含息、抱 60 天（借 xlev_pool_recheck.run_pool）。

用法：雙擊「優分析資本支出驗證.bat」，或 python ua_capex_test.py [--since 2022-01-01] [--hold 60]
要 data/fin_ext.json、data/fin_history.json、data/k10y、data/exdiv.json、data/groups.csv。約 2～5 分鐘。
結果寫到 優分析資本支出_驗證.md。這是歷史回測，不是投資建議。
"""
import os, sys, bisect, argparse, statistics, collections
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
COST = 0.0047
POS = ["cap50", "late", "price", "pre", "vol1", "vol2", "vol3", "lag", "slow"]
NM = {"cap50": "資本支出年增 ≥50%＋營收成長（上修資本支出代理）", "late": "價漲期後段（資本支出大增、折舊未升）", "price": "價漲期（既有產能，毛利率升）",
      "pre": "醞釀（營收長、毛利率沒升）", "vol1": "量增期・價量齊揚", "vol2": "量增期・量增接棒", "vol3": "量增期・量增價跌", "lag": "落後受惠者 ★（同組折舊已升、自己還沒）",
      "slow": "趨緩／不在週期", "ALL": "全部有財報細項的（基準）"}


def due_date(q):
    y, n = int(q[:4]), int(q[5])
    return date(y + 1, 3, 31) if n == 4 else [None, date(y, 5, 15), date(y, 8, 14), date(y, 11, 14)][n]


def ttm4(single, q, key):
    """single: {q: 單季 dict}；近 4 季合計"""
    import tw_radar as R
    vals = []
    for j in range(4):
        s = single.get(R._ms_qprev(q, j))
        if not s or s.get(key) is None:
            return None
        vals.append(float(s[key]))
    return sum(vals)


def metrics(R, X, FIN, c, q):
    """一檔一季：dep_g、cap_g、cap_dep、rev_g、gm_d、rq（單季營收年增）"""
    rows = X.get(c) or {}
    if q not in rows:
        return None
    f = FIN.get(c) or {}
    single = {}
    for qq in f:
        s = R._fd_single(f, qq)
        if s:
            single[qq] = s
    m = {"q": q}
    r4, r4p = ttm4(single, q, "rev"), ttm4(single, R._ms_qprev(q, 4), "rev")
    g4, g4p = ttm4(single, q, "gross"), ttm4(single, R._ms_qprev(q, 4), "gross")
    if r4 and r4p and r4p > 0:
        m["rev_g"] = (r4 / r4p - 1) * 100
    if r4 and r4p and g4 is not None and g4p is not None and g4 < r4 * 0.995:
        m["gm_d"] = g4 / r4 * 100 - g4p / r4p * 100
    s0, s4 = single.get(q), single.get(R._ms_qprev(q, 4))
    if s0 and s4 and s4.get("rev"):
        m["rq"] = (s0["rev"] / s4["rev"] - 1) * 100
    dep = R._ch4_qdiff(rows, "dep_ytd"); cap = R._ch4_qdiff(rows, "capex_ytd")
    dep = dict((k, v) for k, v in dep.items() if v is not None and v >= 0)
    if q in dep:
        m["dep_g"] = R._ch4_yoy(dep, q, 2)
    if q in cap and cap[q] is not None:
        m["cap_g"] = R._ch4_yoy(cap, q, 4)
        c4, d4 = R._ch4_sum(cap, q, 4), R._ch4_sum(dep, q, 4) if q in dep else None
        if c4 is not None and d4:
            m["cap_dep"] = c4 / d4
    return m


def classify(m):
    out = set()
    dg, cg, cd, rg, gd = m.get("dep_g"), m.get("cap_g"), m.get("cap_dep"), m.get("rev_g"), m.get("gm_d")
    if cg is not None and cg >= 50 and rg is not None and rg > 0:
        out.add("cap50")
    if dg is None:
        return out
    if dg >= 15:
        if gd is None:
            out.add("vol2")
        elif gd >= 1.5:
            out.add("vol1")
        elif gd <= -1.5:
            out.add("vol3")
        else:
            out.add("vol2")
    else:
        if cg is not None and cg >= 50 and cd is not None and cd >= 1.5:
            out.add("late")
        elif rg is not None and rg >= 10 and gd is not None and gd >= 1.5:
            out.add("price")
        elif rg is not None and rg >= 10:
            out.add("pre")
        else:
            out.add("slow")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2022-01-01")
    ap.add_argument("--hold", type=int, default=60)
    ap.add_argument("--slots", type=int, default=10)
    ap.add_argument("--frac", type=float, default=0.10)
    ap.add_argument("--out", default=os.path.join(HERE, "優分析資本支出_驗證.md"))
    a = ap.parse_args()
    import tw_radar as R
    import fin_pub_recheck as F
    from xlev_pool_recheck import tr0050, run_pool
    L = ["# 優分析：資本支出／折舊規則回測（fin_ext，%s）" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    P = lambda s: (print(s), L.append(s))
    X = R.fx_load()["rows"]
    FIN = R.load_fin_history() or {}
    px, cal = F.load_px(R, a.since)
    M = F.Mkt(px, cal)
    tr = tr0050(R, M)
    try:
        by_code = R.load_groups()[0] or {}
    except Exception:
        by_code = {}
    P("- 財報細項 %d 檔、季報 %d 檔、日 K %d 檔（%s ～ %s）、族群表 %d 檔" % (len(X), len(FIN), len(px), cal[0], cal[-1], len(by_code)))
    # 每檔每季的指標
    MET = {}
    qs_all = set()
    for c in X:
        if not (len(c) == 4 and c.isdigit()) or c.startswith("00") or c not in px:
            continue
        for q in X[c]:
            if due_date(q).isoformat() < a.since:
                continue
            m = metrics(R, X, FIN, c, q)
            if m and (m.get("dep_g") is not None or m.get("cap_g") is not None):
                MET[(c, q)] = m; qs_all.add(q)
    # 落後者：同族群同一季
    grp_dep = collections.defaultdict(lambda: collections.defaultdict(list))   # (group, q) -> [dep_g]
    for (c, q), m in MET.items():
        if m.get("dep_g") is None:
            continue
        for g in by_code.get(c, []) or []:
            grp_dep[(g, q)]["x"].append(m["dep_g"])
    def is_lag(c, q, m):
        if m.get("dep_g") is None or m["dep_g"] >= 10 or m.get("rq") is None or m["rq"] < 10:
            return False
        for g in by_code.get(c, []) or []:
            L2 = grp_dep.get((g, q), {}).get("x") or []
            if len(L2) >= 3 and sum(1 for x in L2 if x >= 15) / len(L2) >= 0.34:
                return True
        return False
    # 事件
    EV = collections.defaultdict(list)
    for (c, q), m in sorted(MET.items()):
        d_in = M.first_td_after(due_date(q), 1)
        if not d_in or not M.liquid(c, d_in):
            continue
        i = M.idx[d_in]
        if i < 60 or i + a.hold >= len(cal):
            continue
        b = M.bar(c, d_in); b60 = M.bar(c, cal[i - 60])
        r60x = None
        if b and b60 and tr[i] and tr[i - 60]:
            r60x = (float(b[3]) / float(b60[3]) - 1) * 100 - (tr[i] / tr[i - 60] - 1) * 100
        fw = {}
        for n in (60, 120):
            if i + n < len(cal):
                r, d_out = M.ret_close(c, d_in, n, COST)
                if r is not None and tr[i + n]:
                    fw[n] = r - (tr[i + n] / tr[i] - 1) * 100
        if 60 not in fw:
            continue
        d_out = M.shift(d_in, a.hold); bo = M.bar(c, d_out) if d_out else None
        ev = dict(code=c, q=q, d=d_in, r60x=r60x, fx60=fw[60], fx120=fw.get(120), m=m,
                  trade=dict(strat="ua", code=c, buy=d_in, buy_px=float(b[3]), sell=d_out, sell_px=float(bo[3])) if bo else None)
        EV["ALL"].append(ev)
        for k in classify(m):
            EV[k].append(ev)
        if is_lag(c, q, m):
            EV["lag"].append(ev)
    P("- 事件（檔×季）：" + "、".join("%s %d" % (k, len(EV[k])) for k in ["ALL"] + POS))
    P("")
    def st(E, key="fx60"):
        v = [e[key] for e in E if e.get(key) is not None]
        if not v:
            return "—"
        return "n %4d；中位 %+.2f、平均 %+.2f、贏 0050 %.0f%%" % (len(v), statistics.median(v), statistics.mean(v), 100 * sum(1 for x in v if x > 0) / len(v))
    P("## 事件統計：買進日收盤 → N 個交易日後，扣 0050 同期（含息）")
    P("")
    P("| 位置 | 60 天 | 60 天＋先漲 >20 點 | 60 天・落後 0050 | 120 天 |")
    P("|---|---|---|---|---|")
    for k in ["ALL"] + POS:
        E = EV[k]
        P("| %s | %s | %s | %s | %s |" % (NM[k], st(E), st([e for e in E if e["r60x"] is not None and e["r60x"] > 20]),
                                        st([e for e in E if e["r60x"] is not None and e["r60x"] <= 0]), st(E, "fx120")))
    P("")
    P("### 逐年（60 天超額中位，n）")
    years = sorted(set(e["d"][:4] for e in EV["ALL"]))
    P("| 位置 | " + " | ".join(years) + " |")
    P("|---|" + "---|" * len(years))
    for k in ["ALL"] + POS:
        cells = []
        for y in years:
            v = [e["fx60"] for e in EV[k] if e["d"][:4] == y]
            cells.append("%+.1f (%d)" % (statistics.median(v), len(v)) if v else "—")
        P("| %s | " % NM[k] + " | ".join(cells) + " |")
    P("")
    P("## 帳戶模擬：%d 槽 × %.0f%%、閒錢 0050 含息、抱 %d 天、股票來回 %.2f%%" % (a.slots, a.frac * 100, a.hold, COST * 100))
    P("")
    start = M.first_td_after(date.fromisoformat(a.since), 1); end = cal[-1]
    b0 = run_pool(M, tr, [], start, end, a.slots, a.frac)
    P("| 做法 | 年化 | 最大回撤 | 筆數 | 每筆 | 勝率 | 逐年 |")
    P("|---|---|---|---|---|---|---|")
    P("| 只抱 0050 含息 | %.1f%% | %.1f%% | | | | %s |" % (b0["cagr"], b0["mdd"], " ".join("%s %+.0f" % (y[2:], v) for y, v in b0["yr"].items())))
    for k in POS:
        for lab, E in ((NM[k], EV[k]), ("　＋先漲 >20 點", [e for e in EV[k] if e["r60x"] is not None and e["r60x"] > 20])):
            T = [e["trade"] for e in E if e["trade"]]
            if len(T) < 20:
                P("| %s | 筆數 %d 太少 | | | | | |" % (lab, len(T))); continue
            r = run_pool(M, tr, T, start, end, a.slots, a.frac)
            P("| %s | %.1f%% | %.1f%% | %d | %+.2f%% | %.0f%% | %s |" % (lab, r["cagr"], r["mdd"], r["n"], r["avg"], r["win"],
                                                                   " ".join("%s %+.0f" % (y[2:], v) for y, v in r["yr"].items())))
    P("")
    P("## 怎麼讀")
    P("- 這份只有 %s 起的資料（fin_ext 從 2020Q4 開始抓，資本支出年增要 8 季）。四年多、一個多頭段，不夠格當 10 年驗證；"
      "看的是方向：哪個位置的 60 天超額中位是正的、而且逐年不翻臉。" % a.since[:4])
    P("- 雷達自己的 fund_ext_bt（2024-06 起）也有一條 w_capex（近四季資本支出佔營收是過去 1.5 倍）：60 天超額 +1.9 點、923 筆，"
      "方向跟課程說的一樣（擴產是利多不是警示），這份用更長的區間再看一次。")
    P("- 同一天訊號會擠在 5/15、8/14、11/14、3/31 後面那一天，10 槽一下就滿；帳戶模擬的年化只代表「先到先買」那一種排序，事件統計比較可信。")
    P("- 這是歷史回測，不是投資建議。")
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n  結果已寫到 %s。跟 Claude 說「資本支出驗證跑好了」。" % a.out)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        import traceback; traceback.print_exc()
        print("\n失敗：%s" % str(e)[:300]); sys.exit(1)
