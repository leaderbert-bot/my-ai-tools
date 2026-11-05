import sys, statistics, collections, math
PHI = sys.argv[1]
src = open("star_kill.py").read().split("def pct(")[0].replace('PHI = sys.argv[1] if len(sys.argv) > 1 else "0.95"', 'PHI = "%s"' % PHI)
exec(src)
def dd(eq):
    pk = -1; m = 0; t = None
    for d, e in eq:
        pk = max(pk, e); x = e / pk - 1
        if x < m: m, t = x, d
    return m * 100, t
def half(eq, a, b):
    E = [(d, e) for d, e in eq if a <= d <= b]
    yrs = (cal.index(E[-1][0]) - cal.index(E[0][0])) / 245.0
    return ((E[-1][1] / E[0][1]) ** (1 / yrs) - 1) * 100
RULES = [
  ("純隨機", None),
  ("只用「創新高優先」", lambda c: (0 if c["phi"] >= 0.9999 else 1,)),
  ("只用「均量 ≥ 2000 張優先」", lambda c: (0 if c["v20"] >= 2000 else 1,)),
  ("新排序（兩個都用）", lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1)),
  ("均量分 4 級（≥5000／≥2000／≥1000／其他）", lambda c: (0 if c["v20"] >= 5000 else (1 if c["v20"] >= 2000 else (2 if c["v20"] >= 1000 else 3)),)),
  ("均量分 4 級再創新高", lambda c: (0 if c["v20"] >= 5000 else (1 if c["v20"] >= 2000 else (2 if c["v20"] >= 1000 else 3)), 0 if c["phi"] >= 0.9999 else 1)),
  ("離一年高最遠的先（phi 小先，對照）", lambda c: (round(c["phi"], 3),)),
]
print("phi", PHI, "（100 種同分順序；不加月停；6 槽、抱 20 天、每天最多 3 檔）")
print("%-30s %-24s %-26s %-16s %-14s %s" % ("排序", "年化 中位（5%～95%）", "回撤 中位（最好～最差）", "年化÷回撤 中位", "前半／後半", "谷底在 2026-07 的比例"))
for lab, kf in RULES:
    R = []
    for s in range(1000, 1100):
        eq, tr = run3(keyfn=kf, seed=s, mstop=None)
        st = stats(eq, tr); m, t = dd(eq)
        R.append((st["cagr"], m, t, half(eq, cal[0], "2021-12-31"), half(eq, "2022-01-03", cal[-1])))
    cg = sorted(r[0] for r in R); md = sorted(r[1] for r in R); ca = sorted(r[0] / -r[1] for r in R)
    print("%-30s %5.1f%%（%5.1f～%5.1f）    %6.1f%%（%6.1f～%6.1f）     %5.2f            %5.1f／%5.1f    %d%%" % (
        lab, cg[50], cg[5], cg[94], md[50], md[-1], md[0], ca[50], statistics.median(r[3] for r in R), statistics.median(r[4] for r in R), sum(1 for r in R if r[2] and r[2][:7] == "2026-07")))
