"""★ 加「ROIC ≥ 40% 不買」濾網（實體課：ROIC 跑太高要小心客戶 BOM 表壓力）會不會更好。"""
import sys
src = open("star_rank_roic.py").read().split("cap = 3")[0]
exec(src)
cap = 3
def setC(newC):
    global C, byday, days
    C = newC; byday = collections.defaultdict(list)
    for c in C: byday[c["d"]].append(c)
    days = sorted(byday)
base = list(C)
cur = lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1)
for nm, flt in (("全部候選（現行）", lambda c: True), ("排除 ROIC ≥ 40%", lambda c: not (c["roic"] is not None and c["roic"] >= 40)),
                ("排除 ROIC ≥ 30%", lambda c: not (c["roic"] is not None and c["roic"] >= 30)), ("只留 ROIC < 20%（含沒資料）", lambda c: c["roic"] is None or c["roic"] < 20),
                ("對照：只留 ROIC ≥ 40%", lambda c: c["roic"] is not None and c["roic"] >= 40)):
    setC([c for c in base if flt(c)])
    rs = sorted(stats(*run(seed=s, cap=cap))["cagr"] for s in range(60))
    cs = sorted(stats(*run(keyfn=cur, seed=1000 + k, cap=cap))["cagr"] for k in range(30))
    s = stats(*run(keyfn=cur, seed=1000, cap=cap))
    print("  %-26s 候選 %5d  隨機中位 %5.1f%%  現行排序中位 %5.1f%%（%5.1f～%5.1f） 回撤 %.1f%% 筆數 %d 每筆 %+.2f%% 勝率 %.0f%%" % (nm, len(C), rs[30], cs[15], cs[0], cs[-1], s["mdd"], s["n"], s["avg"], s["win"]))
