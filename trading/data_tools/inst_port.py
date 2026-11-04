"""★ 6 槽帳戶模擬：排除「法人 5 日合計／均量 ≥ 0.5」（擁擠）的訊號，CAGR／回撤有沒有變好。"""
import json, pickle, statistics, sys
import sim
R = json.load(open('dl/inst_feat.json'))['rows']
feat = {(r['code'], r['sig']): r for r in R if r['strat'] == 'fundhi'}
TR0 = list(sim.TR)
print("★ 交易 %d 筆，有法人特徵的 %d 筆" % (len(TR0), sum(1 for t in TR0 if (t['code'], t['sig']) in feat)))
def go(nm, keep):
    sim.TR[:] = [t for t in TR0 if keep(feat.get((t['code'], t['sig'])))]
    eq, tr, blocked, n_add = sim.run('base')
    s = sim.stats(eq, tr)
    print("%-36s 訊號 %3d 成交 %3d  CAGR %5.1f%%  MDD %6.1f%%  勝率 %.0f%%  每筆 %+.2f%%  擠掉 %d" % (nm, len(sim.TR), s['n'], s['cagr'], s['mdd'], s['win'], s['avg'], blocked))
    return s
rows = [("基準（全部）", lambda f: True),
        ("排除 法人5日/均量 ≥ 0.5", lambda f: not (f and (f['r5'] or 0) >= 0.5)),
        ("排除 法人5日/均量 ≥ 0.3", lambda f: not (f and (f['r5'] or 0) >= 0.3)),
        ("排除 法人5日/均量 ≥ 1.0", lambda f: not (f and (f['r5'] or 0) >= 1.0)),
        ("只留 外資前5日賣超", lambda f: (f is None) or f['f5'] < 0),
        ("排除 投信連買≥3", lambda f: not (f and f['tc'] >= 3)),
        ("只留 外資+投信前5日都賣", lambda f: (f is None) or (f['f5'] < 0 and f['t5'] < 0))]
res = {}
for nm, k in rows: res[nm] = go(nm, k)
# 逐年：基準 vs 排除 ≥0.5
b = res["基準（全部）"]['yr']; a = res["排除 法人5日/均量 ≥ 0.5"]['yr']
print("\n逐年報酬 基準 vs 排除≥0.5：")
for y in sorted(b): print("  %s  %+6.1f%%  %+6.1f%%  %s" % (y, b[y], a.get(y, 0), "✓" if a.get(y, 0) > b[y] else ""))
