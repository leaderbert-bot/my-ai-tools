"""任務 D：產業循環位置（stage_data.pkl / ind_stage.py / stage_lib.py）方法論稽核。
用法：cd SP && timeout 1800 python3 stagetest/d_audit.py [--quick]
  1 偷看未來  2 TTM 公式  3 倖存者偏差  4 位置 vs 已知循環的落後月數  5 門檻敏感度  6 多重比較（隨機規則）  7 其他假陽性來源
所有數字附 n；輸出 stagetest/d_audit_out.txt"""
import sys, os, json, glob, bisect, random, statistics, collections, pickle, time
SP = "/tmp/claude-0/-home-user-my-ai-tools/bb9482f7-4c31-5f24-a06a-81bc958a76a4/scratchpad"
sys.path.insert(0, SP); os.chdir(SP)
QUICK = "--quick" in sys.argv
T0 = time.time()
OUT = open("stagetest/d_audit_out.txt" if not QUICK else "stagetest/d_audit_out_quick.txt", "w", encoding="utf-8")
def P(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); OUT.write(s + "\n"); OUT.flush()
def med(xs): return statistics.median(xs) if xs else float("nan")
def pct(xs, p):
    if not xs: return float("nan")
    xs = sorted(xs); k = (len(xs) - 1) * p; lo = int(k); hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)
def f1(x): return "nan" if x is None or x != x else "%.1f" % x
def f2(x): return "nan" if x is None or x != x else "%.2f" % x
P("# 任務 D 方法論稽核  %s  (quick=%s)" % (time.strftime("%Y-%m-%d %H:%M"), QUICK))

# ---------- 資料 ----------
px, cal, mk = pickle.load(open("px.pkl", "rb")); idx = {d: i for i, d in enumerate(cal)}
import stage_lib as S
D = S.D; YMS = D["yms"]; AV = D["avail"]; IND = D["IND"]; GRP = D["GRP"]
rev = collections.defaultdict(dict)
for ym, slot in json.load(open("dl/rev10.json"))["m"].items():
    for c, v in slot.items():
        if isinstance(v, (int, float)): rev[c][ym] = float(v)
F = collections.defaultdict(dict); FILES = {}
for f in glob.glob("mopsfin/mopsfin_*.json"):
    nm = os.path.basename(f)[:-5].split("_"); q = "%dQ%s" % (int(nm[2]) + 1911, nm[3]); FILES[(q, nm[1])] = f
    for c, r in json.load(open(f))["rows"].items(): F[c][q] = r
from datetime import date
def ym_prev(ym, k):
    y, m = int(ym[:4]), int(ym[4:]); m -= k
    while m <= 0: m += 12; y -= 1
    return "%04d%02d" % (y, m)
def ym_add(ym, k): return ym_prev(ym, -k)
def ym_diff(a, b): return (int(a[:4]) - int(b[:4])) * 12 + int(a[4:]) - int(b[4:])
def qprev(q, k=1):
    y, n = int(q[:4]), int(q[5]); n -= k
    while n <= 0: n += 4; y -= 1
    return "%dQ%d" % (y, n)
def num(x): return float(x) if isinstance(x, (int, float)) else None
def cum(c, q, k):
    r = F[c].get(q); return num(r.get(k)) if r else None
def due(q):
    y, n = int(q[:4]), int(q[5]); return date(y + 1, 3, 31).isoformat() if n == 4 else [None, date(y, 5, 15), date(y, 8, 14), date(y, 11, 14)][n].isoformat()
ALLQ = sorted(set(q for c in F for q in F[c])); DUE = {q: due(q) for q in ALLQ}
def ttm_cum(c, q, k):   # ind_stage.py 的公式
    a = cum(c, q, k); n = int(q[5])
    if a is None: return None
    if n == 4: return a
    y4 = cum(c, "%dQ4" % (int(q[:4]) - 1), k); ly = cum(c, qprev(q, 4), k)
    return None if (y4 is None or ly is None) else a + y4 - ly
def single(c, q, k):    # 單季（獨立算法，拿來對照）
    a = cum(c, q, k); n = int(q[5])
    if a is None: return None
    if n == 1: return a
    p = cum(c, qprev(q), k); return None if p is None else a - p
def ttm_single(c, q, k):
    xs = [single(c, qprev(q, j), k) for j in range(4)]
    return None if None in xs else sum(xs)
c50 = []; last = None
for d in cal:
    v = px.get("0050", {}).get(d); last = v[3] if v else last; c50.append(last)
P("資料：cal %s～%s（%d 日）；stage 月份 %s～%s（%d）；ind 列 %d、stock 列 %d；mopsfin 季 %s～%s（%d 檔案）" % (cal[0], cal[-1], len(cal), YMS[0], YMS[-1], len(YMS), len(D["ind"]), len(D["stock"]), ALLQ[0], ALLQ[-1], len(FILES)))

# ============ 1. 偷看未來 ============
P("\n==== 1. 偷看未來（avail / due / mom60）====")
bad_av = 0
for ym in YMS:
    y, m = int(ym[:4]), int(ym[4:]); m += 1
    if m > 12: m -= 12; y += 1
    if not (AV[ym] >= "%04d-%02d-11" % (y, m) and AV[ym] in idx): bad_av += 1
P("avail(ym) ≥ 次月 11 日且為交易日：違反 %d/%d" % (bad_av, len(YMS)))
rng = random.Random(7); bad_ymat = 0; n_ymat = 0
for d in rng.sample(cal[300:], 300):
    ym = S.ym_at(d); n_ymat += 1
    j = YMS.index(ym)
    if not (AV[ym] <= d and (j + 1 >= len(YMS) or AV[YMS[j + 1]] > d)): bad_ymat += 1
P("ym_at(d)：avail[ym] ≤ d < avail[下一月]  違反 %d/%d（隨機抽 300 個交易日）" % (bad_ymat, n_ymat))
P("季報取用規則：latest_q 取 DUE[q] < avail(ym)（嚴格小於，期限當天不算可用，保守）；季報期限 Q1 5/15、Q2 8/14、Q3 11/14、Q4 隔年 3/31")
keys = [k for k in D["stock"] if D["stock"][k]["gm_d"] is not None and D["stock"][k]["mom60"] is not None]
keys2 = [k for k in D["stock"] if D["stock"][k]["gm_d"] is None]
rng = random.Random(11); sample = rng.sample(keys, 14) + rng.sample(keys2, 6)
fails = []; P("抽 20 個 (code, ym) 重算（r3 用月份 ≤ ym；季報 due < avail；mom60 兩個價格日 ≤ avail）：")
for (c, ym) in sample:
    o = D["stock"][(c, ym)]; A = AV[ym]
    ms = [ym_prev(ym, j) for j in range(3)] + [ym_prev(ym, 12 + j) for j in range(3)]
    ok_m = max(ms) <= ym
    r3 = (sum(rev[c][x] for x in ms[:3]) / sum(rev[c][x] for x in ms[3:]) - 1) * 100
    ok_r3 = abs(r3 - o["r3"]) < 1e-6
    q = o["q"]; ok_q = (q is None) or (DUE[q] < A)
    # 是不是「可用的最新一季」
    best = None
    for qq in ALLQ:
        if DUE[qq] < A and qq in F[c]: best = qq
    ok_latest = (best == q)
    g = None
    if q:
        a1, b1 = ttm_cum(c, q, "gross"), ttm_cum(c, q, "rev"); a0, b0 = ttm_cum(c, qprev(q, 4), "gross"), ttm_cum(c, qprev(q, 4), "rev")
        if None not in (a1, b1, a0, b0) and b1 and b0: g = a1 / b1 * 100 - a0 / b0 * 100
    ok_g = (g is None and o["gm_d"] is None) or (g is not None and o["gm_d"] is not None and abs(g - o["gm_d"]) < 1e-6)
    i = idx[A]; d0 = cal[i - 60]; mom = None
    b1_, b0_ = px[c].get(A), px[c].get(d0)
    if b1_ and b0_ and c50[i] and c50[i - 60]: mom = (b1_[3] / b0_[3] - 1) * 100 - (c50[i] / c50[i - 60] - 1) * 100
    ok_mom = (mom is None and o["mom60"] is None) or (mom is not None and o["mom60"] is not None and abs(mom - o["mom60"]) < 1e-6)
    ok_dates = d0 <= A and A <= A
    allok = all([ok_m, ok_r3, ok_q, ok_latest, ok_g, ok_mom, ok_dates])
    if not allok: fails.append((c, ym, ok_m, ok_r3, ok_q, ok_latest, ok_g, ok_mom))
    P("  %s %s avail=%s 月份max=%s(≤ym %s) r3 %s=%s q=%s due=%s(<avail %s, 最新 %s) gm_d %s=%s mom60 %s=%s（價格日 %s,%s） %s" % (
        c, ym, A, max(ms), ok_m, f2(r3), f2(o["r3"]), q, DUE.get(q) if q else None, ok_q, ok_latest, f2(g), f2(o["gm_d"]), f2(mom), f2(o["mom60"]), d0, A, "OK" if allok else "FAIL"))
P("→ 20 筆中 %d 筆通過、%d 筆失敗 %s" % (20 - len(fails), len(fails), fails if fails else ""))
# 產業層：抽 5 個 (產業, ym) 重算中位數
rng = random.Random(3); ik = rng.sample([k for k in D["ind"] if D["ind"][k]["gm_d"] is not None], 5); nb = 0
for (k, ym) in ik:
    o = D["ind"][(k, ym)]; mem = [c for c in IND if IND[c] == k and (c, ym) in D["stock"]]
    r3s = [D["stock"][(c, ym)]["r3"] for c in mem]; gs = [D["stock"][(c, ym)]["gm_d"] for c in mem if D["stock"][(c, ym)]["gm_d"] is not None]
    ok = len(mem) == o["n"] and abs(med(r3s) - o["rev3"]) < 1e-9 and abs(med(gs) - o["gm_d"]) < 1e-9
    nb += 0 if ok else 1
    P("  產業 %s %s n=%d/%d rev3 %s=%s gm_d %s=%s（有 gm_d 的成員 %d/%d）%s" % (k, ym, len(mem), o["n"], f2(med(r3s)), f2(o["rev3"]), f2(med(gs)), f2(o["gm_d"]), len(gs), len(mem), "OK" if ok else "FAIL"))
P("→ 產業中位數重算 %d/5 通過" % (5 - nb))
P("季報缺檔（2019Q1 sii、2023Q1 sii、2023Q3 otc，見第 2 節）時 latest_q 會退回更早一季：不是偷看，是「用舊資料」（落後一季）。")
P("注意（非偷看，但要知道）：mom60 用 avail 當天收盤，而回測也在 avail 當天收盤買 → 訊號與進場同一根收盤（與 mgk_test.py 一致）；"
  "月營收／季報用的是今天快取的數字（若有重編／更正，不是當時版本）。")

# ============ 2. TTM 公式 ============
P("\n==== 2. TTM 毛利率公式 cum(q)+cumQ4(前一年)−cum(q−4) ====")
P("代數：cum(q)=Q1..Qn(今年)；cumQ4(前一年)=Q1..Q4(去年)；cum(q−4)=Q1..Qn(去年) → 相加減 = Q1..Qn(今年)+Q(n+1)..Q4(去年) 恰 4 季；n=4 時直接取 cum(Q4)。公式正確。")
for c, qs in (("2330", ["2021Q2", "2022Q3", "2024Q1", "2023Q4"]), ("2603", ["2021Q2", "2021Q3", "2022Q1", "2021Q4"])):
    P("  -- %s" % c)
    for q in qs:
        y4q = "%dQ4" % (int(q[:4]) - 1); lq = qprev(q, 4)
        rows = []
        for k in ("rev", "gross"):
            a, y4, ly = cum(c, q, k), cum(c, y4q, k), cum(c, lq, k); t1 = ttm_cum(c, q, k); t2 = ttm_single(c, q, k)
            rows.append((k, a, y4, ly, t1, t2))
        g1 = rows[1][4] / rows[0][4] * 100 if rows[0][4] and rows[1][4] is not None else None
        g0r, g0g = ttm_cum(c, lq, "rev"), ttm_cum(c, lq, "gross"); g0 = g0g / g0r * 100 if g0r and g0g is not None else None
        for k, a, y4, ly, t1, t2 in rows:
            P("    %s %-5s cum(%s)=%s + cum(%s)=%s − cum(%s)=%s → TTM=%s ；4 個單季相加=%s %s" % (q, k, q, a, y4q, y4, lq, ly, t1, t2, "一致" if (t1 is not None and t2 is not None and abs(t1 - t2) < 1) else ("（單季法缺資料，無法對照）" if t2 is None else "不一致！")))
        P("    %s TTM 毛利率 %s%%，去年同期 TTM %s%% → gm_d %s 點" % (q, f2(g1), f2(g0), f2(g1 - g0) if (g1 is not None and g0 is not None) else None))
P("  外部對照：台積 2023 全年（cum 2023Q4）毛利 1,175,110,628 / 營收 2,161,735,841 = %.2f%%（公開年報 54.4%%）；2022 全年 %.2f%%（公開 59.6%%）" % (cum("2330", "2023Q4", "gross") / cum("2330", "2023Q4", "rev") * 100, cum("2330", "2022Q4", "gross") / cum("2330", "2022Q4", "rev") * 100))
# 資料洞
P("  資料洞（會讓 TTM 變 None 或退回舊季）：")
for q in ALLQ:
    rows_ = [F[c][q] for c in F if q in F[c]]
    ng = sum(1 for r in rows_ if not isinstance(r.get("gross"), (int, float))); nr = sum(1 for r in rows_ if not isinstance(r.get("rev"), (int, float)))
    miss = [m for m in ("sii", "otc") if (q, m) not in FILES]
    if miss or ng > 0.2 * len(rows_):
        P("    %s：列數 %d、缺 gross %d、缺 rev %d、檔案缺 %s" % (q, len(rows_), ng, nr, miss or "無"))
none_by_ym = collections.Counter(); tot_by_ym = collections.Counter()
for (c, ym), o in D["stock"].items():
    tot_by_ym[ym] += 1
    if o["gm_d"] is None: none_by_ym[ym] += 1
P("  個股 gm_d 為 None 的比例（月）：" + " ".join("%s:%d%%" % (ym, 100 * none_by_ym[ym] // tot_by_ym[ym]) for ym in YMS if none_by_ym[ym] > 0.3 * tot_by_ym[ym]))
ind_none = [ym for ym in YMS if sum(1 for (k, y), o in D["ind"].items() if y == ym and o["gm_d"] is None) > 0.5 * sum(1 for (k, y) in D["ind"] if y == ym)]
P("  產業 gm_d 多數為 None 的月份（price 偵測不到、只會有 vol?）：%s（%d 個月）" % (" ".join(ind_none), len(ind_none)))
sub = collections.Counter()
for (k, ym), o in D["ind"].items():
    mem = [c for c in IND if IND[c] == k and (c, ym) in D["stock"]]
    ng = sum(1 for c in mem if D["stock"][(c, ym)]["gm_d"] is not None)
    if o["gm_d"] is not None and ng < 0.5 * len(mem): sub[ym] += 1
P("  產業 gm_d 中位數只由 <50%% 成員算出（sii/otc 缺檔造成的子集合）：%d 個產業月；月份：%s" % (sum(sub.values()), " ".join("%s:%d" % (y, sub[y]) for y in sorted(sub))))

# ============ 3. 倖存者偏差 ============
P("\n==== 3. 倖存者偏差 ====")
codes = [c for c in px if len(c) == 4 and c.isdigit() and not c.startswith("00") and px[c]]
first_px = {c: min(px[c]) for c in codes}; last_px = {c: max(px[c]) for c in codes}
notind = [c for c in codes if c not in IND]
still = [c for c in notind if last_px[c] >= "2026-10-01"]
P("px 4 碼代號 %d：在 IND %d、不在 IND %d（其中到 2026-10 還在交易 %d：%s；其餘 %d 檔是下市股）" % (len(codes), len(codes) - len(notind), len(notind), len(still), " ".join(sorted(still)), len(notind) - len(still)))
P("不在 IND 的最後交易年：%s" % sorted(collections.Counter(last_px[c][:4] for c in notind).items()))
rc = [c for c in rev if c in px and len(c) == 4 and c.isdigit() and not c.startswith("00")]
P("月營收檔 rev10 有營收且有日 K 的代號 %d，其中在 IND %d、不在 %d（%s）→ 營收資料本身只涵蓋今天的上市名單，下市股在營收層就不存在" % (len(rc), sum(1 for c in rc if c in IND), sum(1 for c in rc if c not in IND), [c for c in rc if c not in IND]))
C_all = pickle.load(open("cands.pkl", "rb"))
P("★ 候選 cands.pkl %d 筆：代號不在 IND %d 筆（%d 個代號）" % (len(C_all), sum(1 for c in C_all if c["code"] not in IND), len(set(c["code"] for c in C_all if c["code"] not in IND))))
# MGK 引擎
ns_m = {}; sys.argv = ["mgk_test.py"]
src_m = open("mgk_test.py").read().split("b = run([])")[0]
src_m = src_m.replace('done.append((c / p["in"] - 1) * 100 - COST * 100)', 'done.append((c / p["in"] - 1) * 100 - COST * 100); DONE_D.append(p["out"])')
src_m = src_m.replace("def run(S, seed=None", "DONE_D = []\ndef run(S, seed=None")
exec(src_m, ns_m)
sig = ns_m["sig"]; S20 = [s for s in sig if s["r60x"] > 20]
P("MGK 訊號 %d 筆（先漲 >20 點 %d 筆）：代號不在 IND %d / %d 筆" % (len(sig), len(S20), sum(1 for s in sig if s["code"] not in IND), sum(1 for s in S20 if s["code"] not in IND)))
P("→ 結論：下市股同時不在產業中位數、★ 候選、MGK 訊號裡；A/B/C 的「有產業位置 vs 沒有」比較不會因下市股而失真（查不到產業的筆數 ≈ 0），但整體絕對報酬與產業位置都有倖存者偏差：")
# 年度缺失比例與中位數偏差上界
P("  (a) 下市股占比 f（該年有交易、不在 IND / 在 IND）與產業 rev3 中位數的偏差上界（假設缺的股票全在中位數以下 → 真中位 = 倖存者的 50(1−f) 百分位）：")
mem_by_ind = collections.defaultdict(list)
for c in IND: mem_by_ind[IND[c]].append(c)
for y in range(2016, 2027):
    y0, y1 = "%d-01-01" % y, "%d-12-31" % y
    trade = [c for c in codes if first_px[c] <= y1 and last_px[c] >= y0]
    n_in = sum(1 for c in trade if c in IND); f = (len(trade) - n_in) / max(1, n_in)
    diffs = []; bdiffs = []
    for (k, ym), o in D["ind"].items():
        if ym[:4] != str(y): continue
        r3s = [D["stock"][(c, ym)]["r3"] for c in mem_by_ind[k] if (c, ym) in D["stock"]]
        if len(r3s) < 6: continue
        diffs.append(med(r3s) - pct(r3s, 0.5 * (1 - f))); bdiffs.append(o["breadth"] * f / (1 + f) * 100)
    P("    %d：有交易 %d、不在 IND %d、f=%.1f%% → rev3 中位數偏高上界 中位 %s 點（IQR %s～%s，n=%d 產業月）；breadth 偏高上界 中位 %s 點" % (y, len(trade), len(trade) - n_in, 100 * f, f2(med(diffs)), f2(pct(diffs, .25)), f2(pct(diffs, .75)), len(diffs), f2(med(bdiffs))))
# 報酬層：不在 IND 的股票（下市前）60 日報酬 vs 在 IND
P("  (b) 報酬層：每月第一個交易日起 60 日報酬（等權、停牌／下市用最後一根收盤）—— 不在 IND vs 在 IND：")
def cn(code, d):
    i = idx[d]
    for j in range(i, max(-1, i - 10), -1):
        v = px.get(code, {}).get(cal[j])
        if v: return v[3]
    return None
rows_r = []
for y in range(2016, 2026):
    for m in range(1, 13):
        d = "%d-%02d-01" % (y, m); i = bisect.bisect_left(cal, d)
        if i + 60 >= len(cal): continue
        d, d2 = cal[i], cal[i + 60]
        a = []; b = []
        for c in codes:
            v0 = px[c].get(d)
            if not v0 or v0[3] < 10: continue
            v1 = cn(c, d2)
            if not v1: continue
            (b if c in IND else a).append((v1 / v0[3] - 1) * 100)
        if len(a) >= 5: rows_r.append((d, len(a), med(a), statistics.mean(a), len(b), med(b), statistics.mean(b)))
P("    月數 %d；不在 IND：每月中位數的中位 %s%%、平均的中位 %s%%（每月檔數中位 %d）；在 IND：中位 %s%%、平均 %s%%（檔數中位 %d）→ 差（不在−在）：中位 %s 點、平均 %s 點" % (
    len(rows_r), f2(med([r[2] for r in rows_r])), f2(med([r[3] for r in rows_r])), med([r[1] for r in rows_r]), f2(med([r[5] for r in rows_r])), f2(med([r[6] for r in rows_r])), med([r[4] for r in rows_r]),
    f2(med([r[2] - r[5] for r in rows_r])), f2(med([r[3] - r[6] for r in rows_r]))))
P("    被排除股票的平均 60 日報酬較低 %s 點、占比 1～9%% → 全市場等權 60 日報酬被高估約 %s～%s 點（上界：f × 差）" % (f2(med([r[6] - r[3] for r in rows_r])), f2(0.01 * med([r[6] - r[3] for r in rows_r])), f2(0.09 * med([r[6] - r[3] for r in rows_r]))))
# 上市前營收（回填）
P("  (c) 反向偏差：IND 是今天的名單，含 2017 年後才上市的公司，而 rev10 有它們上市前的營收 → 這些還不能買的公司已被算進產業中位數：")
nl = collections.Counter(); nall = collections.Counter(); r3_un = collections.defaultdict(list); r3_li = collections.defaultdict(list)
for (c, ym), o in D["stock"].items():
    A = AV[ym]; y = ym[:4]; nall[y] += 1
    if c in px and first_px.get(c, "9999") > A: nl[y] += 1; r3_un[y].append(o["r3"])
    else: r3_li[y].append(o["r3"])
P("    年 | 個股列數 | 當月尚未上市(首根 K 在 avail 之後) | 占比 | 未上市者 r3 中位 | 已上市者 r3 中位")
for y in sorted(nall): P("    %s | %d | %d | %.1f%% | %s | %s" % (y, nall[y], nl[y], 100 * nl[y] / nall[y], f2(med(r3_un[y])), f2(med(r3_li[y]))))
chg = collections.Counter(); tot_c = 0
Pp = D["params"]
def stage_of(rev3, gmd):
    if rev3 >= Pp["price_rev"]: return "price" if (gmd is not None and gmd >= Pp["price_gm"]) else ("vol" if gmd is not None else "vol?")
    return "down" if rev3 < 0 else "flat"
for (k, ym), o in D["ind"].items():
    A = AV[ym]; mem = [c for c in mem_by_ind[k] if (c, ym) in D["stock"] and first_px.get(c, "9999") <= A]
    if len(mem) < 6: chg["<6 成員"] += 1; continue
    r3s = [D["stock"][(c, ym)]["r3"] for c in mem]; gs = [D["stock"][(c, ym)]["gm_d"] for c in mem if D["stock"][(c, ym)]["gm_d"] is not None]
    st = stage_of(med(r3s), med(gs) if len(gs) >= 3 else None); tot_c += 1
    if st != o["stage"]: chg["%s→%s" % (o["stage"], st)] += 1
P("    只用「當月已上市」成員重算產業位置：%d 個產業月中位置改變 %d 個（%.1f%%）：%s" % (tot_c, sum(v for k, v in chg.items() if k != "<6 成員"), 100 * sum(v for k, v in chg.items() if k != "<6 成員") / max(1, tot_c), dict(chg)))

# ============ 4. 位置 vs 已知循環 ============
P("\n==== 4. 位置合理性：stage 轉 price/vol 的月份 vs 產業等權股價指數高點 ====")
months = sorted(set(d[:7] for d in cal))
mend = {}  # month -> 該月最後一個交易日
for d in cal: mend[d[:7]] = d
# 日頻等權指數（成員＝今天 IND／GRP 的成員，有倖存者偏差，只拿來看時間點）；|日報酬| > 35% 視為減資／恢復交易等非交易因素，跳過
inds_all = sorted(set(k for k, _ in D["ind"]))
grp_members = collections.defaultdict(list)
for c, gs in GRP.items():
    for g in gs: grp_members[g].append(c)
GRP_SHOW = [g for g in ("被動", "面板", "重電", "散裝航運", "航運", "鋼鐵", "飯店", "旅遊") if any(k == g for k, _ in D["grp"])]
CLIP = 0.35; n_clip = 0; n_ret = 0
def build_daily(groups):  # groups: name -> [codes]
    ds = {k: [0.0] * len(cal) for k in groups}; dc = {k: [0] * len(cal) for k in groups}
    global n_clip, n_ret
    for k, mem in groups.items():
        for c in mem:
            if c not in px: continue
            s_ = px[c]; prev = None; previ = -99
            for i, d in enumerate(cal):
                v = s_.get(d)
                if v and v[3]:
                    if prev is not None and i - previ <= 10:
                        r = v[3] / prev - 1; n_ret += 1
                        if abs(r) > CLIP: n_clip += 1
                        else: ds[k][i] += r; dc[k][i] += 1
                    prev = v[3]; previ = i
    out = {}
    for k in groups:
        lv = 100.0; o = []
        for i in range(len(cal)):
            if dc[k][i] >= 3: lv *= 1 + ds[k][i] / dc[k][i]
            o.append(lv)
        out[k] = o
    return out
DIDX = build_daily({k: [c for c in mem_by_ind[k] if c in px] for k in inds_all})
GIDX = build_daily({g: grp_members[g] for g in GRP_SHOW})
P("指數成員日報酬 %d 筆，|r|>35%% 被剔除 %d 筆（%.3f%%，多為減資／恢復交易）" % (n_ret, n_clip, 100 * n_clip / max(1, n_ret)))
IDX = {k: {m: DIDX[k][idx[mend[m]]] for m in months} for k in inds_all}
GIDXM = {g: {m: GIDX[g][idx[mend[m]]] for m in months} for g in GRP_SHOW}
I50 = {m: c50[idx[mend[m]]] for m in months}
sym = {"price": "P", "vol": "v", "vol?": "?", "down": "d", "flat": "."}
def stage_str(table, k, y, mark=None):
    s = ""
    for m in range(1, 13):
        ym = "%d%02d" % (y, m); st = sym.get(table.get((k, ym), {}).get("stage", " "), " ")
        if mark and ym == mark: st = "[" + st + "]"
        s += st
    return s
CYC = [("航運業", "2020-06", "2022-06", "航運 2021"), ("鋼鐵工業", "2020-06", "2022-06", "鋼鐵 2021"), ("塑膠工業", "2020-06", "2022-06", "塑膠 2021"),
       ("電子零組件業", "2017-06", "2019-06", "電子零組件（被動元件）2018"), ("半導體業", "2017-01", "2019-06", "半導體 2017-18"), ("半導體業", "2020-03", "2022-06", "半導體 2020-21"),
       ("光電業", "2020-06", "2022-06", "光電（面板）2021"), ("觀光餐旅", "2022-06", "2024-06", "觀光餐旅 2023"), ("生技醫療業", "2020-01", "2021-06", "生技 2020"),
       ("建材營造", "2020-06", "2022-12", "建材營造 2021-22"), ("電機機械", "2023-01", "2025-06", "電機機械（重電）2023-24")]
CYC_G = [("被動", "2017-06", "2019-06", "族群：被動元件 2018"), ("面板", "2020-06", "2022-06", "族群：面板 2021"), ("重電", "2023-01", "2025-06", "族群：重電 2023-24"),
         ("散裝航運", "2020-06", "2022-06", "族群：散裝航運 2021"), ("飯店", "2022-06", "2024-06", "族群：飯店 2023")]
lag_rows = []
P("說明：peak＝視窗內等權指數最高的月份；first_up＝視窗內第一次由 down/flat 轉成 vol/vol?/price 的月份（up2＝連續 2 個月才算）；first_price＝第一次 price（price2＝連續 2 個月）；new_price＝資料表 new_price 第一次為真。"
  "stage 月份 ym 要到 avail(ym)（次月 11 日後）才看得到，「實際知道」再 +1 個月。落後月數 = 月份 − peak（正＝晚）。「後6月超額」＝在 avail(ym) 收盤進場、126 個交易日後的指數報酬扣 0050 同期。")
def cycle_lag(table, k, ixm, ixd, w0, w1, lab, show_years=True):
    win = [m for m in months if w0 <= m <= w1]
    peak = max(win, key=lambda m: ixm[m]); trough = min([m for m in win if m <= peak], key=lambda m: ixm[m]); pk_ym = peak.replace("-", "")
    seq = [(m.replace("-", ""), table.get((k, m.replace("-", "")), {}).get("stage")) for m in win]
    fu = fu2 = fp = fp2 = fn = None; prev = None
    for j, (ym, st) in enumerate(seq):
        nxt = seq[j + 1][1] if j + 1 < len(seq) else None
        if st in ("vol", "vol?", "price") and prev in ("down", "flat"):
            if fu is None: fu = ym
            if fu2 is None and nxt in ("vol", "vol?", "price"): fu2 = ym
        if st == "price":
            if fp is None: fp = ym
            if fp2 is None and nxt == "price": fp2 = ym
        if table.get((k, ym), {}).get("new_price") and fn is None: fn = ym
        prev = st
    lag = lambda ym: None if ym is None else ym_diff(ym, pk_ym)
    def got(ym):   # 在 avail(ym) 收盤進場，126 個交易日後的指數報酬 − 0050 同期
        if ym is None: return None
        i0 = idx[AV[ym]]; i1 = i0 + 126
        if i1 >= len(cal) or not c50[i0] or not c50[i1]: return None
        return (ixd[i1] / ixd[i0] - 1) * 100 - (c50[i1] / c50[i0] - 1) * 100
    rise = (ixm[peak] / ixm[trough] - 1) * 100
    lag_rows.append((lab, k, peak, fu, fu2, fp, fp2, fn, lag(fu), lag(fu2), lag(fp), lag(fp2), got(fu2), got(fp2)))
    P("  %-26s peak %s（自 %s 低點 +%.0f%%）| up %s(%s月) up2 %s(%s月, 後6月超額 %s%%) | price %s(%s月) price2 %s(%s月, 後6月超額 %s%%) | new_price %s" % (
        lab, peak, trough, rise, fu, lag(fu), fu2, lag(fu2), f1(got(fu2)), fp, lag(fp), fp2, lag(fp2), f1(got(fp2)), fn))
    if show_years:
        for y in range(int(w0[:4]), int(w1[:4]) + 1):
            P("      %d %s  指數(月底) %s" % (y, stage_str(table, k, y, pk_ym if pk_ym[:4] == str(y) else None), " ".join("%4.0f" % ixm["%d-%02d" % (y, m)] if "%d-%02d" % (y, m) in ixm else "   -" for m in range(1, 13))))
for k, w0, w1, lab in CYC: cycle_lag(D["ind"], k, IDX[k], DIDX[k], w0, w1, lab)
P("  -- 族群層（groups.csv 是今天定的成員，有事後之見，只當參考）：")
for g, w0, w1, lab in CYC_G:
    if g in GIDX: cycle_lag(D["grp"], g, GIDXM[g], GIDX[g], w0, w1, lab)
for g in GRP_SHOW:
    P("  族群 %-6s stage：" % g + " | ".join("%d %s" % (y % 100, stage_str(D["grp"], g, y)) for y in range(2017, 2027)))
P("  各產業逐月位置字串（P=price v=vol ?=vol? d=down .=flat）：")
for k in sorted(IDX):
    P("    %-10s " % k + " | ".join("%d %s" % (y % 100, stage_str(D["ind"], k, y)) for y in range(2016, 2027)))
# 事件統計：產業指數在 new_price / 轉 vol 之後的表現（不挑循環）
P("  不挑循環的事件統計（日頻產業等權指數，自 avail(ym) 當天收盤起 63／126／252 個交易日，扣 0050 同期）：")
def fwd(k, ym, h):
    i0 = idx[AV[ym]]; i1 = i0 + {3: 63, 6: 126, 12: 252}[h]
    if i1 >= len(cal) or not c50[i0] or not c50[i1]: return None
    return (DIDX[k][i1] / DIDX[k][i0] - 1) * 100 - (c50[i1] / c50[i0] - 1) * 100
for lab, cond in (("new_price（這月 price、3 個月前不是）", lambda k, ym, o: o["new_price"]),
                  ("轉 vol/vol?（這月 vol 類、上月 down/flat）", lambda k, ym, o: o["stage"] in ("vol", "vol?") and o["prev_stage"] in ("down", "flat")),
                  ("轉 down（這月 down、上月不是）", lambda k, ym, o: o["stage"] == "down" and o["prev_stage"] not in ("down", None)),
                  ("所有產業月（基準）", lambda k, ym, o: True)):
    ev = [(k, ym) for (k, ym), o in D["ind"].items() if cond(k, ym, o)]
    line = "    %-36s n=%d" % (lab, len(ev))
    for h in (3, 6, 12):
        xs = [fwd(k, ym, h) for k, ym in ev]; xs = [x for x in xs if x is not None]
        line += " | %d月 超額中位 %s 平均 %s 勝 %s%% (n=%d)" % (h, f1(med(xs)), f1(statistics.mean(xs)) if xs else "nan", f1(100 * sum(1 for x in xs if x > 0) / len(xs)) if xs else "nan", len(xs))
    P(line)

# ============ 5. 門檻敏感度 ============
P("\n==== 5. 門檻敏感度 ====")
indrows = list(D["ind"].items())
r3s_all = [o["rev3"] for _, o in indrows]; gm_all = [o["gm_d"] for _, o in indrows if o["gm_d"] is not None]
P("產業月 rev3 中位數分佈（n=%d）：p10 %s p25 %s p50 %s p75 %s p90 %s p95 %s；≥10 的占 %.1f%%，≥5 占 %.1f%%，<0 占 %.1f%%" % (len(r3s_all), f1(pct(r3s_all, .1)), f1(pct(r3s_all, .25)), f1(pct(r3s_all, .5)), f1(pct(r3s_all, .75)), f1(pct(r3s_all, .9)), f1(pct(r3s_all, .95)),
    100 * sum(1 for x in r3s_all if x >= 10) / len(r3s_all), 100 * sum(1 for x in r3s_all if x >= 5) / len(r3s_all), 100 * sum(1 for x in r3s_all if x < 0) / len(r3s_all)))
P("產業月 gm_d 中位數分佈（有值 n=%d／%d）：p10 %s p25 %s p50 %s p75 %s p90 %s p95 %s；≥1.0 占 %.1f%%，≥0.5 占 %.1f%%，≥0 占 %.1f%%" % (len(gm_all), len(indrows), f1(pct(gm_all, .1)), f1(pct(gm_all, .25)), f1(pct(gm_all, .5)), f1(pct(gm_all, .75)), f1(pct(gm_all, .9)), f1(pct(gm_all, .95)),
    100 * sum(1 for x in gm_all if x >= 1) / len(gm_all), 100 * sum(1 for x in gm_all if x >= .5) / len(gm_all), 100 * sum(1 for x in gm_all if x >= 0) / len(gm_all)))
both = [(o["rev3"], o["gm_d"]) for _, o in indrows if o["gm_d"] is not None]
P("rev3 ≥ 10 的產業月 n=%d，其中 gm_d 有值 %d、gm_d ≥ 1 的 %d（price）、gm_d < 1 的 %d（vol）、gm_d None 的 %d（vol?）" % (sum(1 for x in r3s_all if x >= 10), sum(1 for r, g in both if r >= 10), sum(1 for r, g in both if r >= 10 and g >= 1), sum(1 for r, g in both if r >= 10 and g < 1), sum(1 for _, o in indrows if o["rev3"] >= 10 and o["gm_d"] is None)))
P("逐年：price / vol / vol? 產業月數")
byy = collections.defaultdict(collections.Counter)
for (k, ym), o in indrows: byy[ym[:4]][o["stage"]] += 1
for y in sorted(byy): P("  %s price %d vol %d vol? %d down %d flat %d（共 %d）" % (y, byy[y]["price"], byy[y]["vol"], byy[y]["vol?"], byy[y]["down"], byy[y]["flat"], sum(byy[y].values())))
P("門檻格點：price 產業月數 / 曾經 price 的產業數 / new_price 事件數（gm_d None 一律不算 price）")
P("  rev3≥ \\ gm_d≥ " + "".join("%14s" % g for g in (0.0, 0.5, 1.0, 2.0)))
for rt in (5, 10, 15, 20):
    line = "  %6d        " % rt
    for gt in (0.0, 0.5, 1.0, 2.0):
        pr = {(k, ym) for (k, ym), o in indrows if o["rev3"] >= rt and o["gm_d"] is not None and o["gm_d"] >= gt}
        newp = sum(1 for (k, ym) in pr if (k, ym_prev(ym, 3)) in D["ind"] and (k, ym_prev(ym, 3)) not in pr)
        line += "%5d/%2d/%4d  " % (len(pr), len(set(k for k, _ in pr)), newp)
    P(line)
P("  現行（10 / 1.0）：price %d/%d 產業月 = %.1f%%；曾 price 的產業 %d/%d；new_price 事件 %d" % (sum(1 for _, o in indrows if o["stage"] == "price"), len(indrows), 100 * sum(1 for _, o in indrows if o["stage"] == "price") / len(indrows), len(set(k for (k, _), o in indrows if o["stage"] == "price")), len(IDX), sum(1 for _, o in indrows if o["new_price"])))
# price 持續性
runs = []; cur = 0
for k in sorted(IDX):
    seq = [D["ind"].get((k, ym), {}).get("stage") for ym in YMS]; cur = 0
    for st in seq:
        if st == "price": cur += 1
        elif cur: runs.append(cur); cur = 0
    if cur: runs.append(cur)
P("  price 連續段 n=%d：長度中位 %s、平均 %s、1 個月就結束的 %d 段（%.0f%%）→ 位置來回跳的程度" % (len(runs), f1(med(runs)), f1(statistics.mean(runs)) if runs else "nan", sum(1 for r in runs if r == 1), 100 * sum(1 for r in runs if r == 1) / max(1, len(runs))))
P("  各產業 price 月數（n）、gm_d 最大值：")
for k in sorted(IDX):
    xs = [o for (kk, ym), o in indrows if kk == k]; gm = [o["gm_d"] for o in xs if o["gm_d"] is not None]
    P("    %-10s 月數 %3d  price %3d  vol %3d  vol? %3d  成員數中位 %3d  gm_d 最大 %s  rev3 最大 %s" % (k, len(xs), sum(1 for o in xs if o["stage"] == "price"), sum(1 for o in xs if o["stage"] == "vol"), sum(1 for o in xs if o["stage"] == "vol?"), med([o["n"] for o in xs]), f1(max(gm)) if gm else "nan", f1(max(o["rev3"] for o in xs))))
P("  vol? 的處理：vol? = rev3 ≥ 10 但 gm_d None，共 %d 個產業月，其中 2016-01～2018-07 占 %d（%.0f%%）。這段 price 根本偵測不到（見第 2 節資料洞），"
  "若 A/B/C 把 vol? 當 vol、或把 vol? 排除，2017-18 半導體／被動元件循環就會被標錯或整段消失（前半段樣本）。" % (sum(1 for _, o in indrows if o["stage"] == "vol?"), sum(1 for (k, ym), o in indrows if o["stage"] == "vol?" and ym <= "201807"), 100 * sum(1 for (k, ym), o in indrows if o["stage"] == "vol?" and ym <= "201807") / max(1, sum(1 for _, o in indrows if o["stage"] == "vol?"))))

# ============ 6. 多重比較 ============
P("\n==== 6. 多重比較：隨機規則用「30 個 seed 中位數比現行高 3 點」偶然達標的機率 ====")
def load_star(phi):
    ns = {}; sys.argv = ["star_rank.py", "cands.pkl", str(phi)]
    exec(open("star_rank.py").read().split("def main():")[0], ns); return ns
def med30(ns, keyfn, cap=3, seeds=range(1000, 1030)):
    cs = sorted(ns["stats"](*ns["run"](keyfn=keyfn, seed=s, cap=cap))["cagr"] for s in seeds); return cs[len(cs) // 2], cs[0], cs[-1]
CUR = lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1)
FAM_RES = {}
for phi in ((0.95,) if QUICK else (0.95, 0.99)):
    R_ORD = 6 if QUICK else (40 if phi == 0.95 else 25); R_FLT = 4 if QUICK else (30 if phi == 0.95 else 20)
    ns = load_star(phi); C = ns["C"]
    t = time.time()
    rs = sorted(ns["stats"](*ns["run"](seed=s, cap=3))["cagr"] for s in range(100)); rand_med = rs[50]
    cm, clo, chi = med30(ns, CUR)
    P("phi ≥ %.2f：候選 %d、天數 %d；純隨機 100 次中位 %.1f%%（%.1f～%.1f）；現行排序 30 seed 中位 %.1f%%（%.1f～%.1f）  [%.0fs]" % (phi, len(C), len(ns["days"]), rand_med, rs[0], rs[-1], cm, clo, chi, time.time() - t))
    # 現行規則換不同 seed 區塊：中位數本身的雜訊
    blocks = [med30(ns, CUR, seeds=range(b, b + 30))[0] for b in range(2000, 2000 + 30 * (3 if QUICK else 12), 30)]
    P("  現行排序換 %d 組不同的 30 seed：中位數 %s → 範圍 %.1f～%.1f（寬 %.1f 點）＝「3 點」門檻的雜訊底" % (len(blocks), " ".join("%.1f" % b for b in blocks), min(blocks), max(blocks), max(blocks) - min(blocks)))
    # 候選的 (產業, 月) 鍵
    for c in C:
        c["_im"] = (S.ind_of(c["code"]), S.ym_at(c["d"]))
    im_keys = sorted(set(c["_im"] for c in C if c["_im"][0]))
    code_keys = sorted(set(c["code"] for c in C))
    P("  候選的 (產業,月) 組合 %d 個、代號 %d 個 → 「產業位置」這類鍵的獨立選擇數遠少於候選數 %d" % (len(im_keys), len(code_keys), len(C)))
    def fam_cand(p, r):
        rg = random.Random(r); fl = {id(c): (0 if rg.random() < p else 1) for c in C}; return lambda c: (fl[id(c)],)
    def fam_code(p, r):
        rg = random.Random(r); fl = {k: (0 if rg.random() < p else 1) for k in code_keys}; return lambda c: (fl[c["code"]],)
    def fam_im(p, r):
        rg = random.Random(r); fl = {k: (0 if rg.random() < p else 1) for k in im_keys}; return lambda c: (fl.get(c["_im"], 1),)
    def fam_im_cur(p, r):
        f = fam_im(p, r); return lambda c: f(c) + CUR(c)
    def fam_cur_im(p, r):
        f = fam_im(p, r); return lambda c: CUR(c) + f(c)
    def fam_im5(r):   # 隨機 5 級「產業位置」（用實際 stage 頻率）
        rg = random.Random(r); lv = {k: rg.choices([0, 1, 2, 3, 4], weights=[154, 484, 171, 1852, 1459])[0] for k in im_keys}; return lambda c: (lv.get(c["_im"], 5),)
    fams = [("隨機旗標：每筆候選各自 p=0.5", lambda r: fam_cand(0.5, r)), ("隨機旗標：每筆候選各自 p=0.2", lambda r: fam_cand(0.2, r)),
            ("隨機旗標：每個代號固定 p=0.5", lambda r: fam_code(0.5, r)),
            ("隨機旗標：每個(產業,月) p=0.5（模擬產業位置）", lambda r: fam_im(0.5, r)), ("隨機旗標：每個(產業,月) p=0.2", lambda r: fam_im(0.2, r)),
            ("隨機 5 級(產業,月)位置（照實際 stage 頻率）", fam_im5),
            ("隨機(產業,月)旗標 p=0.5 當第一鍵，再接現行排序", lambda r: fam_im_cur(0.5, r)), ("現行排序，再接隨機(產業,月)旗標當第三鍵", lambda r: fam_cur_im(0.5, r))]
    res = {}
    for nm, mk_ in fams:
        t = time.time(); ms = []
        for r in range(R_ORD):
            ms.append(med30(ns, mk_(r))[0])
        ms.sort()
        p3 = sum(1 for m in ms if m >= cm + 3) / len(ms); pr3 = sum(1 for m in ms if m >= rand_med + 3) / len(ms); pc = sum(1 for m in ms if m >= cm) / len(ms)
        res[nm] = (ms, p3, pr3, pc)
        P("  %-44s n=%d 規則：30seed 中位數 的 min %.1f p50 %.1f p90 %.1f p95 %.1f max %.1f | ≥現行+3 的比例 %.0f%% | ≥現行 %.0f%% | ≥隨機中位+3 %.0f%%  [%.0fs]" % (nm, len(ms), ms[0], pct(ms, .5), pct(ms, .9), pct(ms, .95), ms[-1], 100 * p3, 100 * pc, 100 * pr3, time.time() - t))
    FAM_RES[phi] = (cm, rand_med, res)
    pool = [m for nm, (ms, _, _, _) in res.items() for m in ms if "第三鍵" not in nm]
    p_single = sum(1 for m in pool if m >= cm + 3) / len(pool)
    P("  合併（排除第三鍵那族）n=%d 條隨機規則：單條偶然 ≥ 現行+3 的機率 ≈ %.1f%%；若比 K 條規則，至少一條假達標的機率 ≈ 1−(1−p)^K：" % (len(pool), 100 * p_single) +
      " ".join("K=%d→%.0f%%" % (K, 100 * (1 - (1 - p_single) ** K)) for K in (5, 10, 20, 40, 60)))
    p_rand = sum(1 for m in pool if m >= rand_med + 3) / len(pool)
    P("  同樣對「比純隨機中位高 3 點」：單條 %.0f%%（現行排序本身就比隨機高 %.1f 點，所以隨機規則疊在前面常常也過）" % (100 * p_rand, cm - rand_med))
    # 濾網型：隨機拿掉候選
    base_C = list(C)
    def setC(newC):
        ns["C"] = newC; bd = collections.defaultdict(list)
        for c in newC: bd[c["d"]].append(c)
        ns["byday"] = bd; ns["days"] = sorted(bd)
    P("  濾網型（隨機砍候選，再用現行排序；對照＝全部候選的現行排序中位 %.1f%%）：" % cm)
    for nm, keep, mode in (("每筆候選各自保留 70%", 0.7, "cand"), ("每筆候選各自保留 50%", 0.5, "cand"), ("(產業,月) 整塊保留 50%", 0.5, "im"), ("(產業,月) 整塊保留 30%", 0.3, "im")):
        t = time.time(); ms = []; ns_ = []; sz = []
        for r in range(R_FLT):
            rg = random.Random(500 + r)
            if mode == "cand": sub_ = [c for c in base_C if rg.random() < keep]
            else:
                fl = {k: rg.random() < keep for k in im_keys}; sub_ = [c for c in base_C if fl.get(c["_im"], False)]
            setC(sub_); sz.append(len(sub_)); m, lo, hi = med30(ns, CUR); ms.append(m); ns_.append(ns["stats"](*ns["run"](keyfn=CUR, seed=1000, cap=3))["n"])
        setC(base_C); ms.sort()
        P("    %-26s n=%d：候選數中位 %d、筆數中位 %d；30seed 中位數 min %.1f p50 %.1f p90 %.1f max %.1f | ≥全候選現行+3 %.0f%% | ≥全候選現行 %.0f%%  [%.0fs]" % (nm, len(ms), int(med(sz)), int(med(ns_)), ms[0], pct(ms, .5), pct(ms, .9), ms[-1], 100 * sum(1 for m in ms if m >= cm + 3) / len(ms), 100 * sum(1 for m in ms if m >= cm) / len(ms), time.time() - t))
    # 現行排序下的持倉使用率（閒錢在 ★ 引擎是 0 報酬）
    eq, tr = ns["run"](keyfn=CUR, seed=1000, cap=3)
    occ = collections.Counter()
    for t_ in tr:
        i = idx[t_["d"]]
        for j in range(i, i + ns["HOLD"]): occ[j] += 1
    i0, i1 = idx[eq[0][0]], idx[eq[-1][0]]; days_ = list(range(i0, i1 + 1))
    P("  ★ 引擎 phi≥%.2f 現行排序：交易 %d 筆；平均持倉 %.2f/6 槽（投入比例約 %.0f%%）、沒有任何持倉的日子 %.0f%%、6 槽全滿 %.0f%%（n=%d 日）→ 閒置現金報酬 0，濾網少交易會直接拉低年化" % (
        phi, len(tr), sum(occ[j] for j in days_) / len(days_), 100 * sum(occ[j] for j in days_) / len(days_) / 6, 100 * sum(1 for j in days_ if occ[j] == 0) / len(days_), 100 * sum(1 for j in days_ if occ[j] >= 6) / len(days_), len(days_)))
# MGK 濾網的隨機對照
P("  MGK 引擎（先漲 >20 點，10 槽、閒錢 0050 含息、抱 60 天）：隨機濾網的 30 seed 中位數")
runm = ns_m["run"]
def mgk_med30(Sx, seeds=range(30)):
    cs = sorted(runm(Sx, seed=s)["cagr"] for s in seeds); return cs[len(cs) // 2], cs[0], cs[-1]
bm, blo, bhi = mgk_med30(S20); r0 = runm(S20)
P("    全部 %d 筆訊號：排序版（−r60x）年化 %.1f%% 筆數 %d；30 seed 隨機中位 %.1f%%（%.1f～%.1f）；成交 %d/%d 筆（%.0f%%）→ 槽位常滿，濾網主要是「換人」不是「少買」" % (len(S20), r0["cagr"], r0["n"], bm, blo, bhi, r0["n"], len(S20), 100 * r0["n"] / len(S20)))
for s_ in S20: s_["_im"] = (S.ind_of(s_["code"]), S.ym_at(s_["d"]))
im_keys_m = sorted(set(s_["_im"] for s_ in S20 if s_["_im"][0]))
R_M = 4 if QUICK else 40
for nm, keep, mode in (("每筆訊號各自保留 70%", 0.7, "sig"), ("每筆訊號各自保留 50%", 0.5, "sig"), ("(產業,月) 整塊保留 50%", 0.5, "im"), ("(產業,月) 整塊保留 30%", 0.3, "im")):
    t = time.time(); ms = []; nn = []
    for r in range(R_M):
        rg = random.Random(900 + r)
        if mode == "sig": sub_ = [s_ for s_ in S20 if rg.random() < keep]
        else:
            fl = {k: rg.random() < keep for k in im_keys_m}; sub_ = [s_ for s_ in S20 if fl.get(s_["_im"], False)]
        m, lo, hi = mgk_med30(sub_); ms.append(m); nn.append(runm(sub_)["n"])
    ms.sort()
    P("    %-26s n=%d：訊號數約 %d、成交筆數中位 %d；30seed 中位數 min %.1f p50 %.1f p90 %.1f max %.1f | ≥全訊號中位+3 %.0f%% | ≥全訊號中位 %.0f%% | ≥+5 %.0f%%  [%.0fs]" % (
        nm, len(ms), int(len(S20) * keep), int(med(nn)), ms[0], pct(ms, .5), pct(ms, .9), ms[-1], 100 * sum(1 for m in ms if m >= bm + 3) / len(ms), 100 * sum(1 for m in ms if m >= bm) / len(ms), 100 * sum(1 for m in ms if m >= bm + 5) / len(ms), time.time() - t))
# MGK 持倉使用率
ns_m["DONE_D"].clear(); r0 = runm(S20); outs = list(ns_m["DONE_D"])
occ = collections.Counter()
for o_ in outs:
    j1 = idx[o_]
    for j in range(j1 - ns_m["HOLD"], j1): occ[j] += 1
i0 = bisect.bisect_left(cal, "2016-06-01"); days_ = list(range(i0, len(cal)))
P("    MGK 全訊號排序版：平均持倉 %.2f/10 槽、10 槽全滿 %.0f%% 的日子、空手 %.0f%%（n=%d 日）；閒錢在 0050（年化 23.8%%）→ 濾網砍掉訊號時，錢回到 0050 不是 0" % (sum(occ[j] for j in days_) / len(days_), 100 * sum(1 for j in days_ if occ[j] >= 10) / len(days_), 100 * sum(1 for j in days_ if occ[j] == 0) / len(days_), len(days_)))

# ============ 7. 其他 ============
P("\n==== 7. 其他可能造成 A/B/C 假陽性的問題 ====")
ns = load_star(0.95); C = ns["C"]
for c in C: c["_im"] = (S.ind_of(c["code"]), S.ym_at(c["d"]))
# 候選集中在哪些產業；同日同產業
by_ind_c = collections.Counter(c["_im"][0] for c in C)
P("(a) ★ 候選的產業集中度（phi≥0.95，n=%d）：前 8 名 %s" % (len(C), by_ind_c.most_common(8)))
same = 0; tot = 0
for d, L in ns["byday"].items():
    if len(L) >= 2:
        tot += 1; cnt = collections.Counter(c["_im"][0] for c in L)
        if cnt.most_common(1)[0][1] >= 2: same += 1
P("    有 ≥2 檔候選的日子 %d 天，其中有同產業候選的 %d 天（%.0f%%）→ 產業旗標在同一天高度相關，排序鍵能分出的獨立選擇很少" % (tot, same, 100 * same / max(1, tot)))
# 候選自己的 r3 vs 產業 rev3 的相關（Spearman）
pairs = [(c["r3"], D["ind"][c["_im"]]["rev3"]) for c in C if c["r3"] is not None and c["_im"] in D["ind"]]
def rank(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0] * len(xs)
    for k, i in enumerate(o): r[i] = k
    return r
ra, rb = rank([p[0] for p in pairs]), rank([p[1] for p in pairs]); n_ = len(pairs)
rho = 1 - 6 * sum((a - b) ** 2 for a, b in zip(ra, rb)) / (n_ * (n_ ** 2 - 1))
st_c = collections.Counter((D["ind"][c["_im"]]["stage"] if c["_im"] in D["ind"] else "na") for c in C)
own = collections.Counter((D["stock"].get((c["code"], c["_im"][1]), {}).get("stage", "na")) for c in C)
P("(b) 候選自己的 r3 與其產業 rev3 的 Spearman ρ=%.2f（n=%d）；候選所在產業位置分佈 %s；候選自己的位置 %s → 產業位置與候選本身的營收動能重疊，產業旗標的「增量」要跟個股自己的位置比才算" % (rho, n_, dict(st_c), dict(own)))
# 候選日期 vs 月份邊界：候選在 avail 當天／之後幾天
gap = collections.Counter()
for c in C:
    ym = c["_im"][1]
    if ym: gap[min(30, idx[c["d"]] - idx[AV[ym]])] += 1
P("(c) 候選日距離該月營收可用日的交易日數分佔（0＝當天）：%s → 候選日期分散在整個月，產業位置是「上月的」資訊，最多落後 1 個月" % sorted(gap.items())[:12])
# 前後半樣本：price 月數
h1 = sum(1 for (k, ym), o in D["ind"].items() if o["stage"] == "price" and AV[ym] <= "2021-12-31"); h2 = sum(1 for (k, ym), o in D["ind"].items() if o["stage"] == "price" and AV[ym] > "2021-12-31")
c1 = sum(1 for c in C if c["_im"] in D["ind"] and D["ind"][c["_im"]]["stage"] == "price" and c["d"] <= "2021-12-31"); c2 = sum(1 for c in C if c["_im"] in D["ind"] and D["ind"][c["_im"]]["stage"] == "price" and c["d"] > "2021-12-31")
P("(d) price 產業月：前半（avail ≤ 2021-12-31）%d、後半 %d；★ 候選落在 price 產業：前半 %d 筆、後半 %d 筆（候選總數前半 %d、後半 %d）→ 前半的 price 幾乎都是 2021 年，兩個時段不是真正獨立的檢驗" % (
    h1, h2, c1, c2, sum(1 for c in C if c["d"] <= "2021-12-31"), sum(1 for c in C if c["d"] > "2021-12-31")))
P("(e) 產業歸類用今天的證交所分類（改類、改名的公司會被套回 2016），且 36 類裡半導體 207 檔、電子零組件 210 檔混了上下游（IC 設計、晶圓、記憶體、設備…），"
  "中位數吃不到子產業循環（被動元件 2018 只是電子零組件 210 檔中的十幾檔）。")
P("(f) 已知循環清單本身是事後挑的大行情；用它量落後月數只告訴我們「最明顯的循環有沒有抓到」，不代表 stage 的一般命中率。第 4 節的「不挑循環事件統計」才是無偏的。")
P("(g) 「30 seed 中位數高 3 點」：第 6 節量到現行排序自己換 seed 區塊的中位數就有數點的浮動；加上 A/B/C 要比幾十條規則、2 個 phi、2 種 cap，不做多重比較校正幾乎一定會有「達標」的規則。")
P("(h) ★ 引擎閒置現金報酬 0、MGK 引擎閒錢在 0050：同一個濾網在兩個引擎會有相反方向的機械效果（★ 少交易→年化降；MGK 少交易→靠 0050 撐）；濾網結果要同時報交易數與投入比例。")
P("\n==== 落後月數摘要（stage 月份 − 指數高點月份；實際知道要再 +1 個月）====")
for lab, k, peak, fu, fu2, fp, fp2, fn, lu, lu2, lp, lp2, gu2, gp2 in lag_rows:
    P("  %-26s peak %s | 轉 vol 類 %s（%s 月）連續2月 %s（%s 月，進場後6月超額 %s%%）| 轉 price %s（%s 月）連續2月 %s（%s 月，進場後6月超額 %s%%）| new_price %s" % (lab, peak, fu, lu, fu2, lu2, f1(gu2), fp, lp, fp2, lp2, f1(gp2), fn))
P("\n總耗時 %.0f 秒" % (time.time() - T0))
OUT.close()
