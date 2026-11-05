"""v_A_stat_extra：補兩個獨立檢查（phi 0.95）
 (1) 安慰劑濾網 A 改用 seed 組 2000+k（50 次）→ 濾網在 2000+k 的中位 38.5 落在安慰劑分佈的百分位
 (2) 純隨機排序 100 條路徑裡實際買到的「個股 down」交易 vs 其餘交易（與現行排序無關的交易層級檢查）"""
import sys, os, time, collections, statistics, pickle, random, bisect, json, math
SP = "/tmp/claude-0/-home-user-my-ai-tools/bb9482f7-4c31-5f24-a06a-81bc958a76a4/scratchpad"
sys.path.insert(0, SP); os.chdir(SP)
PHI = sys.argv[1] if len(sys.argv) > 1 else "0.95"; NPL = int(os.environ.get("NPL", 50))
sys.argv = ["star_rank.py", "cands.pkl", PHI]
exec(open("star_rank.py").read().split("def main():")[0])
import stage_lib as S
OUT = open("stagetest/v_A_stat_extra_out_%s.txt" % PHI.replace(".", ""), "w")
def P(*a):
    line = " ".join(str(x) for x in a); print(line, flush=True); OUT.write(line + "\n"); OUT.flush()
for c in C:
    st = S.stock_stage(c["code"], c["d"]); c["sst"] = st["stage"] if st else "na"
BASE = list(C); D0 = days[0]; CAP = 3
FD = lambda c: c["sst"] != "down"; n_down = sum(1 for c in BASE if not FD(c))
CK = {(c["d"], c["code"]): c for c in BASE}
cur = lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1)
def setC(newC):
    global C, byday, days
    C = newC; byday = collections.defaultdict(list)
    for c in C: byday[c["d"]].append(c)
    days = sorted(byday)
def med(L): L = sorted(L); return L[len(L) // 2]
def pct_in(x, dist): dist = sorted(dist); return 100.0 * bisect.bisect_left(dist, x) / len(dist)
t0 = time.time()
seeds = list(range(2000, 2030))
setC(BASE); bm = med([stats(*run(keyfn=cur, seed=s, cap=CAP, start=D0))["cagr"] for s in seeds])
setC([c for c in BASE if FD(c)]); fm = med([stats(*run(keyfn=cur, seed=s, cap=CAP, start=D0))["cagr"] for s in seeds])
nondown = [i for i, c in enumerate(BASE) if FD(c)]; pl = []
for j in range(NPL):
    rng = random.Random(9000 + j); drop = set(rng.sample(nondown, n_down))
    setC([c for i, c in enumerate(BASE) if i not in drop]); pl.append(med([stats(*run(keyfn=cur, seed=s, cap=CAP, start=D0))["cagr"] for s in seeds]))
setC(BASE)
pl_s = sorted(pl)
P("(1) phi≥%s seed 組 2000+k（30 seed）：現行中位 %.1f、濾網中位 %.1f（Δ%+.1f）；安慰劑 A（隨機刪 %d 筆非 down，%d 次）中位數分佈 中位 %.1f（%.1f～%.1f，sd %.1f）；安慰劑 ≥ 濾網中位的 %d/%d → 濾網落在第 %.0f 百分位；安慰劑 Δ≥+3 的 %d/%d" % (
    PHI, bm, fm, fm - bm, n_down, NPL, med(pl), pl_s[0], pl_s[-1], statistics.pstdev(pl), sum(1 for x in pl if x >= fm), NPL, pct_in(fm, pl), sum(1 for x in pl if x - bm >= 3), NPL))
# (2) 純隨機路徑裡的 down 交易
dn = []; ot = []; per = []
for s in range(100):
    eq, tr = run(seed=s, cap=CAP, start=D0); k = 0
    for t in tr:
        c = CK.get((t["d"], t["code"]))
        if c is not None and not FD(c): dn.append(t["ret"]); k += 1
        else: ot.append(t["ret"])
    per.append(k)
def tstat(xs): return "n=%d 平均 %+.2f%% 中位 %+.2f%% 勝率 %.1f%%" % (len(xs), statistics.mean(xs), statistics.median(xs), 100 * sum(1 for v in xs if v > 0) / len(xs))
P("(2) 純隨機排序 100 條路徑實際買到的「個股 down」交易：每條 中位 %d 筆（%d～%d）；合併 %s；其餘交易 %s" % (med(per), min(per), max(per), tstat(dn), tstat(ot)))
P("（耗時 %.0f 秒）" % (time.time() - t0))
