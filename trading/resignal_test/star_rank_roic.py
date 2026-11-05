"""★ 候選排序再測一鍵：優分析的「ROIC 創 8 季新高」當第一／第二排序鍵。用 star_rank.py 的引擎與同一批候選。"""
import sys, json, glob, os, collections, bisect, statistics, random, pickle
sys.argv = ["star_rank.py", "cands.pkl", sys.argv[1] if len(sys.argv) > 1 else "0.95"]
src = open("star_rank.py").read().split("def main():")[0]
exec(src)
from datetime import date
F = collections.defaultdict(dict)
for f in glob.glob("mopsfin/mopsfin_*.json"):
    nm = os.path.basename(f)[:-5].split("_"); q = "%dQ%s" % (int(nm[2]) + 1911, nm[3])
    for c, r in json.load(open(f))["rows"].items(): F[c][q] = r
def qprev(q, k=1):
    y, n = int(q[:4]), int(q[5]); n -= k
    while n <= 0: n += 4; y -= 1
    return "%dQ%d" % (y, n)
def num(x): return float(x) if isinstance(x, (int, float)) else None
def cum(c, q, k):
    r = F[c].get(q); return num(r.get(k)) if r else None
def ttm(c, q, k):
    a = cum(c, q, k); n = int(q[5])
    if a is None: return None
    if n == 4: return a
    y4 = cum(c, "%dQ4" % (int(q[:4]) - 1), k); ly = cum(c, qprev(q, 4), k)
    return None if (y4 is None or ly is None) else a + y4 - ly
def roic(c, q):
    op = ttm(c, q, "op"); a = cum(c, q, "assets"); cl = cum(c, q, "cl")
    return None if (op is None or a is None or cl is None or a - cl <= 0) else op / (a - cl) * 100
def due(q):
    y, n = int(q[:4]), int(q[5]); return date(y + 1, 3, 31).isoformat() if n == 4 else [None, date(y, 5, 15), date(y, 8, 14), date(y, 11, 14)][n].isoformat()
DUE = {}
def avail_q(c, d):
    qs = sorted(F.get(c, {})); best = None
    for q in qs:
        if due(q) < d: best = q
    return best
MC = {}
def flags(c, d):
    q = avail_q(c, d)
    if not q: return (0, 0, None)
    k = (c, q)
    if k not in MC:
        R = [roic(c, qprev(q, j)) for j in range(9)]
        hi8 = 1 if (None not in R and R[0] > max(R[1:]) and R[0] > 0) else 0
        up2 = 1 if (None not in R[:3] and R[0] > R[1] > R[2]) else 0
        MC[k] = (hi8, up2, R[0])
    return MC[k]
nf = collections.Counter()
for c in C:
    h, u, r = flags(c["code"], c["d"]); c["roic8"] = h; c["roic_up2"] = u; c["roic"] = r
    nf["hi8"] += h; nf["up2"] += u; nf["has"] += 1 if r is not None else 0
print("候選 %d 筆，有 ROIC 的 %d，ROIC 創 8 季新高 %d（%.0f%%），連升 2 季 %d" % (len(C), nf["has"], nf["hi8"], 100 * nf["hi8"] / len(C), nf["up2"]))
cap = 3
rs = sorted(stats(*run(seed=s, cap=cap))["cagr"] for s in range(100)); rand_med = rs[50]
print("隨機 100 次中位 %.1f%%（%.1f～%.1f）" % (rand_med, rs[0], rs[-1]))
TIE = {
 "創新高優先，同級均量大先（現行）": lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1),
 "ROIC 8 季新高優先": lambda c: (0 if c["roic8"] else 1,),
 "ROIC 8 季新高優先，再創新高，再均量": lambda c: (0 if c["roic8"] else 1, 0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1),
 "創新高優先，再 ROIC 8 季新高，再均量": lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["roic8"] else 1, 0 if c["v20"] >= 2000 else 1),
 "創新高優先，再均量，再 ROIC": lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1, 0 if c["roic8"] else 1),
 "ROIC 連升 2 季優先": lambda c: (0 if c["roic_up2"] else 1,),
 "ROIC 高的先（連續值）": lambda c: (-(c["roic"] if c["roic"] is not None else -999),),
 "ROIC 低的先（對照）": lambda c: ((c["roic"] if c["roic"] is not None else 999),),
 "沒 ROIC 新高的先（對照）": lambda c: (1 if c["roic8"] else 0,),
}
for nm, kf in TIE.items():
    cs = sorted(stats(*run(keyfn=kf, seed=1000 + k, cap=cap))["cagr"] for k in range(30))
    s = stats(*run(keyfn=kf, seed=1000, cap=cap)); h1 = stats(*run(keyfn=kf, seed=1000, cap=cap, end="2021-12-31")); h2 = stats(*run(keyfn=kf, seed=1000, cap=cap, start="2022-01-03"))
    print("  %-34s 中位 %5.1f%% （%5.1f～%5.1f） 贏隨機 %2d/30  回撤 %.1f%% 筆數 %d 勝率 %.0f%% 每筆 %+.2f%%  前半 %.1f%% 後半 %.1f%%" % (nm, cs[15], cs[0], cs[-1], sum(1 for x in cs if x > rand_med), s["mdd"], s["n"], s["win"], s["avg"], h1["cagr"], h2["cagr"]))
