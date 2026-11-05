"""任務 B：產業循環位置（stage_lib / stage_data.pkl）對 MGK（股價先漲 >20 點＋營收第一次跳升）有沒有幫助。10 年回測 2016-06-01～2026-10-30。
引擎：mgk_test.py（10 槽 × 10%、抱 60 個交易日收盤賣、閒錢 0050 含息、成本 0.47%），重用方式照 cycle_stage_test.py 第 5 行。
run2 = 引擎 run() 只改「排序那一行」：keyfn 給了就「先 shuffle（seed）再 sort(keyfn)」→ 規則決定第一排序、同分隨機（30 seed）；
純隨機 = 引擎原寫法 run(S, seed=k)（整天打亂，30 次＝seed 0～29，與使用者 11/05 的 43.9% 同一套）；另報純隨機 100 次中位當對照。
用法：cd SP && NSEED=3 NRAND=5 OUTF=stagetest/_b_try.txt python3 stagetest/b_mgk.py（試跑）；python3 stagetest/b_mgk.py（全部）"""
import sys, os, time, collections, statistics, pickle, random, bisect, json, math
SP = "/tmp/claude-0/-home-user-my-ai-tools/bb9482f7-4c31-5f24-a06a-81bc958a76a4/scratchpad"
sys.path.insert(0, SP); os.chdir(SP)
NSEED = int(os.environ.get("NSEED", 30)); NRAND = int(os.environ.get("NRAND", 100))
OUTF = os.environ.get("OUTF", "stagetest/b_mgk_out.txt")
T0 = time.time()
SRC = open('mgk_test.py').read().split('b = run([])')[0]
exec(SRC)                                   # 借資料載入、sig、run()、close_near()、tr50、c50、avail()
OLD = 'if rng: rng.shuffle(L)\n        else: L.sort(key=lambda s: -s["r60x"])'
RUN_SRC = SRC[SRC.index('def run(S, seed=None'):]
assert RUN_SRC.count(OLD) == 1 and RUN_SRC.count('def run(') == 1, "引擎 run() 文字與預期不同"
exec(RUN_SRC.replace('def run(S, seed=None,', 'def run2(S, keyfn=None, seed=None,')
             .replace(OLD, 'if rng: rng.shuffle(L)\n        if keyfn is not None: L.sort(key=keyfn)\n        elif not rng: L.sort(key=lambda s: -s["r60x"])'))
import stage_lib as S
OUT = open(OUTF, "w")
def P(*a):
    line = " ".join(str(x) for x in a); print(line, flush=True); OUT.write(line + "\n"); OUT.flush()
H1_END = "2021-06-30"; H2_START = "2021-07-01"
ST_ORDER = ("price", "vol", "vol?", "flat", "down", "na"); SST_ORDER = ("up", "vol", "vol?", "flat", "down", "na"); PV = ("price", "vol", "vol?")

# ---------- 0. 自我檢查：run2 不給 keyfn 時與引擎 run 完全相同；keyfn=−r60x（r60x 幾乎無同分）時與預設排序相同 ----------
SX = [s for s in sig if s['r60x'] > 20]
assert run2(SX) == run(SX) and run2(SX, seed=3) == run(SX, seed=3), "run2 與引擎 run 不一致"
chk = run2(SX, keyfn=lambda s: (-s['r60x'],), seed=7); base0 = run(SX)
P("自我檢查：run2(keyfn=−r60x, seed=7) 年化 %.4f%% vs 引擎預設 run 年化 %.4f%%（應相同；r60x 同分數 %d）" % (chk['cagr'], base0['cagr'], len(SX) - len(set((s['d'], s['r60x']) for s in SX))))

# ---------- 1. 每筆訊號附產業／族群／個股位置 ＋ 60 日超額 ----------
def fwd60(s):
    i = idx[s['d']]; j = i + HOLD
    if j >= len(cal): return None
    e = close_near(s['code'], cal[j])
    if not e or not tr50[i] or not tr50[j]: return None
    return (e / s['px'] - 1) * 100 - (tr50[j] / tr50[i] - 1) * 100
for s in sig:
    st = S.ind_stage(s['code'], s['d']); s['ind'] = S.ind_of(s['code'])
    s['ist'] = st['stage'] if st else 'na'; s['inew'] = bool(st and st['new_price'])
    s['irev3'] = st['rev3'] if st else None; s['ibr'] = st['breadth'] if st else None
    s['igm'] = st['gm_d'] if st else None; s['imom'] = st['mom60'] if st else None; s['iprev'] = st['prev_stage'] if st else None
    g = S.grp_stages(s['code'], s['d']); s['ingrp'] = bool(g); s['gprice'] = any(x['stage'] == 'price' for _, x in g)
    ss = S.stock_stage(s['code'], s['d']); s['sst'] = ss['stage'] if ss else 'na'
    s['fx60'] = fwd60(s)
SETS = [("先漲版（r60x>20）", SX), ("全部版（第一次跳升，不管先漲）", sig)]
P("=" * 120)
P("任務 B：產業循環位置對 MGK 的幫助（引擎 mgk_test.py；訊號＝營收 yoy≥30% 且 ≥ 前 23 月最高、12 月內第一次；公布後（隔月 11 日起）第一個交易日收盤買、抱 60 日）")
P("訊號 %d 筆（%s～%s），先漲 >20 點 %d 筆；0050 含息同期 年化 %.1f%% 回撤 %.1f%%" % (len(sig), min(s['d'] for s in sig), max(s['d'] for s in sig), len(SX), run([])['cagr'], run([])['mdd']))
B50 = run([])
for nm, SS in SETS:
    N = len(SS); ci = collections.Counter(s['ist'] for s in SS); cs = collections.Counter(s['sst'] for s in SS)
    na = [s for s in SS if s['ist'] == 'na']
    P("")
    P("== %s：%d 筆；有訊號天數 %d，一天訊號數中位 %d、最多 %d" % (nm, N, len(set(s['d'] for s in SS)), statistics.median(collections.Counter(s['d'] for s in SS).values()), max(collections.Counter(s['d'] for s in SS).values())))
    P("  產業位置覆蓋 %d/%d（%.1f%%）；查不到 %d 筆（代號不在 industry_map %d＝下市／新上市股，在 map 但該月產業成員 <6 檔 %d）" % (N - len(na), N, 100 * (N - len(na)) / N, len(na), sum(1 for s in na if s['ind'] is None), sum(1 for s in na if s['ind'] is not None)))
    P("  產業位置分佈：" + "  ".join("%s %d（%.1f%%）" % (k, ci[k], 100 * ci[k] / N) for k in ST_ORDER) + "；new_price（剛進入價漲期）%d 筆；產業 mom60>0 %d 筆、≤0 %d 筆、無 %d 筆" % (
        sum(s['inew'] for s in SS), sum(1 for s in SS if s['imom'] is not None and s['imom'] > 0), sum(1 for s in SS if s['imom'] is not None and s['imom'] <= 0), sum(1 for s in SS if s['imom'] is None)))
    P("  個股位置分佈：" + "  ".join("%s %d（%.1f%%）" % (k, cs[k], 100 * cs[k] / N) for k in SST_ORDER))
    P("  族群（groups.csv，成員今天定的，有事後之見，只當參考）：在族群表 %d 筆（%.1f%%），任一族群 price %d 筆（%.1f%%）" % (sum(s['ingrp'] for s in SS), 100 * sum(s['ingrp'] for s in SS) / N, sum(s['gprice'] for s in SS), 100 * sum(s['gprice'] for s in SS) / N))
    P("  60 日超額可算 %d 筆（最後 60 日內的訊號 %d 筆算不出、無收盤 %d 筆）" % (sum(1 for s in SS if s['fx60'] is not None), sum(1 for s in SS if idx[s['d']] + HOLD >= len(cal)), sum(1 for s in SS if idx[s['d']] + HOLD < len(cal) and s['fx60'] is None)))
    P("  逐年訊號數與產業位置（price/vol/vol?/flat/down/na）：")
    for y in sorted(set(s['d'][:4] for s in SS)):
        cy = [s for s in SS if s['d'][:4] == y]; cc = collections.Counter(s['ist'] for s in cy)
        P("    %s n=%4d  " % (y, len(cy)) + " ".join("%s %3d" % (k[:4], cc[k]) for k in ST_ORDER) + "   new_price %d  個股 up %d" % (sum(s['inew'] for s in cy), sum(1 for s in cy if s['sst'] == 'up')))
# 產業別出現次數（先漲版）
cind = collections.Counter(s['ind'] or '（無產業）' for s in SX)
P("  先漲版產業別前 12：" + "、".join("%s %d" % (k, v) for k, v in cind.most_common(12)))

# ---------- 2. 事件統計 ----------
def m(L): return statistics.median(L) if L else float('nan')
def evt(rows):
    f = [s['fx60'] for s in rows if s['fx60'] is not None]
    if not f: return "n     0"
    h1 = [s['fx60'] for s in rows if s['fx60'] is not None and s['d'] < H2_START]; h2 = [s['fx60'] for s in rows if s['fx60'] is not None and s['d'] >= H2_START]
    se = statistics.pstdev(f) / math.sqrt(len(f)) if len(f) > 1 else float('nan')
    return "n %5d  中位 %+6.2f  平均 %+6.2f（±%.2f）  贏0050 %4.1f%%   前半中位 %+6.2f（n %4d） 後半 %+6.2f（n %4d）" % (len(f), m(f), statistics.mean(f), se, 100 * sum(1 for x in f if x > 0) / len(f), m(h1), len(h1), m(h2), len(h2))
def pr(s, r, g): return s['irev3'] is not None and s['igm'] is not None and s['irev3'] >= r and s['igm'] >= g
GROUPS = [
 ("全部", lambda s: True),
 ("-- 按產業 stage --", None),
] + [("產業 %s" % k, (lambda k: lambda s: s['ist'] == k)(k)) for k in ST_ORDER] + [
 ("產業 price/vol/vol?（rev3≥10）", lambda s: s['ist'] in PV),
 ("產業 非 down（rev3≥0 或 na）", lambda s: s['ist'] != 'down'),
 ("-- 按 new_price --", None),
 ("產業 new_price（剛進入價漲期）", lambda s: s['inew']),
 ("產業 price 但不是 new（已在價漲期 >3 月）", lambda s: s['ist'] == 'price' and not s['inew']),
 ("產業 非 new_price", lambda s: not s['inew']),
 ("-- 按產業 mom60（產業股價先動）--", None),
 ("產業 mom60 > 0", lambda s: s['imom'] is not None and s['imom'] > 0),
 ("產業 mom60 ≤ 0", lambda s: s['imom'] is not None and s['imom'] <= 0),
 ("產業 mom60 無", lambda s: s['imom'] is None),
 ("鄰：產業 mom60 > 10", lambda s: s['imom'] is not None and s['imom'] > 10),
 ("鄰：產業 mom60 > 20", lambda s: s['imom'] is not None and s['imom'] > 20),
 ("-- 按個股 stage --", None),
] + [("個股 %s" % k, (lambda k: lambda s: s['sst'] == k)(k)) for k in SST_ORDER] + [
 ("-- 相鄰門檻（產業 price 的定義 ±）--", None),
 ("產業 rev3≥5 且 gm_d≥0.5", lambda s: pr(s, 5, 0.5)),
 ("產業 rev3≥15 且 gm_d≥1.5", lambda s: pr(s, 15, 1.5)),
 ("產業 rev3≥10 且 gm_d≥0", lambda s: pr(s, 10, 0)),
 ("產業 rev3≥5（排除 rev3<5）", lambda s: s['irev3'] is not None and s['irev3'] >= 5),
 ("產業 rev3≥−5（排除 rev3<−5）", lambda s: s['irev3'] is not None and s['irev3'] >= -5),
 ("-- 族群（事後之見，只當參考）--", None),
 ("族群任一 price", lambda s: s['gprice']),
 ("在族群表但沒 price", lambda s: s['ingrp'] and not s['gprice']),
 ("不在族群表", lambda s: not s['ingrp']),
 ("-- 交叉 --", None),
 ("產業 price 且 個股 up", lambda s: s['ist'] == 'price' and s['sst'] == 'up'),
 ("產業 price 或 個股 up", lambda s: s['ist'] == 'price' or s['sst'] == 'up'),
 ("產業 down 且 個股 down", lambda s: s['ist'] == 'down' and s['sst'] == 'down'),
]
P("")
P("=" * 120)
P("== 事件統計：每筆訊號 買進日收盤 → 60 個交易日後收盤 的報酬 − 0050 含息（tr50）同期，點，未扣成本；n＝可算的筆數；前半 d<%s、後半 d≥%s" % (H2_START, H2_START))
for nm, SS in SETS:
    P("")
    P("-- %s（n=%d）--" % (nm, len(SS)))
    for gn, f in GROUPS:
        if f is None: P("  %s" % gn); continue
        P("  %-40s %s" % (gn, evt([s for s in SS if f(s)])))
P("")
P("-- 交叉：先漲 × 產業位置（全部版 n=%d）--" % len(sig))
for gn, f in [("先漲(r60x>20) 且 產業 price", lambda s: s['r60x'] > 20 and s['ist'] == 'price'), ("先漲 且 產業 非 price", lambda s: s['r60x'] > 20 and s['ist'] != 'price'),
              ("沒先漲(r60x≤20) 且 產業 price", lambda s: s['r60x'] <= 20 and s['ist'] == 'price'), ("沒先漲 且 產業 price/vol/vol?", lambda s: s['r60x'] <= 20 and s['ist'] in PV),
              ("沒先漲 且 產業 mom60>0", lambda s: s['r60x'] <= 20 and s['imom'] is not None and s['imom'] > 0), ("沒先漲 且 產業 mom60>10", lambda s: s['r60x'] <= 20 and s['imom'] is not None and s['imom'] > 10),
              ("沒先漲 且 產業 new_price", lambda s: s['r60x'] <= 20 and s['inew']), ("沒先漲 且 產業 非 down", lambda s: s['r60x'] <= 20 and s['ist'] != 'down'),
              ("沒先漲（全部）", lambda s: s['r60x'] <= 20), ("落後 0050（r60x≤0）", lambda s: s['r60x'] <= 0), ("先漲 且 產業 down", lambda s: s['r60x'] > 20 and s['ist'] == 'down')]:
    P("  %-40s %s" % (gn, evt([s for s in sig if f(s)])))

# ---------- 3. 帳戶模擬 ----------
def med(L):
    L = sorted(L); return L[len(L) // 2]      # 引擎慣例：30 次取 [15]、100 次取 [50]
YEARS = sorted(B50['yr'])
def evaluate(Sset, keyfn):
    full = [run2(Sset, keyfn=keyfn, seed=k) for k in range(NSEED)]
    h1 = [run2(Sset, keyfn=keyfn, seed=k, end=H1_END)['cagr'] for k in range(NSEED)]
    h2 = [run2(Sset, keyfn=keyfn, seed=k, start=H2_START)['cagr'] for k in range(NSEED)]
    r30 = sorted(run(Sset, seed=k)['cagr'] for k in range(NSEED))        # 純隨機 30 次（引擎原寫法）
    r100 = sorted(run(Sset, seed=k)['cagr'] for k in range(NRAND))       # 純隨機 100 次
    det = run2(Sset, keyfn=keyfn)                                         # 不打亂（同分照原順序＝代號小先，只供對照）
    cs = sorted(x['cagr'] for x in full)
    ymed = {y: statistics.median([x['yr'].get(y, 0) for x in full]) for y in YEARS}
    return dict(cagr=cs[NSEED // 2], lo=cs[0], hi=cs[-1], det=det['cagr'], mdd=med([x['mdd'] for x in full]), n=med([x['n'] for x in full]), avg=med([x['avg'] for x in full]), win=med([x['win'] for x in full]),
                h1=med(h1), h2=med(h2), r30=r30[NSEED // 2], rlo=r30[0], rhi=r30[-1], r100=r100[NRAND // 2], beatr=sum(1 for x in cs if x > r100[NRAND // 2]),
                ymed=ymed, beat50=sum(1 for y in YEARS if ymed[y] > B50['yr'].get(y, 0)), ny=len(YEARS), nsig=len(Sset))
def fmt(nm, r, base, extra=""):
    return "  %-40s 年化 %5.1f%%（同分隨機 %5.1f～%5.1f） 回撤 %5.1f%% 筆數 %3d（%+4d） 每筆 %+5.2f%% 勝率 %2.0f%%  純隨機%d次中位 %5.1f%%（%5.1f～%5.1f）  前半 %5.1f%% 後半 %5.1f%%  贏0050 %d/%d 年%s" % (
        nm, r['cagr'], r['lo'], r['hi'], r['mdd'], r['n'], r['n'] - base['n'], r['avg'], r['win'], NSEED, r['r30'], r['rlo'], r['rhi'], r['h1'], r['h2'], r['beat50'], r['ny'], extra)
def check(r, base):
    c1 = r['cagr'] > base['cagr']; c2 = r['rlo'] >= base['rlo'] - 1e-9; c3 = r['h1'] >= base['h1'] - 1e-9 and r['h2'] >= base['h2'] - 1e-9; c4 = r['beat50'] >= 9
    f = []
    if not c1: f.append("年化 %.1f ≤ %.1f" % (r['cagr'], base['cagr']))
    if not c2: f.append("純隨機最低 %.1f < %.1f" % (r['rlo'], base['rlo']))
    if not c3: f.append("前/後半 %+.1f/%+.1f" % (r['h1'] - base['h1'], r['h2'] - base['h2']))
    if not c4: f.append("贏0050 %d/%d" % (r['beat50'], r['ny']))
    return (c1 and c2 and c3 and c4), f
K_DEF = lambda s: (-s['r60x'],)
def first(flag): return lambda s: ((0 if flag(s) else 1), -s['r60x'])
def big(field): return lambda s: (-(s[field] if s[field] is not None else -1e9),)
RANKS = [
 ("預設排序（−r60x）", K_DEF, None),
 ("產業 price 優先 → 再 −r60x", first(lambda s: s['ist'] == 'price'), None),
 ("產業 price/vol/vol? 優先 → 再 −r60x", first(lambda s: s['ist'] in PV), None),
 ("產業 new_price 優先 → 再 −r60x", first(lambda s: s['inew']), None),
 ("產業 mom60 大先（同產業同分隨機）", big('imom'), None),
 ("產業 mom60 大先 → 再 −r60x", lambda s: (-(s['imom'] if s['imom'] is not None else -1e9), -s['r60x']), None),
 ("產業 rev3 大先（同產業同分隨機）", big('irev3'), None),
 ("產業 rev3 大先 → 再 −r60x", lambda s: (-(s['irev3'] if s['irev3'] is not None else -1e9), -s['r60x']), None),
 ("個股 up 優先 → 再 −r60x", first(lambda s: s['sst'] == 'up'), None),
 ("鄰：產業 rev3≥5 且 gm_d≥0.5 優先 → −r60x", first(lambda s: pr(s, 5, 0.5)), None),
 ("鄰：產業 rev3≥15 且 gm_d≥1.5 優先 → −r60x", first(lambda s: pr(s, 15, 1.5)), None),
 ("鄰：產業 rev3≥10 且 gm_d≥0 優先 → −r60x", first(lambda s: pr(s, 10, 0)), None),
 ("族群 price 優先 → 再 −r60x（事後之見）", first(lambda s: s['gprice']), None),
 ("對照：產業 down 優先 → 再 −r60x", first(lambda s: s['ist'] == 'down'), None),
 ("對照：產業 mom60 小先", lambda s: ((s['imom'] if s['imom'] is not None else 1e9),), None),
 ("對照：+r60x（先漲少的先）", lambda s: (s['r60x'],), None),
]
FILTERS = [
 ("不濾（預設排序，基準）", lambda s: True),
 ("排除產業 down", lambda s: s['ist'] != 'down'),
 ("鄰：排除產業 rev3<−5", lambda s: s['irev3'] is None or s['irev3'] >= -5),
 ("鄰：排除產業 rev3<5", lambda s: s['irev3'] is None or s['irev3'] >= 5),
 ("只買產業 price/vol/vol?（rev3≥10）", lambda s: s['ist'] in PV),
 ("鄰：只買產業 rev3≥15", lambda s: s['irev3'] is not None and s['irev3'] >= 15),
 ("只買 new_price 產業", lambda s: s['inew']),
 ("只買產業 price", lambda s: s['ist'] == 'price'),
 ("鄰：只買產業 rev3≥5 且 gm_d≥0.5", lambda s: pr(s, 5, 0.5)),
 ("鄰：只買產業 rev3≥10 且 gm_d≥0", lambda s: pr(s, 10, 0)),
 ("只買產業 mom60>0", lambda s: s['imom'] is not None and s['imom'] > 0),
 ("鄰：只買產業 mom60>10", lambda s: s['imom'] is not None and s['imom'] > 10),
 ("排除個股 down", lambda s: s['sst'] != 'down'),
 ("只買個股 up", lambda s: s['sst'] == 'up'),
 ("只買「產業 price 或 個股 up」", lambda s: s['ist'] == 'price' or s['sst'] == 'up'),
 ("只買族群 price（事後之見）", lambda s: s['gprice']),
 ("對照：只買產業 down", lambda s: s['ist'] == 'down'),
 ("對照：只買產業 mom60≤0", lambda s: s['imom'] is not None and s['imom'] <= 0),
]
ALL_FILTERS = [
 ("不濾（預設排序 −r60x，全部版基準）", lambda s: True),
 ("排除產業 down", lambda s: s['ist'] != 'down'),
 ("只買產業 price/vol/vol?（rev3≥10）", lambda s: s['ist'] in PV),
 ("只買 new_price 產業", lambda s: s['inew']),
 ("只買產業 price", lambda s: s['ist'] == 'price'),
 ("只買產業 mom60>0", lambda s: s['imom'] is not None and s['imom'] > 0),
 ("只買產業 mom60>10", lambda s: s['imom'] is not None and s['imom'] > 10),
 ("只買產業 mom60>20", lambda s: s['imom'] is not None and s['imom'] > 20),
 ("只買產業 price/vol/vol? 且 mom60>0", lambda s: s['ist'] in PV and s['imom'] is not None and s['imom'] > 0),
 ("排除個股 down", lambda s: s['sst'] != 'down'),
 ("只買個股 up", lambda s: s['sst'] == 'up'),
 ("只買個股 up 且 產業 price/vol/vol?", lambda s: s['sst'] == 'up' and s['ist'] in PV),
 ("對照：只買產業 down", lambda s: s['ist'] == 'down'),
 ("對照：先漲版（r60x>20，就是上面的預設 MGK）", lambda s: s['r60x'] > 20),
 ("鄰：r60x>10", lambda s: s['r60x'] > 10),
 ("鄰：r60x>30", lambda s: s['r60x'] > 30),
 ("沒先漲（r60x≤20）且 產業 price/vol/vol?", lambda s: s['r60x'] <= 20 and s['ist'] in PV),
 ("沒先漲（r60x≤20）且 產業 mom60>0", lambda s: s['r60x'] <= 20 and s['imom'] is not None and s['imom'] > 0),
]
ALL_RANKS = [
 ("預設排序（−r60x）", K_DEF),
 ("產業 price 優先 → 再 −r60x", first(lambda s: s['ist'] == 'price')),
 ("產業 price/vol/vol? 優先 → 再 −r60x", first(lambda s: s['ist'] in PV)),
 ("產業 new_price 優先 → 再 −r60x", first(lambda s: s['inew'])),
 ("產業 mom60 大先 → 再 −r60x", lambda s: (-(s['imom'] if s['imom'] is not None else -1e9), -s['r60x'])),
 ("產業 rev3 大先 → 再 −r60x", lambda s: (-(s['irev3'] if s['irev3'] is not None else -1e9), -s['r60x'])),
 ("個股 up 優先 → 再 −r60x", first(lambda s: s['sst'] == 'up')),
 ("對照：純隨機（30 seed 的中位，無排序鍵）", None),
]
RES = {}
P("")
P("=" * 120)
P("== 帳戶模擬（10 槽 × 10%%、抱 60 日、閒錢 0050 含息、成本 0.47%%；%s～%s）" % ("2016-06-01", cal[-1]))
P("   年化＝規則排序、同分隨機 %d seed 的中位（括號＝最低～最高；排序鍵無同分時 30 次相同）；回撤／筆數／每筆／勝率／前後半＝%d seed 中位；" % (NSEED, NSEED))
P("   純隨機＝整天打亂 run(S, seed=k)，報 %d 次中位（最低～最高），對照 100 次中位另列；前半 end %s／後半 start %s；贏0050＝逐年（%d seed 逐年中位）贏 0050 含息的年數" % (NSEED, H1_END, H2_START, NSEED))
P("   「穩」門檻：年化 > 預設 MGK、純隨機 %d 次最低 ≥ 預設版最低、前後半都不比預設差、贏 0050 年數 ≥ 9/11" % NSEED)
P("   0050 含息逐年：" + " ".join("%s %+.0f" % (y[2:], B50['yr'][y]) for y in YEARS))
# 3a 先漲版排序
P("")
P("-- 先漲版（r60x>20，訊號 %d 筆）：排序規則 --" % len(SX))
RES['x_rank'] = []
for nm, kf, _ in RANKS:
    r = evaluate(SX, kf); r['name'] = nm; RES['x_rank'].append(r)
    if nm.startswith("預設"): BASE = r
    ok, f = check(r, BASE)
    P(fmt(nm, r, BASE, "  不打亂 %.1f%%  贏純隨機100中位(%.1f%%) %d/%d  %s" % (r['det'], r['r100'], r['beatr'], NSEED, "（基準）" if nm.startswith("預設") else ("穩" if ok else "不穩（" + "；".join(f) + "）"))))
P("  逐年（%d seed 逐年中位，%%）：%s" % (NSEED, " ".join("%6s" % y[2:] for y in YEARS)))
P("  %-40s %s" % ("0050 含息", " ".join("%+6.0f" % B50['yr'][y] for y in YEARS)))
for r in RES['x_rank']: P("  %-40s %s   贏0050 %d/%d" % (r['name'], " ".join("%+6.0f" % r['ymed'][y] for y in YEARS), r['beat50'], r['ny']))
# 3b 先漲版濾網
P("")
P("-- 先漲版（r60x>20）：濾網（刪訊號，再用預設排序 −r60x）--")
RES['x_filt'] = []
for nm, flt in FILTERS:
    Sf = [s for s in SX if flt(s)]
    if len(Sf) < 10: P("  %-40s 訊號 %d 筆太少，不跑" % (nm, len(Sf))); continue
    r = evaluate(Sf, K_DEF); r['name'] = nm; RES['x_filt'].append(r)
    ok, f = check(r, BASE)
    P(fmt(nm, r, BASE, "  訊號 %d 筆（%.0f%%）  贏濾後純隨機100中位(%.1f%%) %d/%d  %s" % (len(Sf), 100 * len(Sf) / len(SX), r['r100'], r['beatr'], NSEED, "（基準）" if nm.startswith("不濾") else ("穩" if ok else "不穩（" + "；".join(f) + "）"))))
P("  逐年（%d seed 逐年中位，%%）：%s" % (NSEED, " ".join("%6s" % y[2:] for y in YEARS)))
P("  %-40s %s" % ("0050 含息", " ".join("%+6.0f" % B50['yr'][y] for y in YEARS)))
for r in RES['x_filt']: P("  %-40s %s   贏0050 %d/%d" % (r['name'], " ".join("%+6.0f" % r['ymed'][y] for y in YEARS), r['beat50'], r['ny']))
# 3c 全部版
P("")
P("-- 全部版（第一次跳升不管先漲，訊號 %d 筆）：產業位置能不能取代「先漲」？門檻仍用先漲版預設（年化 %.1f%%、純隨機最低 %.1f%%、前半 %.1f%%／後半 %.1f%%、贏0050 ≥9/11）--" % (len(sig), BASE['cagr'], BASE['rlo'], BASE['h1'], BASE['h2']))
RES['a_rank'] = []; RES['a_filt'] = []
P("  排序規則：")
for nm, kf in ALL_RANKS:
    if kf is None:
        rr = [run(sig, seed=k) for k in range(NSEED)]; cs = sorted(x['cagr'] for x in rr)
        P("  %-40s 年化中位 %5.1f%%（%5.1f～%5.1f） 回撤中位 %5.1f%% 筆數中位 %d" % (nm, cs[NSEED // 2], cs[0], cs[-1], med([x['mdd'] for x in rr]), med([x['n'] for x in rr]))); continue
    r = evaluate(sig, kf); r['name'] = nm; RES['a_rank'].append(r)
    if nm.startswith("預設"): ABASE = r
    ok, f = check(r, BASE)
    P(fmt(nm, r, ABASE, "  不打亂 %.1f%%  贏純隨機100中位(%.1f%%) %d/%d  %s" % (r['det'], r['r100'], r['beatr'], NSEED, "穩（達先漲版門檻）" if ok else "未達先漲版門檻（" + "；".join(f) + "）")))
P("  濾網（再用預設排序 −r60x）：")
for nm, flt in ALL_FILTERS:
    Sf = [s for s in sig if flt(s)]
    if len(Sf) < 10: P("  %-40s 訊號 %d 筆太少，不跑" % (nm, len(Sf))); continue
    r = evaluate(Sf, K_DEF); r['name'] = nm; RES['a_filt'].append(r)
    ok, f = check(r, BASE)
    P(fmt(nm, r, ABASE, "  訊號 %d 筆（%.0f%%）  贏濾後純隨機100中位(%.1f%%) %d/%d  %s" % (len(Sf), 100 * len(Sf) / len(sig), r['r100'], r['beatr'], NSEED, "穩（達先漲版門檻）" if ok else "未達先漲版門檻（" + "；".join(f) + "）")))
P("  逐年（%d seed 逐年中位，%%）：%s" % (NSEED, " ".join("%6s" % y[2:] for y in YEARS)))
P("  %-40s %s" % ("0050 含息", " ".join("%+6.0f" % B50['yr'][y] for y in YEARS)))
for r in RES['a_rank'] + RES['a_filt']: P("  %-40s %s   贏0050 %d/%d" % (r['name'], " ".join("%+6.0f" % r['ymed'][y] for y in YEARS), r['beat50'], r['ny']))

# ---------- 4. 總表 ----------
P("")
P("=" * 120)
P("== 總表（n＝交易筆數；年化＝同分隨機 %d seed 中位；純隨機＝%d 次中位(最低～最高)；穩＝四條件全過：年化>%.1f、純隨機最低≥%.1f、前半≥%.1f 且 後半≥%.1f、贏0050≥9/11）" % (NSEED, NSEED, BASE['cagr'], BASE['rlo'], BASE['h1'], BASE['h2']))
T = ["%-44s|%6s|%6s|%5s|%7s|%4s|%-20s|%-11s|%-5s|%s" % ("規則", "年化", "回撤", "n", "每筆", "勝率", "純隨機30 中位(低～高)", "前半/後半", "贏0050", "判定")]
for sect, lab in (("x_rank", "先漲版排序"), ("x_filt", "先漲版濾網"), ("a_rank", "全部版排序"), ("a_filt", "全部版濾網")):
    T.append("-- %s --" % lab)
    for r in RES[sect]:
        ok, f = check(r, BASE)
        isbase = (sect == "x_rank" and r is BASE) or (sect == "x_filt" and r['name'].startswith("不濾"))
        T.append("%-44s|%5.1f%%|%5.1f%%|%5d|%+6.2f%%|%3.0f%%|%5.1f%%（%5.1f～%5.1f）|%5.1f/%5.1f|%2d/%d|%s" % (
            r['name'][:44], r['cagr'], r['mdd'], r['n'], r['avg'], r['win'], r['r30'], r['rlo'], r['rhi'], r['h1'], r['h2'], r['beat50'], r['ny'],
            "（基準）" if isbase else ("穩" if ok else "不穩：" + "；".join(f))))
for t in T: P(t)
open("stagetest/b_mgk_table.txt", "w").write("\n".join(T) + "\n")
for sect in RES:
    for r in RES[sect]: r.pop('ymed', None)
json.dump(dict(base=dict(cagr=BASE['cagr'], rlo=BASE['rlo'], h1=BASE['h1'], h2=BASE['h2'], beat50=BASE['beat50']), res=RES), open("stagetest/b_mgk_res.json", "w"), ensure_ascii=False, indent=1)
P("（耗時 %.0f 秒；NSEED=%d NRAND=%d）" % (time.time() - T0, NSEED, NRAND))
OUT.close()
