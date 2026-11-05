import sys, statistics, collections
PHI = sys.argv[1]
src = open("star_kill.py").read().split("def pct(")[0].replace('PHI = sys.argv[1] if len(sys.argv) > 1 else "0.95"', 'PHI = "%s"' % PHI)
exec(src)
NEW = lambda c: (0 if c["phi"] >= 0.9999 else 1, 0 if c["v20"] >= 2000 else 1)
pk_c = collections.Counter(); tg_c = collections.Counter(); rec = 0; now_dd = []; ret26 = []; tr50i = {d: k for k, d in enumerate(cal)}
for s in range(1000, 1100):
    eq, tr = run3(keyfn=NEW, seed=s, mstop=None)
    peak = -1; pk_d = None; m = 0; t = None; p_at = None
    for d, e in eq:
        if e > peak: peak, pk_d = e, d
        x = e / peak - 1
        if x < m: m, t, p_at = x, d, pk_d
    pk_c[p_at[:7]] += 1; tg_c[t[:7]] += 1
    last = eq[-1][1]; hi = max(e for d, e in eq if d >= t)
    pre = dict(eq)[p_at]
    rec += 1 if hi >= pre else 0
    now_dd.append((last / max(e for _, e in eq) - 1) * 100)
    e25 = [e for d, e in eq if d <= "2025-12-31"][-1]; ret26.append((last / e25 - 1) * 100)
print("phi", PHI, "新排序 100 種順序：最大回撤的高點月份", dict(pk_c.most_common(4)), "；谷底月份", dict(tg_c.most_common(4)))
print("  之後回到前高的順序 %d/100；到 2026-10-30 離最高點 中位 %.1f%%（最好 %.1f、最差 %.1f）；2026 年到 10/30 報酬 中位 %+.0f%%" % (rec, statistics.median(now_dd), max(now_dd), min(now_dd), statistics.median(ret26)))
c = [x for x in cal if "2026-01-01" <= x <= cal[-1]]
print("  0050 含息：2026 年到 10/30 %+.0f%%；2026-03～2026-07 期間最大回撤 %.1f%%" % ((tr50[tr50i[c[-1]]] / tr50[tr50i[[x for x in cal if x <= '2025-12-31'][-1]]] - 1) * 100,
      min(tr50[tr50i[d]] / max(tr50[tr50i[x]] for x in c if x <= d) - 1 for d in c if d <= "2026-08-31") * 100))
