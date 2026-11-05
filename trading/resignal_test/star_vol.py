"""均量大先（雷達 1024zh 改回）的分佈：用「均量分 8 級、同級隨機」近似，100 種順序；不加月停 vs 加月停配對；停用指標。"""
import sys, statistics, collections
PHI = sys.argv[1]
src = open("star_kill.py").read().split("MS = None if")[0].replace('PHI = sys.argv[1] if len(sys.argv) > 1 else "0.95"', 'PHI = "%s"' % PHI)
exec(src)
TIERS = [50000, 20000, 10000, 5000, 3000, 2000, 1000, 500]
def tier(v):
    for k, t in enumerate(TIERS):
        if v >= t: return k
    return len(TIERS)
VOL8 = lambda c: (tier(c["v20"]),)
OLD = lambda c: -c["v20"]
def show(lab, M):
    cg = sorted(m["cagr"] for m in M); md = sorted(m["mdd"] for m in M)
    print("\n==== phi %s %s（%d 種順序）" % (PHI, lab, len(M)))
    print("年化：中位 %.1f%%、5%% 分位 %.1f、最低 %.1f、最高 %.1f" % (pct(cg, 50), pct(cg, 5), cg[0], cg[-1]))
    print("最大回撤：中位 %.1f%%、80%% 好於 %.1f、95%% 好於 %.1f、最差 %.1f、最好 %.1f；谷底 %s" % (pct(md, 50), pct(md, 20), pct(md, 5), md[0], md[-1], dict(collections.Counter(m["trough"][:7] for m in M).most_common(4))))
    for key, nm in (("w30", "滾動 30 筆勝率 %"), ("a30", "滾動 30 筆平均每筆 %")):
        mins = sorted(min(m[key]) for m in M); pooled = [x for m in M for x in m[key]]
        print("%s：路徑最低值 中位 %.1f、最差 %.1f；所有時間點 5%% 分位 %.1f、1%% 分位 %.1f" % (nm, pct(mins, 50), mins[0], pct(pooled, 5), pct(pooled, 1)))
    sk = sorted(m["streak"] for m in M)
    print("最長連虧：中位 %d、95%% 分位 %d、最多 %d" % (pct(sk, 50), pct(sk, 95), sk[-1]))
import sys as _s
M0 = [metrics(*run3(keyfn=VOL8, seed=s, mstop=None)) for s in range(1000, 1100)]
show("均量 8 級同級隨機（不加月停）", M0)
M1 = [metrics(*run3(keyfn=VOL8, seed=s, mstop=-0.05)) for s in range(1000, 1100)]
d = sorted(a["cagr"] - b["cagr"] for a, b in zip(M1, M0)); dd = sorted(a["mdd"] - b["mdd"] for a, b in zip(M1, M0))
print("加「本月 −5%% 停開新倉到月底」：年化差中位 %+.1f 點、%d/100 變好；回撤差中位 %+.1f 點、%d/100 變淺" % (statistics.median(d), sum(1 for x in d if x > 0), statistics.median(dd), sum(1 for x in dd if x > 0)))
for lab, ms in (("均量大先（確定，不加月停）", None), ("均量大先（確定，加月停）", -0.05)):
    m = metrics(*run3(keyfn=OLD, seed=None, mstop=ms))
    print("%s：年化 %.1f%%、回撤 %.1f%%（谷底 %s）、30 筆勝率最低 %.1f%%、30 筆平均最低 %.1f%%、最長連虧 %d" % (lab, m["cagr"], m["mdd"], m["trough"], min(m["w30"]), min(m["a30"]), m["streak"]))
