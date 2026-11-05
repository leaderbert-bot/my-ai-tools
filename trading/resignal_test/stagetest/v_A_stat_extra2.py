"""v_A_stat_extra2：phi 0.95 安慰劑 B（同一天換一筆）改用 seed 組 2000+k（50 次），看濾網中位 38.5 的百分位"""
import sys, os, time, collections, statistics, pickle, random, bisect
SP = "/tmp/claude-0/-home-user-my-ai-tools/bb9482f7-4c31-5f24-a06a-81bc958a76a4/scratchpad"
sys.path.insert(0, SP); os.chdir(SP)
PHI = sys.argv[1] if len(sys.argv) > 1 else "0.95"; NPL = int(os.environ.get("NPL", 50))
sys.argv = ["star_rank.py", "cands.pkl", PHI]
exec(open("star_rank.py").read().split("def main():")[0])
import stage_lib as S
OUT = open("stagetest/v_A_stat_extra2_out_%s.txt" % PHI.replace(".", ""), "w")
def P(*a):
    line = " ".join(str(x) for x in a); print(line, flush=True); OUT.write(line + "\n"); OUT.flush()
for c in C:
    st = S.stock_stage(c["code"], c["d"]); c["sst"] = st["stage"] if st else "na"
BASE = list(C); D0 = days[0]; CAP = 3
FD = lambda c: c["sst"] != "down"
cur = lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1)
def setC(newC):
    global C, byday, days
    C = newC; byday = collections.defaultdict(list)
    for c in C: byday[c["d"]].append(c)
    days = sorted(byday)
def med(L): L = sorted(L); return L[len(L) // 2]
def pct_in(x, dist): dist = sorted(dist); return 100.0 * bisect.bisect_left(dist, x) / len(dist)
t0 = time.time(); seeds = list(range(2000, 2030))
setC(BASE); bm = med([stats(*run(keyfn=cur, seed=s, cap=CAP, start=D0))["cagr"] for s in seeds])
setC([c for c in BASE if FD(c)]); fm = med([stats(*run(keyfn=cur, seed=s, cap=CAP, start=D0))["cagr"] for s in seeds])
setC(BASE)
down_by_day = collections.defaultdict(list)
for c in BASE:
    if not FD(c): down_by_day[c["d"]].append(c)
pl = []
for j in range(NPL):
    rng = random.Random(9500 + j); drop = set()
    for d, L in down_by_day.items():
        pool = [id(c) for c in byday[d] if FD(c)]; rng.shuffle(pool)
        for q in pool[:len(L)]: drop.add(q)
    setC([c for c in BASE if id(c) not in drop]); pl.append(med([stats(*run(keyfn=cur, seed=s, cap=CAP, start=D0))["cagr"] for s in seeds])); setC(BASE)
pl_s = sorted(pl)
P("phi≥%s seed 組 2000+k：現行中位 %.1f、濾網中位 %.1f（Δ%+.1f）；安慰劑 B（同一天換一筆，%d 次）中位數分佈 中位 %.1f（%.1f～%.1f，sd %.1f）；≥ 濾網中位的 %d/%d → 第 %.0f 百分位；Δ≥+3 的 %d/%d  （耗時 %.0f 秒）" % (
    PHI, bm, fm, fm - bm, NPL, med(pl), pl_s[0], pl_s[-1], statistics.pstdev(pl), sum(1 for x in pl if x >= fm), NPL, pct_in(fm, pl), sum(1 for x in pl if x - bm >= 3), NPL, time.time() - t0))
