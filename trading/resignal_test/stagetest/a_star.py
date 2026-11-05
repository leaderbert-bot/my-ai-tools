"""任務 A：把「產業循環位置」（stage_lib / stage_data.pkl）當 ★ 候選的排序鍵與濾網，看能不能穩定贏現行規則
（現行＝當天創新高優先、同級 20 日均量 ≥ 2000 張先）。
用法（在 scratchpad 目錄）：python3 stagetest/a_star.py 0.95 ；python3 stagetest/a_star.py 0.99 ；python3 stagetest/a_star.py merge
引擎：star_rank.py（6 槽、抱 20 天收盤賣、每天最多買 3 檔 cap=3、成本 0.47%），重用方式照 star_rank_roic.py。
排序規則：同分隨機 30 個 seed（1000+k，先打亂再排序），報中位／最低／最高；對照＝純隨機 100 次中位（引擎寫法 sorted[50]）。
前半 end=2021-12-31、後半 start=2022-01-03，各 30 seed 取中位。逐年用 30 seed 逐年中位 vs 0050 含息（tr50.pkl）。
回撤／筆數／勝率／每筆 皆為 30 seed 的中位數。"""
import sys, os, time, collections, statistics, pickle, random, bisect, json
SP = "/tmp/claude-0/-home-user-my-ai-tools/bb9482f7-4c31-5f24-a06a-81bc958a76a4/scratchpad"
sys.path.insert(0, SP); os.chdir(SP)
ARG = sys.argv[1] if len(sys.argv) > 1 else "0.95"
NSEED = int(os.environ.get("NSEED", 30)); NRAND = int(os.environ.get("NRAND", 100)); CAP = 3   # 試跑時用環境變數縮小
H1_END = "2021-12-31"; H2_START = "2022-01-03"
TAGS = ("095", "099")
ST_ORDER = ("price", "vol", "vol?", "flat", "down", "na")
SST_ORDER = ("up", "vol", "vol?", "flat", "down", "na")


def stable_check(r, cur):
    """單一設定內的三個條件：中位 ≥ 現行 +3、≥25/30 贏純隨機中位、前後半都不低於現行"""
    d = r["cagr"] - cur["cagr"]
    return dict(d=d, c1=d >= 3.0, c2=r["beat"] >= 25, c3=(r["h1"] >= cur["h1"] and r["h2"] >= cur["h2"]),
                dh1=r["h1"] - cur["h1"], dh2=r["h2"] - cur["h2"])


def merge():
    R = {t: json.load(open("stagetest/a_star_res_%s.json" % t)) for t in TAGS}
    lines = []
    def W(s=""): lines.append(s)
    W("任務 A：產業循環位置當 ★ 候選排序鍵／濾網（10 年回測，2017-08-23～2026-10-30）")
    W("引擎 star_rank.py：6 槽、抱 20 天、每天最多買 3 檔；排序規則 30 seed 同分隨機（1000+k）；對照純隨機 100 次中位；前半 end 2021-12-31／後半 start 2022-01-03")
    W("「穩」門檻：兩個設定（phi≥0.95、phi≥0.99）都比現行中位高 ≥ 3 點、30 次裡 ≥ 25 次贏純隨機中位、前後半年化都不低於現行。")
    W()
    for t in TAGS:
        W(open("stagetest/a_star_out_%s.txt" % t).read().rstrip()); W()
    W("=" * 110)
    W("== 跨兩設定「穩」判定（Δ＝與現行中位的差，點；贏隨機＝30 seed 裡贏純隨機 100 次中位的次數；前半/後半＝30 seed 中位年化）")
    W("%-34s | %-38s | %-38s | %s" % ("規則", "phi≥0.95：中位(Δ) 贏隨機 前半/後半 筆數", "phi≥0.99：中位(Δ) 贏隨機 前半/後半 筆數", "判定"))
    table = []
    for sect in ("rank", "filter"):
        W("-- %s --" % ("排序規則" if sect == "rank" else "濾網（搭配現行排序）"))
        cur = {t: R[t][sect][0] for t in TAGS}
        for i, r0 in enumerate(R["095"][sect]):
            nm = r0["name"]
            rr = {t: R[t][sect][i] for t in TAGS}
            assert all(rr[t]["name"] == nm for t in TAGS), nm
            chk = {t: stable_check(rr[t], cur[t]) for t in TAGS}
            cells = []
            for t in TAGS:
                r = rr[t]
                cells.append("%5.1f%%(%+5.1f) %2d/30 %5.1f/%5.1f n=%d" % (r["cagr"], chk[t]["d"], r["beat"], r["h1"], r["h2"], r["n"]))
            ok_all = all(chk[t]["c1"] and chk[t]["c2"] and chk[t]["c3"] for t in TAGS)
            if i == 0: verdict = "（基準）"
            elif ok_all: verdict = "穩：三條件兩設定都過"
            else:
                fails = []
                for t in TAGS:
                    f = []
                    if not chk[t]["c1"]: f.append("Δ<3")
                    if not chk[t]["c2"]: f.append("贏隨機<25")
                    if not chk[t]["c3"]: f.append("前/後半變差(%+.1f/%+.1f)" % (chk[t]["dh1"], chk[t]["dh2"]))
                    if f: fails.append("%s:%s" % (t, ",".join(f)))
                verdict = "不穩（" + "；".join(fails) + "）"
            W("%-34s | %s | %s | %s" % (nm, cells[0], cells[1], verdict))
            table.append((sect, nm, rr, chk, verdict))
        W()
    # 隨機基準
    W("純隨機 100 次中位：phi≥0.95 %.1f%%（%.1f～%.1f）、phi≥0.99 %.1f%%（%.1f～%.1f）；0050 含息同期年化 %.1f%%（2017-08-23～2026-10-30）" % (
        R["095"]["rand"]["med"], R["095"]["rand"]["lo"], R["095"]["rand"]["hi"], R["099"]["rand"]["med"], R["099"]["rand"]["lo"], R["099"]["rand"]["hi"], R["095"]["cagr50"]))
    open("stagetest/a_star_out.txt", "w").write("\n".join(lines) + "\n")
    # 給回傳用的精簡表
    T = []
    T.append("%-30s|%-28s|%-28s|%s" % ("規則（n=30 seed）", "0.95 中位(Δ現行) 贏隨機 前/後", "0.99 中位(Δ現行) 贏隨機 前/後", "筆數 .95/.99  判定"))
    for sect, nm, rr, chk, verdict in table:
        T.append("%-30s|%5.1f%%(%+5.1f) %2d/30 %4.1f/%4.1f|%5.1f%%(%+5.1f) %2d/30 %4.1f/%4.1f|%d/%d %s" % (
            nm[:30], rr["095"]["cagr"], chk["095"]["d"], rr["095"]["beat"], rr["095"]["h1"], rr["095"]["h2"],
            rr["099"]["cagr"], chk["099"]["d"], rr["099"]["beat"], rr["099"]["h1"], rr["099"]["h2"], rr["095"]["n"], rr["099"]["n"], verdict))
    open("stagetest/a_star_table.txt", "w").write("\n".join(T) + "\n")
    print("\n".join(lines[-40:]))


if ARG == "merge":
    merge(); sys.exit(0)

PHI = ARG
sys.argv = ["star_rank.py", "cands.pkl", PHI]
exec(open("star_rank.py").read().split("def main():")[0])
import stage_lib as S
tr50, _divs = pickle.load(open("tr50.pkl", "rb"))
TAG = PHI.replace(".", "")
OUT = open("stagetest/a_star_out_%s.txt" % TAG, "w")
def P(*a):
    line = " ".join(str(x) for x in a); print(line, flush=True); OUT.write(line + "\n"); OUT.flush()
T0 = time.time()

# ---------- 1. 附上產業／族群／個股位置 ----------
for c in C:
    s = S.ind_stage(c["code"], c["d"])
    c["ist"] = s["stage"] if s else "na"; c["inew"] = bool(s and s["new_price"])
    c["irev3"] = s["rev3"] if s else None; c["ibr"] = s["breadth"] if s else None
    c["imom"] = s["mom60"] if s else None; c["iprev"] = s["prev_stage"] if s else None; c["igm"] = s["gm_d"] if s else None
    g = S.grp_stages(c["code"], c["d"]); c["ingrp"] = 1 if g else 0
    c["gprice"] = 1 if any(x["stage"] == "price" for _, x in g) else 0
    st = S.stock_stage(c["code"], c["d"]); c["sst"] = st["stage"] if st else "na"
N = len(C)
ci = collections.Counter(c["ist"] for c in C); cs_ = collections.Counter(c["sst"] for c in C)
P("=" * 110)
P("== phi ≥ %s：候選 %d 筆（%s～%s，%d 天有候選）；一天候選數中位 %d、最多 %d" % (PHI, N, days[0], days[-1], len(days), statistics.median(len(v) for v in byday.values()), max(len(v) for v in byday.values())))
P("產業位置覆蓋 %d/%d（%.1f%%；na＝該月產業成員 <6 檔或查不到產業）：" % (N - ci["na"], N, 100 * (N - ci["na"]) / N) + "  ".join("%s %d（%.1f%%）" % (k, ci[k], 100 * ci[k] / N) for k in ST_ORDER))
P("  產業 new_price（剛進入價漲期，3 個月前不是）%d 筆；上月產業位置 prev_stage 有值 %d 筆" % (sum(c["inew"] for c in C), sum(1 for c in C if c["iprev"])))
P("個股位置覆蓋 %d/%d（%.1f%%）：" % (N - cs_["na"], N, 100 * (N - cs_["na"]) / N) + "  ".join("%s %d（%.1f%%）" % (k, cs_[k], 100 * cs_[k] / N) for k in SST_ORDER))
P("族群（groups.csv，成員是今天定的，有事後之見，只當參考）：在族群表 %d 筆（%.1f%%），任一族群 price %d 筆（%.1f%%）" % (sum(c["ingrp"] for c in C), 100 * sum(c["ingrp"] for c in C) / N, sum(c["gprice"] for c in C), 100 * sum(c["gprice"] for c in C) / N))
P("逐年候選數與產業位置分佔（price/vol/vol?/flat/down/na）：")
for y in sorted(set(c["d"][:4] for c in C)):
    cy = [c for c in C if c["d"][:4] == y]; cc = collections.Counter(c["ist"] for c in cy)
    P("  %s n=%4d  " % (y, len(cy)) + " ".join("%s %3d" % (k[:4], cc[k]) for k in ST_ORDER) + "   個股 up %d" % sum(1 for c in cy if c["sst"] == "up"))

# ---------- 1b. 事件統計：每筆候選買進後 20 日報酬 − 0050 含息同期（點）；同一股多天出現會重複計 ----------
def fwd_x(c, k=20):
    i = idx[c["d"]]
    if i + k >= len(cal): return None
    p1 = close_near(c["code"], cal[i + k])
    if not p1 or not tr50[i] or not tr50[i + k]: return None
    return (p1 / c["px"] - 1) * 100 - (tr50[i + k] / tr50[i] - 1) * 100
for c in C: c["fx20"] = fwd_x(c)
def evt(rows):
    xs = [c["fx20"] for c in rows if c["fx20"] is not None]
    if not xs: return "n=0"
    return "n=%5d 平均 %+5.2f 中位 %+5.2f 勝率 %4.1f%%" % (len(xs), statistics.mean(xs), statistics.median(xs), 100 * sum(1 for x in xs if x > 0) / len(xs))
P("事件統計（買進後 20 日報酬 − 0050 含息同期，點，未扣成本；n＝候選筆數）：")
P("  全部候選                 " + evt(C))
for k in ST_ORDER: P("  產業 %-6s              " % k + evt([c for c in C if c["ist"] == k]))
P("  產業 new_price           " + evt([c for c in C if c["inew"]]))
for k in SST_ORDER: P("  個股 %-6s              " % k + evt([c for c in C if c["sst"] == k]))
P("  族群任一 price           " + evt([c for c in C if c["gprice"]]))
P("  在族群表但沒 price       " + evt([c for c in C if c["ingrp"] and not c["gprice"]]))
P("  產業 price 或 個股 up    " + evt([c for c in C if c["ist"] == "price" or c["sst"] == "up"]))
P("  創新高 phi=1             " + evt([c for c in C if c["phi"] >= 0.9999]))
P("  非創新高                 " + evt([c for c in C if c["phi"] < 0.9999]))

# ---------- 2. 工具 ----------
BASE = list(C); D0 = days[0]
def setC(newC):
    global C, byday, days
    C = newC; byday = collections.defaultdict(list)
    for c in C: byday[c["d"]].append(c)
    days = sorted(byday)
def med(L):
    L = sorted(L); return L[len(L) // 2]          # 引擎慣例（100 次取 [50]、30 次取 [15]）
eq0, _ = run(seed=0, cap=CAP, start=D0)
def yr50(eq):
    base = tr50[idx[eq[0][0]]]; last = {}
    for d, e in eq: last[d[:4]] = tr50[idx[d]]
    o = {}; b = base
    for y in sorted(last): o[y] = (last[y] / b - 1) * 100; b = last[y]
    return o
Y50 = yr50(eq0); YEARS = sorted(Y50)
i0, i1 = idx[eq0[0][0]], idx[eq0[-1][0]]
CAGR50 = ((tr50[i1] / tr50[i0]) ** (245.0 / (i1 - i0)) - 1) * 100
P("0050 含息同期（%s～%s）年化 %.1f%%；逐年：" % (eq0[0][0], eq0[-1][0], CAGR50) + " ".join("%s %+.0f" % (y[2:], Y50[y]) for y in YEARS))

def rand_base(n=NRAND):
    rs = [stats(*run(seed=s, cap=CAP, start=D0)) for s in range(n)]
    cg = sorted(x["cagr"] for x in rs)
    ymed = {y: statistics.median([x["yr"].get(y, 0) for x in rs]) for y in YEARS}
    return dict(med=cg[len(cg) // 2], lo=cg[0], hi=cg[-1], n=med([x["n"] for x in rs]), mdd=med([x["mdd"] for x in rs]), ymed=ymed, cs=cg)

def evaluate(kf, ref):
    full = [stats(*run(keyfn=kf, seed=1000 + k, cap=CAP, start=D0)) for k in range(NSEED)]
    h1 = [stats(*run(keyfn=kf, seed=1000 + k, cap=CAP, start=D0, end=H1_END))["cagr"] for k in range(NSEED)]
    h2 = [stats(*run(keyfn=kf, seed=1000 + k, cap=CAP, start=H2_START))["cagr"] for k in range(NSEED)]
    cs = sorted(x["cagr"] for x in full)
    ymed = {y: statistics.median([x["yr"].get(y, 0) for x in full]) for y in YEARS}
    return dict(cagr=cs[NSEED // 2], lo=cs[0], hi=cs[-1], beat=sum(1 for x in cs if x > ref), cs=cs,
                mdd=med([x["mdd"] for x in full]), n=med([x["n"] for x in full]), win=med([x["win"] for x in full]), avg=med([x["avg"] for x in full]),
                h1=med(h1), h2=med(h2), h1lo=min(h1), h1hi=max(h1), h2lo=min(h2), h2hi=max(h2),
                ymed=ymed, beat50=sum(1 for y in YEARS if ymed[y] > Y50[y]), ny=len(YEARS))
def fmt(nm, r, extra=""):
    return "  %-36s 中位 %5.1f%%（%5.1f～%5.1f） 贏隨機 %2d/%d  回撤 %5.1f%% 筆數 %3d 勝率 %2.0f%% 每筆 %+5.2f%%  前半 %5.1f%% 後半 %5.1f%%  贏0050 %d/%d 年%s" % (
        nm, r["cagr"], r["lo"], r["hi"], r["beat"], NSEED, r["mdd"], r["n"], r["win"], r["avg"], r["h1"], r["h2"], r["beat50"], r["ny"], extra)

RES = dict(phi=PHI, n_cands=N, cagr50=CAGR50, y50=Y50)
# ---------- 2a. 純隨機 ----------
RB = rand_base(); rand_med = RB["med"]
P("純隨機 %d 次（cap=3）：年化中位 %.1f%%（最低 %.1f、最高 %.1f）、回撤中位 %.1f%%、筆數中位 %d；逐年中位贏 0050 %d/%d 年" % (
    NRAND, RB["med"], RB["lo"], RB["hi"], RB["mdd"], RB["n"], sum(1 for y in YEARS if RB["ymed"][y] > Y50[y]), len(YEARS)))
RES["rand"] = dict(med=RB["med"], lo=RB["lo"], hi=RB["hi"], n=RB["n"], mdd=RB["mdd"])

# ---------- 2b. 排序規則 ----------
cur = lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1)
PV = ("price", "vol", "vol?")
def pr(c, r, g): return c["irev3"] is not None and c["igm"] is not None and c["irev3"] >= r and c["igm"] >= g
RULES = [
 ("現行：創新高優先，同級均量≥2000先", lambda c: cur(c)),
 ("產業 price 優先 → 再現行", lambda c: (0 if c["ist"] == "price" else 1,) + cur(c)),
 ("產業 price/vol/vol? 優先 → 再現行", lambda c: (0 if c["ist"] in PV else 1,) + cur(c)),
 ("產業 new_price 優先 → 再現行", lambda c: (0 if c["inew"] else 1,) + cur(c)),
 ("產業 rev3 大先", lambda c: (-(c["irev3"] if c["irev3"] is not None else -999),)),
 ("產業 breadth 大先", lambda c: (-(c["ibr"] if c["ibr"] is not None else -999),)),
 ("產業 mom60 大先", lambda c: (-(c["imom"] if c["imom"] is not None else -999),)),
 ("現行 → 第三鍵產業 price", lambda c: cur(c) + (0 if c["ist"] == "price" else 1,)),
 ("個股 up 優先 → 再現行", lambda c: (0 if c["sst"] == "up" else 1,) + cur(c)),
 ("族群 price 優先 → 再現行（事後之見）", lambda c: (0 if c["gprice"] else 1,) + cur(c)),
 ("對照：產業 down 優先 → 再現行", lambda c: (0 if c["ist"] == "down" else 1,) + cur(c)),
 ("對照：產業 mom60 小先", lambda c: ((c["imom"] if c["imom"] is not None else 999),)),
 ("對照：代號小先", lambda c: (c["code"],)),
 ("相鄰門檻：rev3≥5 且 gm_d≥0.5 優先 → 現行", lambda c: (0 if pr(c, 5, 0.5) else 1,) + cur(c)),
 ("相鄰門檻：rev3≥15 且 gm_d≥1.5 優先 → 現行", lambda c: (0 if pr(c, 15, 1.5) else 1,) + cur(c)),
 ("相鄰門檻：rev3≥10 且 gm_d≥0 優先 → 現行", lambda c: (0 if pr(c, 10, 0) else 1,) + cur(c)),
]
P("")
P("== 排序規則（同分隨機 30 seed；回撤／筆數／勝率／每筆／前後半＝30 seed 中位；贏隨機＝贏純隨機 100 次中位 %.1f%% 的次數；贏0050＝逐年中位贏 0050 含息的年數）" % rand_med)
RES["rank"] = []
for nm, kf in RULES:
    r = evaluate(kf, rand_med); r["name"] = nm
    if nm.startswith("相鄰門檻"): r["n_first"] = sum(1 for c in C if kf(c)[0] == 0)
    RES["rank"].append(r)
    P(fmt(nm, r, "  [第一鍵為 0 的候選 %d 筆]" % r["n_first"] if "n_first" in r else ""))
cur_r = RES["rank"][0]
P("  逐年（30 seed 逐年中位，%）：" + " ".join("%6s" % y[2:] for y in YEARS))
P("  %-36s" % "0050 含息" + " ".join("%+6.0f" % Y50[y] for y in YEARS))
P("  %-36s" % "純隨機中位" + " ".join("%+6.0f" % RB["ymed"][y] for y in YEARS))
for r in RES["rank"]:
    P("  %-36s" % r["name"] + " ".join("%+6.0f" % r["ymed"][y] for y in YEARS) + "   贏0050 %d/%d" % (r["beat50"], r["ny"]))
P("  本設定內三條件（Δ現行中位≥3、贏隨機≥25/30、前後半不低於現行）：")
for r in RES["rank"][1:]:
    k = stable_check(r, cur_r)
    P("    %-36s Δ%+5.1f %s  贏隨機 %2d %s  前半Δ%+5.1f 後半Δ%+5.1f %s" % (r["name"], k["d"], "過" if k["c1"] else "✗", r["beat"], "過" if k["c2"] else "✗", k["dh1"], k["dh2"], "過" if k["c3"] else "✗"))

# ---------- 3. 濾網（搭配現行排序） ----------
FILTERS = [
 ("全部候選（現行，基準）", lambda c: True),
 ("排除產業 down", lambda c: c["ist"] != "down"),
 ("只買產業 price/vol/vol?", lambda c: c["ist"] in PV),
 ("只買產業 price", lambda c: c["ist"] == "price"),
 ("排除個股 down", lambda c: c["sst"] != "down"),
 ("只買個股 up", lambda c: c["sst"] == "up"),
 ("只買「產業 price 或個股 up」", lambda c: c["ist"] == "price" or c["sst"] == "up"),
 ("對照：只買產業 down", lambda c: c["ist"] == "down"),
]
P("")
P("== 濾網（直接刪候選，再用現行排序 30 seed）：報候選數、交易數變化；贏隨機＝贏「不濾」純隨機中位 %.1f%% 的次數；另報濾後純隨機 100 次中位與贏它的次數" % rand_med)
RES["filter"] = []
base_n = None
for nm, flt in FILTERS:
    setC([c for c in BASE if flt(c)])
    fr = rand_base()
    r = evaluate(cur, rand_med); r["name"] = nm; r["n_cands"] = len(C); r["frand_med"] = fr["med"]; r["frand_lo"] = fr["lo"]; r["frand_hi"] = fr["hi"]
    r["beat_f"] = sum(1 for x in r["cs"] if x > fr["med"])
    if base_n is None: base_n = r["n"]
    r["dn"] = r["n"] - base_n
    RES["filter"].append(r)
    P(fmt(nm, r, "  [候選 %d 筆（%.0f%%），交易數 %+d；濾後純隨機中位 %.1f%%（%.1f～%.1f），贏它 %d/%d]" % (len(C), 100 * len(C) / N, r["dn"], fr["med"], fr["lo"], fr["hi"], r["beat_f"], NSEED)))
setC(BASE)
P("  逐年（30 seed 逐年中位，%）：" + " ".join("%6s" % y[2:] for y in YEARS))
P("  %-36s" % "0050 含息" + " ".join("%+6.0f" % Y50[y] for y in YEARS))
for r in RES["filter"]:
    P("  %-36s" % r["name"] + " ".join("%+6.0f" % r["ymed"][y] for y in YEARS) + "   贏0050 %d/%d" % (r["beat50"], r["ny"]))
cur_f = RES["filter"][0]
P("  本設定內三條件（Δ現行(不濾)中位≥3、贏不濾純隨機≥25/30、前後半不低於現行）：")
for r in RES["filter"][1:]:
    k = stable_check(r, cur_f)
    P("    %-36s Δ%+5.1f %s  贏隨機 %2d %s  前半Δ%+5.1f 後半Δ%+5.1f %s" % (r["name"], k["d"], "過" if k["c1"] else "✗", r["beat"], "過" if k["c2"] else "✗", k["dh1"], k["dh2"], "過" if k["c3"] else "✗"))
P("（耗時 %.0f 秒）" % (time.time() - T0))
for sect in ("rank", "filter"):
    for r in RES[sect]: r.pop("cs", None)
json.dump(RES, open("stagetest/a_star_res_%s.json" % TAG, "w"), ensure_ascii=False, indent=1)
OUT.close()
