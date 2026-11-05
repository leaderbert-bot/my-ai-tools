"""任務 B 補充：(1) 產業 price 事件統計排除 2021；(2) 產業 mom60>0 vs ≤0 逐年；(3) 預設帳戶實際買的 306 筆按產業位置的每筆報酬（run3＝引擎 run 多記錄每筆交易對應的訊號）。
結果 append 到 stagetest/b_mgk_out.txt。"""
import sys, os, collections, statistics, math
SP = "/tmp/claude-0/-home-user-my-ai-tools/bb9482f7-4c31-5f24-a06a-81bc958a76a4/scratchpad"
sys.path.insert(0, SP); os.chdir(SP)
SRC = open('mgk_test.py').read().split('b = run([])')[0]; exec(SRC)
RUN_SRC = SRC[SRC.index('def run(S, seed=None'):]
R3 = (RUN_SRC.replace('def run(S, seed=None,', 'def run3(S, seed=None,')
      .replace('out=cal[i + HOLD], **{"in": s["px"]}))', 'out=cal[i + HOLD], sig=s, **{"in": s["px"]}))')
      .replace('done.append((c / p["in"] - 1) * 100 - COST * 100)', 'done.append((c / p["in"] - 1) * 100 - COST * 100); TRADES.append((p["sig"], d, done[-1]))'))
assert R3.count('TRADES.append') == 1 and R3.count('sig=s') == 1
exec(R3)
import stage_lib as S
OUT = open("stagetest/b_mgk_out.txt", "a")
def P(*a):
    line = " ".join(str(x) for x in a); print(line, flush=True); OUT.write(line + "\n")
def fwd60(s):
    i = idx[s['d']]; j = i + HOLD
    if j >= len(cal): return None
    e = close_near(s['code'], cal[j])
    if not e or not tr50[i] or not tr50[j]: return None
    return (e / s['px'] - 1) * 100 - (tr50[j] / tr50[i] - 1) * 100
for s in sig:
    st = S.ind_stage(s['code'], s['d']); s['ist'] = st['stage'] if st else 'na'; s['inew'] = bool(st and st['new_price'])
    s['imom'] = st['mom60'] if st else None; s['irev3'] = st['rev3'] if st else None
    ss = S.stock_stage(s['code'], s['d']); s['sst'] = ss['stage'] if ss else 'na'; s['fx60'] = fwd60(s)
SX = [s for s in sig if s['r60x'] > 20]
def m(L): return statistics.median(L) if L else float('nan')
def evt(rows):
    f = [s['fx60'] for s in rows if s['fx60'] is not None]
    if not f: return "n     0"
    h1 = [x['fx60'] for x in rows if x['fx60'] is not None and x['d'] < "2021-07-01"]; h2 = [x['fx60'] for x in rows if x['fx60'] is not None and x['d'] >= "2021-07-01"]
    se = statistics.pstdev(f) / math.sqrt(len(f)) if len(f) > 1 else float('nan')
    return "n %5d  中位 %+6.2f  平均 %+6.2f（±%.2f）  贏0050 %4.1f%%   前半中位 %+6.2f（n %4d） 後半 %+6.2f（n %4d）" % (len(f), m(f), statistics.mean(f), se, 100 * sum(1 for x in f if x > 0) / len(f), m(h1), len(h1), m(h2), len(h2))
P("")
P("=" * 120)
P("== 補充 1：產業 price／new_price 的訊號集中在 2021（先漲版 37 筆裡 25 筆、new_price 27 筆裡 21 筆）→ 排除 2021 再看事件統計")
for nm, SS in (("先漲版", SX), ("全部版", sig)):
    for gn, f in (("產業 price（全部年）", lambda s: s['ist'] == 'price'), ("產業 price，排除 2021", lambda s: s['ist'] == 'price' and s['d'][:4] != '2021'),
                  ("產業 new_price，排除 2021", lambda s: s['inew'] and s['d'][:4] != '2021'), ("產業 price/vol/vol?，排除 2021", lambda s: s['ist'] in ('price', 'vol', 'vol?') and s['d'][:4] != '2021'),
                  ("全部，排除 2021", lambda s: s['d'][:4] != '2021'), ("全部，只 2021", lambda s: s['d'][:4] == '2021'), ("產業 price，只 2021", lambda s: s['ist'] == 'price' and s['d'][:4] == '2021')):
        P("  %-6s %-32s %s" % (nm, gn, evt([s for s in SS if f(s)])))
P("")
P("== 補充 2：產業 mom60 > 0 vs ≤ 0 逐年（60 日超額：n／中位／贏0050%）；看方向是不是每年一致")
for nm, SS in (("先漲版", SX), ("全部版", sig)):
    P("  -- %s --" % nm); pos_better = 0; ny = 0
    for y in sorted(set(s['d'][:4] for s in SS)):
        a = [s['fx60'] for s in SS if s['d'][:4] == y and s['fx60'] is not None and s['imom'] is not None and s['imom'] > 0]
        b = [s['fx60'] for s in SS if s['d'][:4] == y and s['fx60'] is not None and s['imom'] is not None and s['imom'] <= 0]
        if a and b:
            ny += 1; pos_better += (m(a) > m(b))
        P("    %s  mom60>0: n %3d 中位 %+6.2f 贏 %3.0f%%   | mom60≤0: n %3d 中位 %+6.2f 贏 %3.0f%%   %s" % (y, len(a), m(a), 100 * sum(1 for x in a if x > 0) / len(a) if a else float('nan'), len(b), m(b), 100 * sum(1 for x in b if x > 0) / len(b) if b else float('nan'), ">0 中位較高" if (a and b and m(a) > m(b)) else ""))
    P("    >0 組中位較高的年數 %d/%d（兩組都有資料的年）" % (pos_better, ny))
P("")
P("== 補充 3：預設 MGK 帳戶（先漲版、−r60x 排序、不打亂）實際買進的 306 筆，按位置分組的每筆報酬（含成本、絕對報酬 %，非超額）")
TRADES = []; r = run3(SX); assert r['n'] == 306, r['n']
P("  帳戶年化 %.1f%% 筆數 %d 每筆 %+.2f%% 勝率 %.0f%%（與正式表一致）" % (r['cagr'], r['n'], r['avg'], r['win']))
def tstat(rows):
    f = [x for _, _, x in rows]
    if not f: return "n   0"
    return "n %3d  平均 %+6.2f%%  中位 %+6.2f%%  勝率 %3.0f%%  合計貢獻（Σ每筆%%） %+7.0f" % (len(f), statistics.mean(f), m(f), 100 * sum(1 for x in f if x > 0) / len(f), sum(f))
for gn, f in (("全部 306 筆", lambda s: True),) + tuple(("產業 %s" % k, (lambda k: lambda s: s['ist'] == k)(k)) for k in ("price", "vol", "vol?", "flat", "down", "na")) + (
        ("產業 new_price", lambda s: s['inew']), ("產業 mom60>0", lambda s: s['imom'] is not None and s['imom'] > 0), ("產業 mom60≤0", lambda s: s['imom'] is not None and s['imom'] <= 0),
        ("個股 up", lambda s: s['sst'] == 'up'), ("個股 非 up", lambda s: s['sst'] != 'up'), ("個股 down", lambda s: s['sst'] == 'down')):
    P("  %-20s %s" % (gn, tstat([t for t in TRADES if f(t[0])])))
P("  逐年買進筆數（產業 price/vol/vol?/flat/down/na）：")
for y in sorted(set(t[0]['d'][:4] for t in TRADES)):
    ty = [t for t in TRADES if t[0]['d'][:4] == y]; cc = collections.Counter(t[0]['ist'] for t in ty)
    P("    %s n=%3d  %s   平均每筆 %+6.2f%%" % (y, len(ty), " ".join("%s %2d" % (k[:4], cc[k]) for k in ("price", "vol", "vol?", "flat", "down", "na")), statistics.mean(x for _, _, x in ty)))
# 一天訊號數 vs 槽位：預設帳戶有多少訊號因滿槽／重複而沒買
bought = set((t[0]['code'], t[0]['d']) for t in TRADES)
P("  先漲版 543 筆訊號裡實際買進 %d 筆（%.0f%%）；沒買的 %d 筆（滿槽、已持有同股、或最後 60 日內）" % (len(bought), 100 * len(bought) / len(SX), len(SX) - len(bought)))
P("  沒買的訊號事件統計：" + evt([s for s in SX if (s['code'], s['d']) not in bought]))
P("  有買的訊號事件統計：" + evt([s for s in SX if (s['code'], s['d']) in bought]))
OUT.close()
