"""「本月淨值 −5% 停開新倉到月底」在新排序、舊排序、純隨機下的配對比較（同一個 seed 加 vs 不加）。"""
import sys, statistics, collections
PHI = sys.argv[1] if len(sys.argv) > 1 else "0.95"
NSEED = int(sys.argv[2]) if len(sys.argv) > 2 else 100
src = open("star_kill.py").read().split("def pct(")[0].replace('PHI = sys.argv[1] if len(sys.argv) > 1 else "0.95"', 'PHI = "%s"' % PHI).replace("NSEED = int(sys.argv[2]) if len(sys.argv) > 2 else 100", "NSEED = %d" % NSEED)
exec(src)
def yr_of(eq):
    ye = {}; base = eq[0][1]; out = {}
    for d, e in eq: ye[d[:4]] = e
    for y in sorted(ye): out[y] = (ye[y] / base - 1) * 100; base = ye[y]
    return out
def summarize(lab, pairs):
    a = [p[0] for p in pairs]; b = [p[1] for p in pairs]
    d = sorted(x - y for x, y in zip(a, b))
    ma = sorted(p[2] for p in pairs); mb = sorted(p[3] for p in pairs)
    yw = collections.Counter(); yt = collections.Counter()
    for p in pairs:
        for y in p[4]:
            if y in p[5]:
                yt[y] += 1; yw[y] += 1 if p[4][y] > p[5][y] + 1e-9 else 0
    ys = sorted(yt)
    print("phi %s %-30s 不加：年化中位 %5.1f%%（%5.1f～%5.1f）回撤中位 %6.1f%%｜加：年化中位 %5.1f%%（%5.1f～%5.1f）回撤中位 %6.1f%%｜配對差（加−不加）中位 %+5.1f 點、%d/%d 個順序變好；回撤差中位 %+5.1f 點" % (
        PHI, lab, statistics.median(b), min(b), max(b), statistics.median(mb), statistics.median(a), min(a), max(a), statistics.median(ma),
        statistics.median(d), sum(1 for x in d if x > 0), len(d), statistics.median(x - y for x, y in zip(ma, mb))))
    print("      逐年「加」比「不加」好的順序比例：" + " ".join("%s %d%%" % (y[2:], round(100 * yw[y] / yt[y])) for y in ys))
NEW = lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1)
OLD = lambda c: -c["v20"]
for lab, kf, seeds in (("新排序（同分隨機）", NEW, list(range(1000, 1000 + NSEED))), ("純隨機", None, list(range(NSEED))), ("舊排序（均量大先）", OLD, [None])):
    pairs = []
    for s in seeds:
        e1, t1 = run3(keyfn=kf, seed=s, mstop=-0.05); e0, t0 = run3(keyfn=kf, seed=s, mstop=None)
        s1, s0 = stats(e1, t1), stats(e0, t0)
        pairs.append((s1["cagr"], s0["cagr"], s1["mdd"], s0["mdd"], yr_of(e1), yr_of(e0)))
    summarize(lab, pairs)
