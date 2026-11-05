"""v_A_stat：統計面驗證任務 A 的「濾網：排除個股 down（個股 r3<0），其餘照現行排序」。
引擎／資料／現行排序與 a_star.py 完全相同（star_rank.py：6 槽、抱 20 天、cap=3、成本 0.47%；phi 設定 0.95／0.99）。
用法（在 scratchpad）：python3 stagetest/v_A_stat.py 0.95 ； python3 stagetest/v_A_stat.py 0.99 ； python3 stagetest/v_A_stat.py merge
檢查項目：
  T0 重現原結果（seed 1000+k）；T1 換 seed（2000+k、3000+k、100 seed 5000+k）＋ Mann-Whitney／置換檢定／bootstrap；
  T2 拿掉多頭 2020-07～2021-12、2024-01～2024-12（分段串接）；T3 逐年＋留一年法；T4 相鄰門檻（排除 r3<t）；
  T5 同分有先打亂的確認；T6 槽位／路徑雜訊：安慰劑濾網（隨機刪同樣筆數候選）的中位數分佈、交易層級歸因；
  T7 跟純隨機 100 次分佈比的百分位。"""
import sys, os, time, collections, statistics, pickle, random, bisect, json, math
SP = "/tmp/claude-0/-home-user-my-ai-tools/bb9482f7-4c31-5f24-a06a-81bc958a76a4/scratchpad"
sys.path.insert(0, SP); os.chdir(SP)
ARG = sys.argv[1] if len(sys.argv) > 1 else "0.95"
NSEED = int(os.environ.get("NSEED", 30)); NRAND = int(os.environ.get("NRAND", 100)); NPLAC = int(os.environ.get("NPLAC", 100))
NBIG = int(os.environ.get("NBIG", 100)); NPLAC3 = int(os.environ.get("NPLAC3", 40)); CAP = 3
H1_END = "2021-12-31"; H2_START = "2022-01-03"
BULL = [("2020-07-01", "2021-12-31"), ("2024-01-01", "2024-12-31")]
TAGS = ("095", "099")


def merge():
    lines = []
    for t in TAGS:
        lines.append(open("stagetest/v_A_stat_out_%s.txt" % t).read().rstrip()); lines.append("")
    open("stagetest/v_A_stat_out.txt", "w").write("\n".join(lines) + "\n")
    R = {t: json.load(open("stagetest/v_A_stat_res_%s.json" % t)) for t in TAGS}
    print(json.dumps(R, ensure_ascii=False, indent=1)[:6000])


if ARG == "merge":
    merge(); sys.exit(0)

PHI = ARG
sys.argv = ["star_rank.py", "cands.pkl", PHI]
exec(open("star_rank.py").read().split("def main():")[0])
import stage_lib as S
tr50, _divs = pickle.load(open("tr50.pkl", "rb"))
TAG = PHI.replace(".", "")
OUT = open("stagetest/v_A_stat_out_%s.txt" % TAG, "w")
def P(*a):
    line = " ".join(str(x) for x in a); print(line, flush=True); OUT.write(line + "\n"); OUT.flush()
T0 = time.time()
RES = dict(phi=PHI)

for c in C:
    st = S.stock_stage(c["code"], c["d"])
    c["sst"] = st["stage"] if st else "na"; c["sr3"] = st["r3"] if st else None
BASE = list(C); D0 = days[0]; N = len(BASE)
cur = lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1)
FD = lambda c: c["sst"] != "down"
n_down = sum(1 for c in BASE if not FD(c))
CK = {(c["d"], c["code"]): c for c in BASE}

def setC(newC):
    global C, byday, days
    C = newC; byday = collections.defaultdict(list)
    for c in C: byday[c["d"]].append(c)
    days = sorted(byday)
def med(L):
    L = sorted(L); return L[len(L) // 2]          # 引擎／a_star 慣例
def summ(cs):
    cs = sorted(cs); return dict(med=cs[len(cs) // 2], lo=cs[0], hi=cs[-1], mean=statistics.mean(cs), sd=statistics.pstdev(cs) if len(cs) > 1 else 0, n=len(cs))
def runs(seeds, start=D0, end=None, kf=cur):
    return [stats(*run(keyfn=kf, seed=s, cap=CAP, start=start, end=end)) for s in seeds]
def runs_tr(seeds, start=D0, end=None, kf=cur):
    o = []
    for s in seeds:
        eq, tr = run(keyfn=kf, seed=s, cap=CAP, start=start, end=end); st = stats(eq, tr); st["tr"] = tr; o.append(st)
    return o
def cagrs(seeds, start=D0, end=None, kf=cur): return [x["cagr"] for x in runs(seeds, start, end, kf)]
def rand_cagrs(seeds, start=D0, end=None): return [stats(*run(seed=s, cap=CAP, start=start, end=end))["cagr"] for s in seeds]
def pct_in(x, dist):
    dist = sorted(dist); return 100.0 * bisect.bisect_left(dist, x) / len(dist)
def Phi(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))
def mwu(a, b):
    """Mann-Whitney U（雙尾，常態近似）：a 比 b 大 → z>0"""
    allv = sorted([(v, 0) for v in a] + [(v, 1) for v in b]); ranks = [0] * len(allv); i = 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1][0] == allv[i][0]: j += 1
        for k in range(i, j + 1): ranks[k] = (i + j) / 2 + 1
        i = j + 1
    n1, n2 = len(a), len(b); R1 = sum(r for r, (v, g) in zip(ranks, allv) if g == 0)
    U1 = R1 - n1 * (n1 + 1) / 2; mu = n1 * n2 / 2; sig = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    z = (U1 - mu) / sig; return U1, z, 2 * (1 - Phi(abs(z)))
def perm_test(a, b, nperm=5000, seed=1):
    """置換檢定：中位數差 med(a)-med(b) 的雙尾 p"""
    rng = random.Random(seed); obs = med(a) - med(b); pool = list(a) + list(b); n1 = len(a); cnt = 0
    for _ in range(nperm):
        rng.shuffle(pool); d = med(pool[:n1]) - med(pool[n1:])
        if abs(d) >= abs(obs) - 1e-12: cnt += 1
    return obs, (cnt + 1) / (nperm + 1)
def boot_ci(a, b, nb=3000, seed=2):
    rng = random.Random(seed); ds = []
    for _ in range(nb):
        ds.append(med([rng.choice(a) for _ in a]) - med([rng.choice(b) for _ in b]))
    ds.sort(); return ds[int(0.025 * nb)], ds[int(0.975 * nb)]
def three_cond(f, b, rand_med):
    """a_star 的三條件：中位 ≥ 現行+3、≥25/30 贏純隨機中位、前後半都不低於現行"""
    return dict(d=f["med"] - b["med"], c1=f["med"] - b["med"] >= 3.0, c2=f["beat"] / max(1, len(f["cs"])) >= 25 / 30.0, c3=(f["h1"] >= b["h1"] and f["h2"] >= b["h2"]),
                dh1=f["h1"] - b["h1"], dh2=f["h2"] - b["h2"])
def evaluate(seeds, rand_med, kf=cur):
    full = runs_tr(seeds, kf=kf)
    cs = [x["cagr"] for x in full]
    h1 = cagrs(seeds, end=H1_END, kf=kf); h2 = cagrs(seeds, start=H2_START, kf=kf)
    o = summ(cs); o.update(beat=sum(1 for x in cs if x > rand_med), h1=med(h1), h2=med(h2), h1s=h1, h2s=h2, cs=cs,
                           n=med([x["n"] for x in full]), win=med([x["win"] for x in full]), avg=med([x["avg"] for x in full]),
                           mdd=med([x["mdd"] for x in full]), full=full)
    return o
def fmt(nm, r):
    return "  %-30s 中位 %5.1f%%（%5.1f～%5.1f，平均 %5.1f，sd %4.1f） 贏隨機 %2d/%d  前半 %5.1f%% 後半 %5.1f%%  筆數 %3d 勝率 %2.0f%% 每筆 %+5.2f%% 回撤 %5.1f%%" % (
        nm, r["med"], r["lo"], r["hi"], r["mean"], r["sd"], r["beat"], r["n_seeds"] if "n_seeds" in r else len(r["cs"]), r["h1"], r["h2"], r["n"], r["win"], r["avg"], r["mdd"])
def cond_line(k):
    return "Δ%+5.1f %s  贏隨機 %s  前半Δ%+5.1f 後半Δ%+5.1f %s → %s" % (k["d"], "過" if k["c1"] else "✗", "過" if k["c2"] else "✗", k["dh1"], k["dh2"], "過" if k["c3"] else "✗",
                                                           "三條件都過" if (k["c1"] and k["c2"] and k["c3"]) else "不過")

P("=" * 120)
P("== v_A_stat  phi ≥ %s：候選 %d 筆（%s～%s）；個股 down（r3<0）%d 筆（%.1f%%）；濾網＝刪掉這 %d 筆，再用現行排序（創新高優先、同級均量≥2000先）" % (PHI, N, days[0], days[-1], n_down, 100 * n_down / N, n_down))
P("   個股 down 的 r3 與 cands.pkl 的 r3 一致（stage_lib 個股 r3 == cands r3，兩者皆有值的 %d 筆全部相等）" % sum(1 for c in BASE if c["sr3"] is not None and c["r3"] is not None and abs(c["sr3"] - c["r3"]) < 1e-6))
nd_days = collections.Counter(len(v) for v in byday.values())
P("   有候選的天數 %d；一天候選 >3（cap）的天數 %d；down 候選落在「當天候選 >3」的 %d/%d 筆，落在「當天候選 >6（槽數）」的 %d/%d 筆" % (
    len(byday), sum(1 for v in byday.values() if len(v) > 3), sum(1 for v in byday.values() if len(v) > 3 for c in v if not FD(c)), n_down,
    sum(1 for v in byday.values() if len(v) > 6 for c in v if not FD(c)), n_down))

# ---------- 純隨機（兩組）----------
R0 = rand_cagrs(range(NRAND)); rand_med = med(R0)
R0b = rand_cagrs(range(500, 500 + NRAND))
setC([c for c in BASE if FD(c)]); RF = rand_cagrs(range(NRAND)); RFb = rand_cagrs(range(500, 500 + NRAND)); setC(BASE)
P("純隨機 %d 次（不濾，seed 0～%d）：中位 %.1f%%（%.1f～%.1f）；第二組（seed 500～）中位 %.1f%%（%.1f～%.1f）" % (NRAND, NRAND - 1, rand_med, min(R0), max(R0), med(R0b), min(R0b), max(R0b)))
P("純隨機 %d 次（濾後池，seed 0～）：中位 %.1f%%（%.1f～%.1f）；第二組 中位 %.1f%%（%.1f～%.1f）  → 排序隨機時濾網本身的效果 Δ %+.1f／%+.1f" % (
    NRAND, med(RF), min(RF), max(RF), med(RFb), min(RFb), max(RFb), med(RF) - rand_med, med(RFb) - med(R0b)))
_, zr, pr_ = mwu(RF + RFb, R0 + R0b)
P("   濾後純隨機 vs 不濾純隨機（各 %d）：Mann-Whitney z=%+.2f p=%.3f" % (2 * NRAND, zr, pr_))
RES["rand"] = dict(med=rand_med, med_b=med(R0b), filt_med=med(RF), filt_med_b=med(RFb), mwu_p=pr_)

# ---------- T0/T1：原 seed 與新 seed ----------
P("")
P("== T0/T1 原 seed（1000+k）重現 ＋ 換 seed（2000+k、3000+k）＋ 100 seed（5000+k）；贏隨機＝贏不濾純隨機中位 %.1f%% 的次數" % rand_med)
SEEDSETS = [("1000+k（原）", list(range(1000, 1000 + NSEED))), ("2000+k", list(range(2000, 2000 + NSEED))), ("3000+k", list(range(3000, 3000 + NSEED))),
            ("5000+k（%d seed）" % NBIG, list(range(5000, 5000 + NBIG)))]
EV = {}
RES["seedsets"] = []
for nm, seeds in SEEDSETS:
    setC(BASE); b = evaluate(seeds, rand_med); b["n_seeds"] = len(seeds)
    setC([c for c in BASE if FD(c)]); f = evaluate(seeds, rand_med); f["n_seeds"] = len(seeds); setC(BASE)
    EV[nm] = (b, f)
    k = three_cond(f, b, rand_med)
    paired = [fc - bc for fc, bc in zip(f["cs"], b["cs"])]
    U, z, p = mwu(f["cs"], b["cs"]); obs, pp = perm_test(f["cs"], b["cs"]); lo, hi = boot_ci(f["cs"], b["cs"])
    P("-- seed 組 %s（n=%d）--" % (nm, len(seeds)))
    P(fmt("現行（不濾）", b)); P(fmt("排除個股 down", f))
    P("   三條件（a_star 定義，贏隨機門檻 25 是以 30 seed 設計）：" + cond_line(k))
    P("   同 seed 配對 Δ（濾−不濾）：中位 %+.1f、平均 %+.1f、>0 的 %d/%d；Mann-Whitney z=%+.2f p=%.3f；中位差置換檢定 p=%.3f；中位差 bootstrap 95%% CI [%+.1f, %+.1f]" % (
        med(paired), statistics.mean(paired), sum(1 for x in paired if x > 0), len(paired), z, p, pp, lo, hi))
    P("   前半 30 seed：不濾 中位 %.1f（%.1f～%.1f） 濾 %.1f（%.1f～%.1f）；後半：不濾 %.1f（%.1f～%.1f） 濾 %.1f（%.1f～%.1f）" % (
        b["h1"], min(b["h1s"]), max(b["h1s"]), f["h1"], min(f["h1s"]), max(f["h1s"]), b["h2"], min(b["h2s"]), max(b["h2s"]), f["h2"], min(f["h2s"]), max(f["h2s"])))
    RES["seedsets"].append(dict(name=nm, n=len(seeds), base=b["med"], filt=f["med"], d=k["d"], base_lo=b["lo"], base_hi=b["hi"], filt_lo=f["lo"], filt_hi=f["hi"],
                                beat=f["beat"], base_beat=b["beat"], h1=(b["h1"], f["h1"]), h2=(b["h2"], f["h2"]), c1=k["c1"], c2=k["c2"], c3=k["c3"],
                                mwu_p=p, perm_p=pp, boot_ci=(lo, hi), paired_pos=sum(1 for x in paired if x > 0)))

# ---------- T7：百分位 ----------
P("")
P("== T7 跟純隨機 %d 次分佈比：各中位數落在純隨機分佈的百分位（多少 %% 的隨機路徑比它低）" % NRAND)
for nm in ("1000+k（原）", "2000+k", "3000+k"):
    b, f = EV[nm]
    P("  seed 組 %-12s 現行中位 %.1f → 不濾隨機第 %.0f 百分位、濾後隨機第 %.0f 百分位；濾網中位 %.1f → 不濾隨機第 %.0f 百分位、濾後隨機第 %.0f 百分位" % (
        nm, b["med"], pct_in(b["med"], R0), pct_in(b["med"], RF), f["med"], pct_in(f["med"], R0), pct_in(f["med"], RF)))
b, f = EV["1000+k（原）"]
P("  原 seed 組 30 個別 seed：現行 落在不濾隨機分佈的百分位 中位 %.0f（%.0f～%.0f）；濾網 中位 %.0f（%.0f～%.0f）" % (
    med([pct_in(x, R0) for x in b["cs"]]), min(pct_in(x, R0) for x in b["cs"]), max(pct_in(x, R0) for x in b["cs"]),
    med([pct_in(x, R0) for x in f["cs"]]), min(pct_in(x, R0) for x in f["cs"]), max(pct_in(x, R0) for x in f["cs"])))
RES["pct"] = dict(base_in_rand=pct_in(b["med"], R0), filt_in_rand=pct_in(f["med"], R0), filt_in_filtrand=pct_in(f["med"], RF))

# ---------- T2：拿掉多頭 ----------
P("")
P("== T2 拿掉多頭 2020-07～2021-12 與 2024-01～2024-12（三段各自從現金起跑、分段串接年化；n＝seed 數）")
def seg_bounds():
    segs = [(D0, "2020-06-30"), ("2022-01-01", "2023-12-31"), ("2025-01-01", cal[-1])]
    return segs
def chain_cagr(seeds, segs, kf=cur):
    out = []; per = collections.defaultdict(list)
    for s in seeds:
        tot = 1.0; nd = 0
        for a, bnd in segs:
            eq, tr = run(keyfn=kf, seed=s, cap=CAP, start=a, end=bnd)
            r = eq[-1][1] / eq[0][1]; d = idx[eq[-1][0]] - idx[eq[0][0]]
            per[(a, bnd)].append((r ** (245.0 / d) - 1) * 100); tot *= r; nd += d
        out.append((tot ** (245.0 / nd) - 1) * 100)
    return out, per
SEG = seg_bounds(); BULLSEG = [(a, bnd) for a, bnd in BULL]
RES["exbull"] = []
for nm in ("1000+k（原）", "2000+k"):
    seeds = dict(SEEDSETS)[nm]
    setC(BASE); bc, bper = chain_cagr(seeds, SEG); bb, bbper = chain_cagr(seeds, BULLSEG)
    setC([c for c in BASE if FD(c)]); fc, fper = chain_cagr(seeds, SEG); fb, fbper = chain_cagr(seeds, BULLSEG); setC(BASE)
    P("-- seed 組 %s（n=%d）--" % (nm, len(seeds)))
    P("  非多頭三段串接年化：現行 中位 %.1f%%（%.1f～%.1f）  濾網 %.1f%%（%.1f～%.1f）  Δ %+.1f；濾>現行的 seed %d/%d" % (
        med(bc), min(bc), max(bc), med(fc), min(fc), max(fc), med(fc) - med(bc), sum(1 for x, y in zip(fc, bc) if x > y), len(seeds)))
    for a, bnd in SEG:
        P("     段 %s～%s：現行 %.1f%%  濾網 %.1f%%  Δ %+.1f" % (a, bnd, med(bper[(a, bnd)]), med(fper[(a, bnd)]), med(fper[(a, bnd)]) - med(bper[(a, bnd)])))
    P("  兩段多頭串接年化：現行 中位 %.1f%%  濾網 %.1f%%  Δ %+.1f；逐段：" % (med(bb), med(fb), med(fb) - med(bb)) + "  ".join(
        "%s～%s 現行 %.1f 濾 %.1f Δ%+.1f" % (a, bnd, med(bbper[(a, bnd)]), med(fbper[(a, bnd)]), med(fbper[(a, bnd)]) - med(bbper[(a, bnd)])) for a, bnd in BULLSEG))
    RES["exbull"].append(dict(seeds=nm, base=med(bc), filt=med(fc), d=med(fc) - med(bc), filt_gt=sum(1 for x, y in zip(fc, bc) if x > y), n=len(seeds),
                              bull_base=med(bb), bull_filt=med(fb), segs={"%s~%s" % (a, bnd): (med(bper[(a, bnd)]), med(fper[(a, bnd)])) for a, bnd in SEG}))

# ---------- T3：逐年 ＋ 留一年法 ----------
P("")
P("== T3 逐年（%d seed 逐年中位）與留一年法（把某一年拿掉後的串接年化；n＝seed 數）" % NSEED)
eq0, _ = run(keyfn=cur, seed=1000, cap=CAP, start=D0)
YEARS = sorted(set(d[:4] for d, _ in eq0)); DAYS_Y = collections.Counter(d[:4] for d, _ in eq0); TOTD = idx[eq0[-1][0]] - idx[eq0[0][0]]
def yr50():
    base = tr50[idx[eq0[0][0]]]; last = {}
    for d, e in eq0: last[d[:4]] = tr50[idx[d]]
    o = {}; b_ = base
    for y in sorted(last): o[y] = (last[y] / b_ - 1) * 100; b_ = last[y]
    return o
Y50 = yr50()
def loo(full):
    """每個 seed：拿掉年 y 後的年化（用該 run 的逐年報酬串接）"""
    o = {}
    for y in YEARS:
        vals = []
        for x in full:
            tot = 1.0
            for yy in YEARS:
                if yy != y: tot *= 1 + x["yr"].get(yy, 0) / 100
            dd = TOTD - DAYS_Y[y]
            vals.append((tot ** (245.0 / dd) - 1) * 100)
        o[y] = vals
    return o
RES["yearly"] = {}
for nm in ("1000+k（原）", "2000+k"):
    b, f = EV[nm]
    P("-- seed 組 %s --" % nm)
    P("  %-14s" % "年" + " ".join("%6s" % y[2:] for y in YEARS))
    P("  %-14s" % "0050 含息" + " ".join("%+6.0f" % Y50[y] for y in YEARS))
    bym = {y: med([x["yr"].get(y, 0) for x in b["full"]]) for y in YEARS}; fym = {y: med([x["yr"].get(y, 0) for x in f["full"]]) for y in YEARS}
    P("  %-14s" % "現行中位" + " ".join("%+6.0f" % bym[y] for y in YEARS) + "   贏0050 %d/%d" % (sum(1 for y in YEARS if bym[y] > Y50[y]), len(YEARS)))
    P("  %-14s" % "濾網中位" + " ".join("%+6.0f" % fym[y] for y in YEARS) + "   贏0050 %d/%d" % (sum(1 for y in YEARS if fym[y] > Y50[y]), len(YEARS)))
    P("  %-14s" % "Δ（濾−現行）" + " ".join("%+6.0f" % (fym[y] - bym[y]) for y in YEARS) + "   濾網贏現行 %d/%d 年" % (sum(1 for y in YEARS if fym[y] > bym[y]), len(YEARS)))
    pos = {y: sum(1 for x, z in zip(f["full"], b["full"]) if x["yr"].get(y, 0) > z["yr"].get(y, 0)) for y in YEARS}
    P("  %-14s" % "同seed濾>現行數" + " ".join("%6d" % pos[y] for y in YEARS) + "   （/%d seed）" % len(b["full"]))
    bl = loo(b["full"]); fl = loo(f["full"])
    P("  留一年法 Δ中位年化（拿掉該年）：" + " ".join("%s %+.1f" % (y[2:], med(fl[y]) - med(bl[y])) for y in YEARS) + "   （全年化 Δ %+.1f）" % (f["med"] - b["med"]))
    RES["yearly"][nm] = dict(base={y: bym[y] for y in YEARS}, filt={y: fym[y] for y in YEARS}, filt_beats_base_years=sum(1 for y in YEARS if fym[y] > bym[y]),
                             loo_d={y: med(fl[y]) - med(bl[y]) for y in YEARS})

# ---------- T4：相鄰門檻 ----------
P("")
P("== T4 相鄰門檻：排除「個股 r3 < t」（t=0 即原濾網；r3 缺值的 na 一律保留）；兩組 seed；贏隨機＝贏不濾純隨機中位")
RES["thr"] = []
for t in (-20, -10, -5, 0, 5, 10):
    flt = lambda c, t=t: not (c["sr3"] is not None and c["sr3"] < t)
    setC([c for c in BASE if flt(c)]); nc = len(C)
    row = dict(t=t, n_cands=nc, removed=N - nc)
    for nm in ("1000+k（原）", "2000+k"):
        seeds = dict(SEEDSETS)[nm]; b = EV[nm][0]
        f = evaluate(seeds, rand_med); f["n_seeds"] = len(seeds); k = three_cond(f, b, rand_med)
        row[nm] = dict(med=f["med"], lo=f["lo"], hi=f["hi"], d=k["d"], beat=f["beat"], h1=f["h1"], h2=f["h2"], dh1=k["dh1"], dh2=k["dh2"], n=f["n"], ok=(k["c1"] and k["c2"] and k["c3"]))
        P("  排除 r3<%+3d（刪 %4d 筆 %.1f%%，交易 %3d）seed %-10s 中位 %5.1f%%（%5.1f～%5.1f） Δ%+5.1f 贏隨機 %2d/%d 前半 %5.1f（Δ%+5.1f） 後半 %5.1f（Δ%+5.1f） %s" % (
            t, N - nc, 100 * (N - nc) / N, f["n"], nm, f["med"], f["lo"], f["hi"], k["d"], f["beat"], len(seeds), f["h1"], k["dh1"], f["h2"], k["dh2"],
            "三條件過" if row[nm]["ok"] else "不過"))
    RES["thr"].append(row)
setC(BASE)
# 另一個相鄰定義：用 1 個月前的個股位置（lag=1）
for c in BASE:
    st = S.stock_stage(c["code"], c["d"], lag=1); c["sst1"] = st["stage"] if st else "na"
setC([c for c in BASE if c["sst1"] != "down"]); nc = len(C)
for nm in ("1000+k（原）", "2000+k"):
    seeds = dict(SEEDSETS)[nm]; b = EV[nm][0]
    f = evaluate(seeds, rand_med); k = three_cond(f, b, rand_med)
    P("  排除「上個月個股 down」（lag=1，刪 %d 筆）seed %-10s 中位 %5.1f%%（%5.1f～%5.1f） Δ%+5.1f 贏隨機 %2d/%d 前半Δ%+5.1f 後半Δ%+5.1f %s" % (
        N - nc, nm, f["med"], f["lo"], f["hi"], k["d"], f["beat"], len(seeds), k["dh1"], k["dh2"], "三條件過" if (k["c1"] and k["c2"] and k["c3"]) else "不過"))
    RES["thr"].append(dict(t="lag1", n_cands=nc, removed=N - nc, seeds=nm, med=f["med"], d=k["d"], beat=f["beat"], dh1=k["dh1"], dh2=k["dh2"]))
setC(BASE)

# ---------- T5：同分有先打亂 ----------
P("")
P("== T5 同分有先打亂的確認")
src = open("star_rank.py").read()
P("  引擎原始碼：%s" % ("有 rng.shuffle(L) 後再 L.sort(key=keyfn)（先打亂再排序）" if "rng.shuffle(L); L.sort(key=keyfn)" in src else "找不到 shuffle→sort 片段！"))
b, f = EV["1000+k（原）"]
def trset(st): return set((t["d"], t["code"]) for t in st["tr"])
d01 = len(trset(f["full"][0]) ^ trset(f["full"][1])); d0b = len(trset(b["full"][0]) ^ trset(b["full"][1]))
setC([c for c in BASE if FD(c)]); eqn, trn = run(keyfn=cur, seed=None, cap=CAP, start=D0); sn = stats(eqn, trn)
setC(BASE); eqnb, trnb = run(keyfn=cur, seed=None, cap=CAP, start=D0); snb = stats(eqnb, trnb)
keys_per_day = [len(set(cur(c) for c in v)) for v in byday.values() if len(v) > 3]
P("  濾網 seed 1000 vs 1001 的交易集合對稱差 %d 筆（各 %d 筆）；現行 seed 1000 vs 1001 對稱差 %d 筆 → 不同 seed 確實買到不同股票" % (d01, f["full"][0]["n"], d0b))
P("  現行排序鍵只有 4 種值；候選 >3 的 %d 天裡，當天不同鍵值數中位 %d（最多 %d）→ 同分極多，打亂有實質作用" % (len(keys_per_day), med(keys_per_day), max(keys_per_day)))
P("  不打亂（seed=None，同分照代號小先）的單一路徑：現行 %.1f%%、濾網 %.1f%%（Δ%+.1f）—— 只當提醒，不採用" % (snb["cagr"], sn["cagr"], sn["cagr"] - snb["cagr"]))
RES["tie"] = dict(symdiff_filt=d01, symdiff_base=d0b, noshuffle_base=snb["cagr"], noshuffle_filt=sn["cagr"])

# ---------- T6：槽位／路徑雜訊 ----------
P("")
P("== T6 槽位／路徑雜訊")
b, f = EV["1000+k（原）"]
# 6a. 現行各路徑裡實際買到的 down 交易
dn_tr = []; ot_tr = []; per_seed_dn = []
for x in b["full"]:
    k_ = 0
    for t in x["tr"]:
        c = CK.get((t["d"], t["code"]))
        if c is not None and not FD(c): dn_tr.append(t["ret"]); k_ += 1
        else: ot_tr.append(t["ret"])
    per_seed_dn.append(k_)
def tstat(xs):
    if not xs: return "n=0"
    return "n=%d 平均 %+.2f%% 中位 %+.2f%% 勝率 %.1f%%" % (len(xs), statistics.mean(xs), statistics.median(xs), 100 * sum(1 for v in xs if v > 0) / len(xs))
P("  6a 現行 %d 條路徑裡實際買到的「個股 down」交易：每條路徑 中位 %d 筆（%d～%d）／%d 筆交易；合併 %s；其餘交易 %s" % (
    len(b["full"]), med(per_seed_dn), min(per_seed_dn), max(per_seed_dn), b["n"], tstat(dn_tr), tstat(ot_tr)))
if dn_tr:
    U, z, p = mwu(dn_tr, ot_tr); P("     down 交易 vs 其餘交易報酬 Mann-Whitney z=%+.2f p=%.3f（z<0 表示 down 交易較差）" % (z, p))
RES["down_trades"] = dict(per_seed_med=med(per_seed_dn), n=len(dn_tr), mean=statistics.mean(dn_tr) if dn_tr else None, med=statistics.median(dn_tr) if dn_tr else None,
                          win=100 * sum(1 for v in dn_tr if v > 0) / len(dn_tr) if dn_tr else None, other_mean=statistics.mean(ot_tr), other_med=statistics.median(ot_tr))
# 6b. 交易層級歸因：同 seed 濾 vs 不濾的交易集合差
rem_all = []; add_all = []; rem_dn = 0; n_rem = []; n_add = []; n_com = []
for xb, xf in zip(b["full"], f["full"]):
    tb = {(t["d"], t["code"]): t["ret"] for t in xb["tr"]}; tf = {(t["d"], t["code"]): t["ret"] for t in xf["tr"]}
    rem = [k for k in tb if k not in tf]; add = [k for k in tf if k not in tb]; com = [k for k in tb if k in tf]
    n_rem.append(len(rem)); n_add.append(len(add)); n_com.append(len(com))
    rem_dn += sum(1 for k in rem if not FD(CK[k]))
    rem_all += [tb[k] for k in rem]; add_all += [tf[k] for k in add]
P("  6b 同 seed 濾 vs 不濾的交易集合（%d seed 合併）：共同 中位 %d 筆、被換掉 %d 筆、新增 %d 筆（/%d）；被換掉的裡面真正是 down 的 %d/%d（其餘是路徑連鎖效應）" % (
    len(b["full"]),
    med(n_com), med(n_rem), med(n_add), b["n"], rem_dn, len(rem_all)))
P("     被換掉的交易 %s；新增的交易 %s" % (tstat(rem_all), tstat(add_all)))
if rem_all and add_all:
    U, z, p = mwu(add_all, rem_all); P("     新增 vs 被換掉 Mann-Whitney z=%+.2f p=%.3f" % (z, p))
RES["attrib"] = dict(common=med(n_com), removed=med(n_rem), added=med(n_add), removed_down=rem_dn, removed_total=len(rem_all),
                     rem_mean=statistics.mean(rem_all) if rem_all else None, add_mean=statistics.mean(add_all) if add_all else None)
# 6c. 安慰劑濾網 A：隨機刪同樣筆數（n_down）的「非 down」候選，100 次，每次 30 seed（1000+k）中位
seeds = dict(SEEDSETS)["1000+k（原）"]
nondown = [i for i, c in enumerate(BASE) if FD(c)]
plA = []; tA = time.time()
for j in range(NPLAC):
    rng = random.Random(7000 + j); drop = set(rng.sample(nondown, n_down))
    setC([c for i, c in enumerate(BASE) if i not in drop]); plA.append(med(cagrs(seeds)))
setC(BASE)
sA = summ(plA)
P("  6c 安慰劑濾網 A（隨機刪 %d 筆非 down 候選，%d 次，每次 %d seed 中位；%.0f 秒）：中位數的分佈 中位 %.1f%%（%.1f～%.1f，sd %.1f）；≥ 現行中位 %.1f 的 %d/%d；≥ 濾網中位 %.1f 的 %d/%d → 濾網中位落在安慰劑分佈第 %.0f 百分位" % (
    n_down, NPLAC, NSEED, time.time() - tA, sA["med"], sA["lo"], sA["hi"], sA["sd"], b["med"], sum(1 for x in plA if x >= b["med"]), NPLAC, f["med"], sum(1 for x in plA if x >= f["med"]), NPLAC, pct_in(f["med"], plA)))
P("     安慰劑 Δ（安慰劑中位 − 現行中位）：中位 %+.1f、平均 %+.1f、≥+3 的 %d/%d、≥%+.1f（濾網的 Δ）的 %d/%d" % (
    med([x - b["med"] for x in plA]), statistics.mean(plA) - b["med"], sum(1 for x in plA if x - b["med"] >= 3), NPLAC, f["med"] - b["med"], sum(1 for x in plA if x - b["med"] >= f["med"] - b["med"] - 1e-9), NPLAC))
RES["placeboA"] = dict(n=NPLAC, med=sA["med"], lo=sA["lo"], hi=sA["hi"], sd=sA["sd"], ge_filt=sum(1 for x in plA if x >= f["med"]), ge_base=sum(1 for x in plA if x >= b["med"]), pct_filt=pct_in(f["med"], plA), vals=plA)
# 6d. 安慰劑濾網 B：同一天換一筆（每筆 down 候選→刪掉同一天一筆隨機非 down），控制日期結構；前 NPLAC3 次連前後半＋三條件
plB = []; plB3 = []; tB = time.time()
down_by_day = collections.defaultdict(list)
for c in BASE:
    if not FD(c): down_by_day[c["d"]].append(c)
for j in range(NPLAC):
    rng = random.Random(8000 + j); drop = set()
    for d, L in down_by_day.items():
        pool = [id(c) for c in byday[d] if FD(c)]
        rng.shuffle(pool)
        for q in pool[:len(L)]: drop.add(q)
    setC([c for c in BASE if id(c) not in drop])
    if j < NPLAC3:
        fj = evaluate(seeds, rand_med); kj = three_cond(fj, b, rand_med); plB.append(fj["med"]); plB3.append((kj["d"], kj["c1"], kj["c2"], kj["c3"], fj["beat"], kj["dh1"], kj["dh2"]))
    else: plB.append(med(cagrs(seeds)))
setC(BASE)
sB = summ(plB)
P("  6d 安慰劑濾網 B（每筆 down 候選改刪「同一天」一筆隨機非 down，共刪 %d 筆，%d 次；%.0f 秒）：中位數分佈 中位 %.1f%%（%.1f～%.1f，sd %.1f）；≥ 濾網中位 %.1f 的 %d/%d → 第 %.0f 百分位；Δ≥+3 的 %d/%d" % (
    len(drop), NPLAC, time.time() - tB, sB["med"], sB["lo"], sB["hi"], sB["sd"], f["med"], sum(1 for x in plB if x >= f["med"]), NPLAC, pct_in(f["med"], plB), sum(1 for x in plB if x - b["med"] >= 3), NPLAC))
n3 = sum(1 for d_, c1, c2, c3, bt, _, _ in plB3 if c1 and c2 and c3)
P("     前 %d 次安慰劑 B 連前後半：三條件全過 %d/%d；Δ≥3 %d；贏隨機≥25 %d；前後半都不低於現行 %d；Δ 中位 %+.1f 前半Δ中位 %+.1f 後半Δ中位 %+.1f" % (
    NPLAC3, n3, NPLAC3, sum(1 for r in plB3 if r[1]), sum(1 for r in plB3 if r[2]), sum(1 for r in plB3 if r[3]), med([r[0] for r in plB3]), med([r[5] for r in plB3]), med([r[6] for r in plB3])))
RES["placeboB"] = dict(n=NPLAC, med=sB["med"], lo=sB["lo"], hi=sB["hi"], sd=sB["sd"], ge_filt=sum(1 for x in plB if x >= f["med"]), pct_filt=pct_in(f["med"], plB), three_pass=n3, n3=NPLAC3, vals=plB)

# ---------- T8：換成確定性排序（沒有同分雜訊）看濾網效果 ----------
P("")
P("== T8 用沒有同分的確定性排序（單一路徑，無 seed 雜訊）看濾網效果：濾 vs 不濾")
DET = [("代號小先", lambda c: (c["code"],)), ("均量大先", lambda c: (-c["v20"], c["code"])), ("低價先", lambda c: (c["px"], c["code"])), ("phi 大先再均量大", lambda c: (-c["phi"], -c["v20"], c["code"]))]
RES["det"] = []
for nm, kf in DET:
    setC(BASE); sb = stats(*run(keyfn=kf, cap=CAP, start=D0)); sb1 = stats(*run(keyfn=kf, cap=CAP, start=D0, end=H1_END)); sb2 = stats(*run(keyfn=kf, cap=CAP, start=H2_START))
    setC([c for c in BASE if FD(c)]); sf = stats(*run(keyfn=kf, cap=CAP, start=D0)); sf1 = stats(*run(keyfn=kf, cap=CAP, start=D0, end=H1_END)); sf2 = stats(*run(keyfn=kf, cap=CAP, start=H2_START))
    setC(BASE)
    P("  %-16s 不濾 %5.1f%%（前 %5.1f 後 %5.1f，n=%d） 濾 %5.1f%%（前 %5.1f 後 %5.1f，n=%d） Δ %+.1f（前 %+.1f 後 %+.1f）" % (
        nm, sb["cagr"], sb1["cagr"], sb2["cagr"], sb["n"], sf["cagr"], sf1["cagr"], sf2["cagr"], sf["n"], sf["cagr"] - sb["cagr"], sf1["cagr"] - sb1["cagr"], sf2["cagr"] - sb2["cagr"]))
    RES["det"].append(dict(name=nm, base=sb["cagr"], filt=sf["cagr"], d=sf["cagr"] - sb["cagr"], dh1=sf1["cagr"] - sb1["cagr"], dh2=sf2["cagr"] - sb2["cagr"]))


P("")
P("== 摘要（phi ≥ %s）" % PHI)
for r in RES["seedsets"]:
    P("  seed %-14s 現行 %5.1f  濾網 %5.1f  Δ%+5.1f  贏隨機 %d/%d  前半 %5.1f→%5.1f  後半 %5.1f→%5.1f  MWU p=%.3f  三條件 %s" % (
        r["name"], r["base"], r["filt"], r["d"], r["beat"], r["n"], r["h1"][0], r["h1"][1], r["h2"][0], r["h2"][1], r["mwu_p"], "過" if (r["c1"] and r["c2"] and r["c3"]) else "不過"))
for r in RES["exbull"]:
    P("  拿掉多頭 seed %-10s 現行 %5.1f 濾網 %5.1f Δ%+5.1f（濾>現行 %d/%d）" % (r["seeds"], r["base"], r["filt"], r["d"], r["filt_gt"], r["n"]))
P("  安慰劑 A：濾網中位第 %.0f 百分位（≥ 的 %d/%d）；安慰劑 B：第 %.0f 百分位（≥ 的 %d/%d），三條件全過 %d/%d" % (
    RES["placeboA"]["pct_filt"], RES["placeboA"]["ge_filt"], RES["placeboA"]["n"], RES["placeboB"]["pct_filt"], RES["placeboB"]["ge_filt"], RES["placeboB"]["n"], RES["placeboB"]["three_pass"], RES["placeboB"]["n3"]))
P("  down 交易（現行路徑實買）n=%d 平均 %+.2f%% 勝率 %.1f%% vs 其餘 平均 %+.2f%%；被換掉 vs 新增 平均 %+.2f%% vs %+.2f%%" % (
    RES["down_trades"]["n"], RES["down_trades"]["mean"] or 0, RES["down_trades"]["win"] or 0, RES["down_trades"]["other_mean"], RES["attrib"]["rem_mean"] or 0, RES["attrib"]["add_mean"] or 0))
P("")
P("（耗時 %.0f 秒）" % (time.time() - T0))
json.dump(RES, open("stagetest/v_A_stat_res_%s.json" % TAG, "w"), ensure_ascii=False, indent=1, default=float)
OUT.close()
