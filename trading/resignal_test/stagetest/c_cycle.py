"""任務 C：「產業剛進入某一期 → 從那個產業裡挑股」能不能當獨立的循環選股策略。10 年回測 2016-06-01～2026-10-30。
引擎：mgk_test.py（10 槽 × 10%、抱 HOLD 個交易日收盤賣、閒錢 0050 含息、成本 0.47%），重用方式照 cycle_stage_test.py 第 5 行。
產業位置：stage_lib / stage_data.pkl（證交所產業別，成員 ≥ 6 檔；族群表 groups.csv 另跑、有事後之見）。
訊號：每個月 ym 的產業位置在 A = avail[ym]（下月 11 日後第一個交易日）當天收盤買；個股流動性：進場日前 20 日均量 ≥ 500 張、收盤 ≥ 10 元、當天沒鎖漲停。
 事件型（只在進入當月買）：S1 new_price；S2 剛進入成長期（stage ∈ price/vol/vol? 且 prev ∈ down/flat）；S3 衰退轉正（prev down 且本月非 down）；S4 breadth 突破（≥0.6 且上月 <0.6）
 狀態型（每月都可買）：S5 產業 price 且個股 stage up；S6 產業 price/vol 且個股 mom60 > 20
 成員挑法：(a) 全部合格成員、同日 mom60 大先；(b) 只留個股 stage up；(c) 只留 mom60 > 20；(d) 只留該產業當月 r3 最高前 3 檔；(e) 對照：mom60 小先
用法：cd SP && python3 stagetest/c_cycle.py；試跑 QUICK=1 NSEED=3 OUTF=stagetest/_c_try.txt python3 stagetest/c_cycle.py"""
import sys, os, time, collections, statistics, pickle, random, bisect, json, math, itertools
SP = "/tmp/claude-0/-home-user-my-ai-tools/bb9482f7-4c31-5f24-a06a-81bc958a76a4/scratchpad"
sys.path.insert(0, SP); os.chdir(SP)
NSEED = int(os.environ.get("NSEED", 30)); QUICK = bool(os.environ.get("QUICK"))
OUTF = os.environ.get("OUTF", "stagetest/c_cycle_out.txt")
T0 = time.time()
exec(open('mgk_test.py').read().split('b = run([])')[0])   # px, cal, idx, tr50, c50, rev, avail(), close_near(), run(), COST, HOLD
MGK_SIG = sig; del sig
import stage_lib as S
OUT = open(OUTF, "w")
def P(*a):
    line = " ".join(str(x) for x in a); print(line, flush=True); OUT.write(line + "\n"); OUT.flush()
H1_END = "2021-06-30"; H2_START = "2021-07-01"; PV = ("price", "vol", "vol?")
IND_ROWS, GRP_ROWS, STK = S.D["ind"], S.D["grp"], S.D["stock"]; AV = S.D["avail"]
def ymp(ym, k):
    y, m = int(ym[:4]), int(ym[4:]); m -= k
    while m <= 0: m += 12; y -= 1
    return "%04d%02d" % (y, m)
IND_MEM = collections.defaultdict(list)
for c, k in S.IND.items(): IND_MEM[k].append(c)
GRP_MEM = collections.defaultdict(list)
for c, gs in S.GRP.items():
    for g in gs: GRP_MEM[g].append(c)

# ---------- 0. 基準 ----------
B50 = run([]); B50H1 = run([], end=H1_END)["cagr"]; B50H2 = run([], start=H2_START)["cagr"]; YEARS = sorted(B50["yr"])
P("=" * 130)
P("任務 C：產業剛進入某一期 → 從那個產業裡挑股（引擎 mgk_test.py：10 槽 × 10%%、閒錢 0050 含息、成本 0.47%%、收盤買、抱 HOLD 日收盤賣；%s～%s）" % ("2016-06-01", cal[-1]))
P("0050 含息同期：年化 %.2f%% 回撤 %.2f%%；前半（～%s）年化 %.2f%%、後半（%s～）年化 %.2f%%；逐年 %s" % (B50["cagr"], B50["mdd"], H1_END, B50H1, H2_START, B50H2, " ".join("%s %+.0f" % (y[2:], B50["yr"][y]) for y in YEARS)))
P("產業位置資料：%d 個月（%s～%s，avail %s～%s）、%d 個產業、產業×月 %d 列（price %d / vol %d / vol? %d / flat %d / down %d）；個股×月 %d 列；族群 %d 個、族群×月 %d 列（事後之見）" % (
    len(S.YMS), S.YMS[0], S.YMS[-1], AV[S.YMS[0]], AV[S.YMS[-1]], len(S.industries()), len(IND_ROWS),
    *[sum(1 for o in IND_ROWS.values() if o["stage"] == k) for k in ("price", "vol", "vol?", "flat", "down")], len(STK), len(set(k for k, _ in GRP_ROWS)), len(GRP_ROWS)))
P("注意：產業成員＝今天的上市名單（%d 檔），下市股不在裡面（倖存者偏差）；2016 年產業 gm_d 多半 None → price 位置 2017-04 起才可靠；所有月營收位置在 avail 當天收盤前已知（11 日邊界的輕微偷看見 d_audit）" % len(S.IND))

# ---------- 1. 合格成員（流動性）＋個股欄位 ----------
LIQ = {}; LSTAT = collections.Counter()
def qual(c, ym):
    key = (c, ym)
    if key in LIQ: return LIQ[key]
    A = AV[ym]; i = idx[A]; s = px.get(c); res = None
    if not s: LSTAT["無日K"] += 1
    elif i < 60: LSTAT["太早(<60日)"] += 1
    else:
        bar = s.get(A); b60 = s.get(cal[i - 60])
        if not bar: LSTAT["當天無收盤"] += 1
        elif not b60 or not c50[i] or not c50[i - 60]: LSTAT["60日前無收盤(新股)"] += 1
        else:
            vols = [s[x][4] for x in cal[i - 20:i] if x in s]
            if len(vols) < 15 or sum(vols) / 20 < 500: LSTAT["均量<500張"] += 1
            elif bar[3] < 10: LSTAT["收盤<10元"] += 1
            else:
                pb = s.get(cal[i - 1])
                if pb and bar[3] >= pb[3] * 1.094 and bar[3] >= bar[1] * 0.999: LSTAT["鎖漲停"] += 1
                else:
                    LSTAT["合格"] += 1
                    res = dict(px=bar[3], mom=(bar[3] / b60[3] - 1) * 100 - (c50[i] / c50[i - 60] - 1) * 100)
    LIQ[key] = res; return res
MEMC = {}
def mem_rows(members, ym, tag, scope):
    key = (scope, tag, ym)
    if key in MEMC: return MEMC[key]
    A = AV[ym]; out = []
    for c in members:
        q = qual(c, ym)
        if not q: continue
        st = STK.get((c, ym))
        out.append(dict(code=c, d=A, px=q["px"], r60x=q["mom"], mom=q["mom"], sst=st["stage"] if st else "na", r3=st["r3"] if st else None, ym=ym, ind=tag))
    MEMC[key] = out; return out
def variant(rows, v):
    if v == "a": return [dict(r) for r in rows]
    if v == "b": return [dict(r) for r in rows if r["sst"] == "up"]
    if v == "c": return [dict(r) for r in rows if r["mom"] > 20]
    if v == "d": return [dict(r) for r in sorted([r for r in rows if r["r3"] is not None], key=lambda r: -r["r3"])[:3]]
    if v == "e": return [dict(r, r60x=-r["mom"]) for r in rows]
    raise ValueError(v)
VNAME = {"a": "(a) 全部合格成員，mom60 大先", "b": "(b) 只留個股 stage up", "c": "(c) 只留個股 mom60>20", "d": "(d) 只留該產業當月 r3 前 3 檔", "e": "(e) 對照：mom60 小先"}
def fwd(s, H):
    i = idx[s["d"]]; j = i + H
    if j >= len(cal): return None
    e = close_near(s["code"], cal[j])
    if not e or not tr50[i] or not tr50[j]: return None
    return (e / s["px"] - 1) * 100 - (tr50[j] / tr50[i] - 1) * 100
def build(table, members_of, ev, basef, v, dedupe=False, scope="ind"):
    """回傳 (訊號 list, 事件數, 有訊號的事件數)。ev(k, ym, o) 判斷產業-月是不是事件；basef 是訊號自帶的個股條件（S5/S6）；v 是成員挑法"""
    sigs = []; nev = 0; nev1 = 0; seen = set()
    for (k, ym), o in table.items():
        if not ev(k, ym, o): continue
        nev += 1
        rows = [r for r in mem_rows(members_of(k), ym, k, scope) if basef(r)]
        R = variant(rows, v)
        if R: nev1 += 1
        for r in R:
            if dedupe:
                if (r["code"], r["d"]) in seen: continue
                seen.add((r["code"], r["d"]))
            r["fx60"] = fwd(r, 60); r["fx120"] = fwd(r, 120); sigs.append(r)
    sigs.sort(key=lambda r: (r["d"], r["code"]))
    return sigs, nev, nev1
def ev_S1(k, ym, o): return bool(o["new_price"])
def ev_S2(k, ym, o): return o["stage"] in PV and o["prev_stage"] in ("down", "flat")
def ev_S3(k, ym, o): return o["prev_stage"] == "down" and o["stage"] != "down"
def ev_S4(k, ym, o):
    p = IND_ROWS.get((k, ymp(ym, 1))); return o["breadth"] >= 0.6 and p is not None and p["breadth"] < 0.6
def ev_S5(k, ym, o): return o["stage"] == "price"
def ev_S6(k, ym, o): return o["stage"] in ("price", "vol")
ANY = lambda r: True
SIGDEF = [
 ("S1", "事件：產業 new_price（剛進入價漲期：本月 price、3 個月前不是）", ev_S1, ANY),
 ("S2", "事件：產業剛進入成長期（本月 price/vol/vol?，上月 down/flat）", ev_S2, ANY),
 ("S3", "事件：產業衰退轉正（上月 down，本月不是 down）", ev_S3, ANY),
 ("S4", "事件：產業 breadth 突破（本月 ≥0.6，上月 <0.6）", ev_S4, ANY),
 ("S5", "狀態：產業 price 且 個股 stage up（每月都可買）", ev_S5, lambda r: r["sst"] == "up"),
 ("S6", "狀態：產業 price/vol 且 個股 mom60>20（每月都可買）", ev_S6, lambda r: r["mom"] > 20),
]
if QUICK: SIGDEF = [SIGDEF[0], SIGDEF[4]]
VARS = ["a", "b", "c", "d", "e"]
SIGS = {}   # (sg, v) -> (sigs, nev, nev1)
for sg, nm, ev, basef in SIGDEF:
    for v in VARS: SIGS[(sg, v)] = build(IND_ROWS, lambda k: IND_MEM[k], ev, basef, v)
# 對照：不看產業位置的全市場
UNIV_ROWS = {}
for ym in S.YMS:
    UNIV_ROWS[("全市場", ym)] = dict(stage="x")
ALLCODES = sorted(S.IND)
CTRL = [
 ("U1", "對照：全市場合格股（不看產業位置），mom60 大先", ANY, "a"),
 ("U2", "對照：全市場 個股 mom60>20，mom60 大先", lambda r: r["mom"] > 20, "a"),
 ("U3", "對照：全市場 個股 stage up，mom60 大先", lambda r: r["sst"] == "up", "a"),
 ("U4", "對照：全市場 個股 stage up 且 mom60>20", lambda r: r["sst"] == "up" and r["mom"] > 20, "a"),
 ("U5", "對照：全市場合格股，mom60 小先", ANY, "e"),
]
if QUICK: CTRL = CTRL[:1]
for cg, nm, basef, v in CTRL: SIGS[(cg, v)] = build(UNIV_ROWS, lambda k: ALLCODES, lambda k, ym, o: True, basef, v, scope="univ")
P("流動性篩選（成員×月 累計，%d 檔 × %d 月）：%s" % (len(S.IND), len(S.YMS), "、".join("%s %d" % (k, v) for k, v in LSTAT.most_common())))

# ---------- 2. 訊號描述 ----------
P("")
P("=" * 130)
P("== 訊號清單（事件＝產業-月；訊號＝股票-日；n 都是筆數）==")
for sg, nm, ev, basef in SIGDEF:
    sa, nev, nev1 = SIGS[(sg, "a")]
    byy = collections.Counter(r["d"][:4] for r in sa); evy = collections.Counter()
    for (k, ym), o in IND_ROWS.items():
        if ev(k, ym, o): evy[AV[ym][:4]] += 1
    P("")
    P("-- %s %s" % (sg, nm))
    P("   事件 %d 個產業-月（有合格成員的 %d）；(a) 訊號 %d 筆、(b) %d、(c) %d、(d) %d、(e) %d；訊號日數 %d、一天訊號數中位 %s 最多 %s；個股 stage up 佔 %.1f%%、mom60>20 佔 %.1f%%、mom60 中位 %+.1f" % (
        nev, nev1, len(sa), len(SIGS[(sg, "b")][0]), len(SIGS[(sg, "c")][0]), len(SIGS[(sg, "d")][0]), len(SIGS[(sg, "e")][0]),
        len(set(r["d"] for r in sa)), statistics.median(collections.Counter(r["d"] for r in sa).values()) if sa else "-", max(collections.Counter(r["d"] for r in sa).values()) if sa else "-",
        100 * sum(1 for r in sa if r["sst"] == "up") / max(1, len(sa)), 100 * sum(1 for r in sa if r["mom"] > 20) / max(1, len(sa)), statistics.median([r["mom"] for r in sa]) if sa else float("nan")))
    P("   逐年 事件數／(a)訊號數：" + "  ".join("%s %d/%d" % (y[2:], evy.get(y, 0), byy.get(y, 0)) for y in YEARS))
    ci = collections.Counter(r["ind"] for r in sa)
    P("   產業別前 10（訊號數）：" + "、".join("%s %d" % (k, v) for k, v in ci.most_common(10)))
    if sg in ("S1", "S2"):
        evs = collections.defaultdict(list)
        for (k, ym), o in sorted(IND_ROWS.items(), key=lambda x: (x[0][0], x[0][1])):
            if ev(k, ym, o): evs[k].append(ym)
        P("   事件明細（產業：月份）：" + "；".join("%s：%s" % (k, " ".join(v)) for k, v in evs.items()))
for cg, nm, basef, v in CTRL:
    sa, nev, nev1 = SIGS[(cg, v)]
    P("-- %s %s：訊號 %d 筆、%d 個月" % (cg, nm, len(sa), nev1))

# ---------- 3. 事件統計 ----------
def m(L): return statistics.median(L) if L else float("nan")
def evt(rows, key):
    f = [s[key] for s in rows if s[key] is not None]
    if not f: return "n     0"
    h1 = [s[key] for s in rows if s[key] is not None and s["d"] < H2_START]; h2 = [s[key] for s in rows if s[key] is not None and s["d"] >= H2_START]
    se = statistics.pstdev(f) / math.sqrt(len(f)) if len(f) > 1 else float("nan")
    return "n %5d  中位 %+6.2f  平均 %+6.2f（±%.2f）  贏0050 %4.1f%%   前半中位 %+6.2f（n %4d） 後半 %+6.2f（n %4d）" % (len(f), m(f), statistics.mean(f), se, 100 * sum(1 for x in f if x > 0) / len(f), m(h1), len(h1), m(h2), len(h2))
def basket(rows, key):
    g = collections.defaultdict(list)
    for s in rows:
        if s[key] is not None: g[(s["ind"], s["d"])].append(s[key])
    f = [statistics.mean(v) for v in g.values()]
    if not f: return "n 0"
    return "事件籃 n %4d  中位 %+6.2f  平均 %+6.2f  贏0050 %4.1f%%" % (len(f), m(f), statistics.mean(f), 100 * sum(1 for x in f if x > 0) / len(f))
P("")
P("=" * 130)
P("== 事件統計：每筆訊號 買進日收盤 → 60 / 120 個交易日後收盤 的報酬 − 0050 含息（tr50）同期，點，未扣成本；n＝可算筆數（最後 60/120 日內的訊號算不出）；前半 d<%s、後半 d≥%s" % (H2_START, H2_START))
P("   「事件籃」＝同一產業-月的 (a) 訊號等權平均成一筆，n＝事件數")
for sg, nm, ev, basef in SIGDEF:
    P("")
    P("-- %s %s" % (sg, nm))
    for v in VARS:
        rows = SIGS[(sg, v)][0]
        P("   %-34s 60日 %s" % (VNAME[v][:34], evt(rows, "fx60")))
        P("   %-34s 120日 %s" % ("", evt(rows, "fx120")))
    P("   %-34s 60日 %s   120日 %s" % ("(a) 事件籃（每個產業-月一筆）", basket(SIGS[(sg, "a")][0], "fx60"), basket(SIGS[(sg, "a")][0], "fx120")))
P("")
P("-- 對照（不看產業位置）")
for cg, nm, basef, v in CTRL:
    rows = SIGS[(cg, v)][0]
    P("   %-34s 60日 %s" % (cg + " " + nm[3:30], evt(rows, "fx60")))
    P("   %-34s 120日 %s" % ("", evt(rows, "fx120")))
# 相對「同月全市場合格股中位」的超額（排除 0050 本身強弱的影響：問的是「從這個產業挑」有沒有比「隨便挑一檔」好）
UM = {}
for key in ("fx60", "fx120"):
    byd = collections.defaultdict(list)
    for x in SIGS[("U1", "a")][0]:
        if x[key] is not None: byd[x["d"]].append(x[key])
    UM[key] = {d: statistics.median(v) for d, v in byd.items()}
def rel(rows, key):
    f = [x[key] - UM[key][x["d"]] for x in rows if x[key] is not None and x["d"] in UM[key]]
    if not f: return "n     0"
    h1 = [x[key] - UM[key][x["d"]] for x in rows if x[key] is not None and x["d"] in UM[key] and x["d"] < H2_START]
    h2 = [x[key] - UM[key][x["d"]] for x in rows if x[key] is not None and x["d"] in UM[key] and x["d"] >= H2_START]
    return "n %5d  中位 %+6.2f  平均 %+6.2f（±%.2f）  贏同月全市場中位 %4.1f%%   前半中位 %+6.2f（n %4d） 後半 %+6.2f（n %4d）" % (len(f), m(f), statistics.mean(f), statistics.pstdev(f) / math.sqrt(len(f)), 100 * sum(1 for x in f if x > 0) / len(f), m(h1), len(h1), m(h2), len(h2))
P("")
P("== 事件統計 B：每筆訊號的 60/120 日報酬 − 同一天「全市場合格股（U1）」的中位數（點）；>0 ＝ 從這個產業挑比全市場隨便挑好；n＝筆數")
for sg, nm, ev, basef in SIGDEF:
    P("-- %s %s" % (sg, nm))
    for v in VARS:
        rows = SIGS[(sg, v)][0]
        P("   %-34s 60日 %s" % (VNAME[v][:34], rel(rows, "fx60")))
        P("   %-34s 120日 %s" % ("", rel(rows, "fx120")))
P("")
P("== 事件統計 C：(a) 版逐年（60 日超額 vs 0050 含息；n 中位 勝率%%；再附 vs 同月全市場中位 的中位）")
P("   %-6s %s" % ("", " ".join("%-22s" % y for y in YEARS)))
for sg, nm, ev, basef in SIGDEF:
    rows = SIGS[(sg, "a")][0]; cells = []
    for y in YEARS:
        f = [x["fx60"] for x in rows if x["fx60"] is not None and x["d"][:4] == y]
        g = [x["fx60"] - UM["fx60"][x["d"]] for x in rows if x["fx60"] is not None and x["d"][:4] == y and x["d"] in UM["fx60"]]
        cells.append("%-22s" % ("—" if not f else "n%4d %+5.1f %3.0f%% r%+5.1f" % (len(f), m(f), 100 * sum(1 for x in f if x > 0) / len(f), m(g))))
    P("   %-6s %s" % (sg, " ".join(cells)))
rows = SIGS[("U1", "a")][0]; cells = []
for y in YEARS:
    f = [x["fx60"] for x in rows if x["fx60"] is not None and x["d"][:4] == y]
    cells.append("%-22s" % ("—" if not f else "n%4d %+5.1f %3.0f%%" % (len(f), m(f), 100 * sum(1 for x in f if x > 0) / len(f))))
P("   %-6s %s" % ("U1", " ".join(cells)))

# ---------- 4. 帳戶模擬 ----------
def evaluate(Sset, hold):
    global HOLD
    HOLD = hold
    det = run(Sset); rs = sorted(run(Sset, seed=k)["cagr"] for k in range(NSEED))
    h1 = run(Sset, end=H1_END)["cagr"]; h2 = run(Sset, start=H2_START)["cagr"]
    beat = sum(1 for y in YEARS if det["yr"].get(y, 0) > B50["yr"][y])
    return dict(cagr=det["cagr"], mdd=det["mdd"], n=det["n"], avg=det["avg"], win=det["win"], rmed=rs[NSEED // 2], rlo=rs[0], rhi=rs[-1], h1=h1, h2=h2, beat=beat, yr=det["yr"], nsig=len(Sset), hold=hold)
def check(r):
    f = []
    if not r["cagr"] > B50["cagr"]: f.append("年化 %.1f ≤ 0050 %.1f" % (r["cagr"], B50["cagr"]))
    if not r["rlo"] > B50["cagr"]: f.append("隨機最低 %.1f ≤ %.1f" % (r["rlo"], B50["cagr"]))
    if not (r["h1"] > B50H1 and r["h2"] > B50H2): f.append("前/後半 %.1f/%.1f vs 0050 %.1f/%.1f" % (r["h1"], r["h2"], B50H1, B50H2))
    if not r["beat"] >= 7: f.append("贏0050 %d/%d 年" % (r["beat"], len(YEARS)))
    if not r["mdd"] >= -40: f.append("回撤 %.1f" % r["mdd"])
    return (not f), f
def fmt(lab, r, extra=""):
    ok, f = check(r)
    return "  %-36s 抱%3d  年化 %5.1f%% 回撤 %5.1f%% 筆數 %3d 每筆 %+5.2f%% 勝率 %2.0f%%  隨機%d次中位 %5.1f%%（%5.1f～%5.1f） 前半 %5.1f%% 後半 %5.1f%%  贏0050 %2d/%d  訊號 %5d%s  %s" % (
        lab[:36], r["hold"], r["cagr"], r["mdd"], r["n"], r["avg"], r["win"], NSEED, r["rmed"], r["rlo"], r["rhi"], r["h1"], r["h2"], r["beat"], len(YEARS), r["nsig"], extra, "穩" if ok else "不穩（" + "；".join(f) + "）")
RES = collections.OrderedDict()
P("")
P("=" * 130)
P("== 帳戶模擬（10 槽 × 10%%、閒錢 0050 含息、成本 0.47%%；%s～%s）==" % ("2016-06-01", cal[-1]))
P("   年化／回撤／筆數／每筆／勝率／前後半／贏0050＝不給 seed 的引擎預設排序（同日照 −r60x＝個股 mom60 大先；(e) 版 r60x 取負號＝mom60 小先）；")
P("   隨機 %d 次＝引擎 run(S, seed=k) 同日整天打亂（跟排序無關，所以 (a) 與 (e) 的隨機數字相同），報中位（最低～最高）；前半 end %s／後半 start %s；贏0050＝逐年贏 0050 含息的年數（含 2016 下半、2026 前 10 月）" % (NSEED, H1_END, H2_START))
P("   「穩」門檻：年化 > 0050 %.1f%%、隨機 %d 次最低 > %.1f%%、前半 > %.1f%% 且 後半 > %.1f%%、贏 0050 年數 ≥ 7/11、回撤 ≥ −40%%" % (B50["cagr"], NSEED, B50["cagr"], B50H1, B50H2))
P("   S5 自帶「個股 stage up」所以 S5(b)≡S5(a)；S6 自帶「mom60>20」所以 S6(c)≡S6(a)")
HOLDS = [60, 120]
for sg, nm, ev, basef in SIGDEF:
    P("")
    P("-- %s %s（事件 %d）" % (sg, nm, SIGS[(sg, "a")][1]))
    for hold in HOLDS:
        for v in VARS:
            Sset = SIGS[(sg, v)][0]
            if len(Sset) < 10: P("  %-36s 抱%3d  訊號 %d 筆太少，不跑" % (VNAME[v], hold, len(Sset))); continue
            r = evaluate(Sset, hold); RES[(sg, v, hold)] = r
            P(fmt(VNAME[v], r))
    P("  逐年（抱 60，%%）：%s" % " ".join("%6s" % y[2:] for y in YEARS))
    P("  %-36s %s" % ("0050 含息", " ".join("%+6.0f" % B50["yr"][y] for y in YEARS)))
    for v in VARS:
        if (sg, v, 60) in RES: P("  %-36s %s   贏0050 %d/%d" % (VNAME[v], " ".join("%+6.0f" % RES[(sg, v, 60)]["yr"].get(y, 0) for y in YEARS), RES[(sg, v, 60)]["beat"], len(YEARS)))
P("")
P("-- 對照：不看產業位置（全市場）")
for cg, nm, basef, v in CTRL:
    for hold in HOLDS:
        r = evaluate(SIGS[(cg, v)][0], hold); RES[(cg, v, hold)] = r
        P(fmt(cg + " " + nm[3:], r))
P("  逐年（抱 60，%%）：%s" % " ".join("%6s" % y[2:] for y in YEARS))
P("  %-36s %s" % ("0050 含息", " ".join("%+6.0f" % B50["yr"][y] for y in YEARS)))
for cg, nm, basef, v in CTRL:
    if (cg, v, 60) in RES: P("  %-36s %s   贏0050 %d/%d" % (cg + " " + nm[3:], " ".join("%+6.0f" % RES[(cg, v, 60)]["yr"].get(y, 0) for y in YEARS), RES[(cg, v, 60)]["beat"], len(YEARS)))

# ---------- 5. 相鄰參數：S1 用原始 rev3 / gm_d 重算 price 門檻 ----------
P("")
P("=" * 130)
P("== 相鄰參數：S1 new_price 的 price 門檻重算（price＝rev3 ≥ R 且 gm_d ≥ G；new_price＝本月 price、3 個月前有資料且不是 price）；(a) 版、抱 60；年化＝引擎預設排序，括號＝隨機 %d 次中位（最低～最高）；事件＝產業-月；n＝交易筆數" % NSEED)
def price_rg(o, R, G): return o["rev3"] >= R and o["gm_d"] is not None and o["gm_d"] >= G
def ev_new(R, G):
    def f(k, ym, o):
        p = IND_ROWS.get((k, ymp(ym, 3)))
        return price_rg(o, R, G) and p is not None and not price_rg(p, R, G)
    return f
RS = [5, 10, 15] if not QUICK else [10]; GS = [0.5, 1.0, 1.5] if not QUICK else [1.0]
ADJ = {}
for R in RS:
    for G in GS:
        sa, nev, nev1 = build(IND_ROWS, lambda k: IND_MEM[k], ev_new(R, G), ANY, "a")
        if R == 10 and G == 1.0:
            base = SIGS[("S1", "a")][0]
            same = set((r["code"], r["d"]) for r in sa) == set((r["code"], r["d"]) for r in base)
            P("   自我檢查：(R=10, G=1.0) 重算的 new_price 訊號 %d 筆 vs stage_data 的 S1(a) %d 筆，集合相同＝%s" % (len(sa), len(base), same))
        if len(sa) < 10: ADJ[(R, G)] = None; P("   R=%d G=%.1f：事件 %d、訊號 %d 筆太少" % (R, G, nev, len(sa))); continue
        r = evaluate(sa, 60); r["nev"] = nev; ADJ[(R, G)] = r
P("   年化矩陣（列 rev3 ≥ R，欄 gm_d ≥ G）：")
P("   %-10s %s" % ("", " | ".join("%-52s" % ("gm_d ≥ %.1f" % G) for G in GS)))
for R in RS:
    cells = []
    for G in GS:
        r = ADJ.get((R, G))
        cells.append("%-52s" % ("—" if not r else "年化 %5.1f%%（隨機 %5.1f～%5.1f） n %3d 事件 %3d 訊號 %4d 回撤 %5.1f%% 贏 %d/11" % (r["cagr"], r["rlo"], r["rhi"], r["n"], r["nev"], r["nsig"], r["mdd"], r["beat"])))
    P("   rev3 ≥ %-3d %s" % (R, " | ".join(cells)))
for (R, G), r in ADJ.items():
    if r: P("   " + fmt("S1(a) R=%d G=%.1f" % (R, G), r, "（事件 %d）" % r["nev"]))

# ---------- 6. 族群版（groups.csv，事後之見）----------
P("")
P("=" * 130)
P("== 族群版（S.D['grp']，使用者今天定的主題族群、成員今天定、成員 ≥ 3 檔 → 有事後之見，只當參考）：S1 / S2 的 (a) 版；同一股在多個族群時同日只算一筆")
GRES = {}
for sg, nm, ev in (("S1", "族群 new_price", lambda k, ym, o: bool(o["new_price"])), ("S2", "族群剛進入成長期（price/vol/vol?，上月 down/flat）", lambda k, ym, o: o["stage"] in PV and o["prev_stage"] in ("down", "flat"))):
    sa, nev, nev1 = build(GRP_ROWS, lambda k: GRP_MEM[k], ev, ANY, "a", dedupe=True, scope="grp")
    cg = collections.Counter(r["ind"] for r in sa)
    P("-- G%s %s：事件 %d 個族群-月（有合格成員 %d）、訊號 %d 筆；族群前 8：%s" % (sg[1], nm, nev, nev1, len(sa), "、".join("%s %d" % (k, v) for k, v in cg.most_common(8))))
    P("   60日 %s" % evt(sa, "fx60")); P("   120日 %s" % evt(sa, "fx120"))
    for hold in HOLDS:
        if len(sa) < 10: P("   訊號太少不跑"); continue
        r = evaluate(sa, hold); GRES[(sg, hold)] = r; P(fmt("G%s %s（事後之見）" % (sg[1], nm), r))

# ---------- 7. 總表 ----------
P("")
P("=" * 130)
P("== 總表（抱 60／120；年化＝引擎預設排序 mom60 大先；隨機＝同日整天打亂 %d 次中位(最低～最高)；n＝交易筆數；穩＝年化>%.1f、隨機最低>%.1f、前半>%.1f 且後半>%.1f、贏0050≥7/11、回撤≥−40）" % (NSEED, B50["cagr"], B50["cagr"], B50H1, B50H2))
T = ["%-40s|%4s|%6s|%6s|%4s|%7s|%4s|%-22s|%-11s|%-5s|%6s|%s" % ("訊號／挑法", "抱", "年化", "回撤", "n", "每筆", "勝率", "隨機30 中位(低～高)", "前半/後半", "贏0050", "訊號數", "判定")]
T.append("%-40s|%4s|%5.1f%%|%5.1f%%|%4s|%7s|%4s|%-22s|%5.1f/%5.1f|%-5s|%6s|%s" % ("0050 含息（基準）", "", B50["cagr"], B50["mdd"], "", "", "", "", B50H1, B50H2, "", "", "基準"))
def trow(lab, r):
    ok, f = check(r)
    return "%-40s|%4d|%5.1f%%|%5.1f%%|%4d|%+6.2f%%|%3.0f%%|%5.1f%%（%5.1f～%5.1f）|%5.1f/%5.1f|%2d/%d|%6d|%s" % (lab[:40], r["hold"], r["cagr"], r["mdd"], r["n"], r["avg"], r["win"], r["rmed"], r["rlo"], r["rhi"], r["h1"], r["h2"], r["beat"], len(YEARS), r["nsig"], "穩" if ok else "不穩：" + "；".join(f))
for sg, nm, ev, basef in SIGDEF:
    T.append("-- %s %s --" % (sg, nm))
    for hold in HOLDS:
        for v in VARS:
            if (sg, v, hold) in RES: T.append(trow("%s %s" % (sg, VNAME[v]), RES[(sg, v, hold)]))
T.append("-- 對照：不看產業位置 --")
for cg, nm, basef, v in CTRL:
    for hold in HOLDS:
        if (cg, v, hold) in RES: T.append(trow(cg + " " + nm[3:], RES[(cg, v, hold)]))
T.append("-- 相鄰參數 S1(a) 抱 60 --")
for (R, G), r in ADJ.items():
    if r: T.append(trow("S1(a) rev3≥%d gm_d≥%.1f（事件 %d）" % (R, G, r["nev"]), r))
T.append("-- 族群版（事後之見）--")
for (sg, hold), r in GRES.items(): T.append(trow("G%s 族群 %s (a)" % (sg[1], "new_price" if sg == "S1" else "剛進入成長期"), r))
for t in T: P(t)
open("stagetest/c_cycle_table.txt", "w").write("\n".join(T) + "\n")
nstable = sum(1 for r in list(RES.values()) + [x for x in ADJ.values() if x] + list(GRES.values()) if check(r)[0])
P("")
P("穩的組合數：%d / %d（含對照、相鄰、族群）" % (nstable, len(RES) + sum(1 for x in ADJ.values() if x) + len(GRES)))
J = {"%s|%s|%d" % k: {kk: vv for kk, vv in r.items() if kk != "yr"} for k, r in RES.items()}
J.update({"ADJ|R%d|G%.1f" % k: ({kk: vv for kk, vv in r.items() if kk != "yr"} if r else None) for k, r in ADJ.items()})
J.update({"GRP|%s|%d" % k: {kk: vv for kk, vv in r.items() if kk != "yr"} for k, r in GRES.items()})
J["base"] = dict(cagr=B50["cagr"], mdd=B50["mdd"], h1=B50H1, h2=B50H2, yr=B50["yr"])
json.dump(J, open("stagetest/c_cycle_res.json", "w"), ensure_ascii=False, indent=1)
P("（耗時 %.0f 秒；NSEED=%d QUICK=%s）" % (time.time() - T0, NSEED, QUICK))
OUT.close()
