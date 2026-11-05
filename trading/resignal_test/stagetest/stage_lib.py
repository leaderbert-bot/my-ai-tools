"""stage_lib：讀 stage_data.pkl（ind_stage.py 產生）的查詢工具。在 scratchpad 目錄 import stage_lib as S。
S.D = dict(yms, avail, IND, GRP, ind, grp, stock, params)
  yms      已處理的月份 ['201601', ...]；avail[ym] = 該月營收「可用」的第一個交易日（下月 11 日後）
  IND[code] 證交所產業別；GRP[code] = [使用者族群名...]（主題族群，成員是今天定的，有事後之見）
  ind[(產業, ym)] / grp[(族群, ym)] = dict(n, rev3, breadth, gm_d, mom60, stage, new_price, prev_stage)
      rev3     成員「近 3 月營收年增 %」中位數        breadth  成員年增 > 0 的比例
      gm_d     成員「近 4 季毛利率 − 去年同期近 4 季毛利率（點）」中位數（None = 資料不足，2016 年多半是 None）
      mom60    成員「近 60 日報酬 − 0050 近 60 日報酬（點）」中位數（產業股價先動）
      stage    'price' 價漲期(rev3≥10 且 gm_d≥1) / 'vol' 量增(rev3≥10 且 gm_d<1) / 'vol?' (rev3≥10 但 gm_d 不明) / 'down' 衰退(rev3<0) / 'flat'
      new_price 這個月 price 而 3 個月前不是；prev_stage 上個月的 stage
  stock[(code, ym)] = dict(r3, gm_d, gm_c, mom60, stage, q)：個股自己的位置；stage 'up'(r3≥10 且 累計季毛利率比去年同季高≥1.5) / 'vol' / 'vol?' / 'down' / 'flat'
所有欄位在 avail[ym] 當天收盤前就已知（月營收 10 日公布、季報用法定期限），回測時用 ym_at(d) 取「d 當天可用的最新月份」就不會偷看未來。"""
import pickle, bisect, os
_HERE = os.path.dirname(os.path.abspath(__file__))
D = pickle.load(open(os.path.join(_HERE, "stage_data.pkl"), "rb"))
YMS = D["yms"]; _AV = [D["avail"][y] for y in YMS]
IND, GRP = D["IND"], D["GRP"]

def ym_at(d):
    """交易日 d（'YYYY-MM-DD'）當天已可用的最新月份 ym；太早回 None"""
    i = bisect.bisect_right(_AV, d) - 1
    return YMS[i] if i >= 0 else None

def ind_of(code): return IND.get(code)

def ind_stage(code, d, lag=0):
    """該股證交所產業在 d 的位置；lag=k 取 k 個月前的（算「剛進入」用）"""
    k = IND.get(code); ym = ym_at(d)
    if not k or not ym: return None
    if lag:
        i = YMS.index(ym) - lag
        if i < 0: return None
        ym = YMS[i]
    return D["ind"].get((k, ym))

def ind_series(name):
    return [(ym, D["ind"][(name, ym)]) for ym in YMS if (name, ym) in D["ind"]]

def grp_stages(code, d):
    ym = ym_at(d)
    return [(g, D["grp"][(g, ym)]) for g in GRP.get(code, []) if ym and (g, ym) in D["grp"]]

def stock_stage(code, d, lag=0):
    ym = ym_at(d)
    if not ym: return None
    if lag:
        i = YMS.index(ym) - lag
        if i < 0: return None
        ym = YMS[i]
    return D["stock"].get((code, ym))

def members(name):
    return sorted(c for c, k in IND.items() if k == name)

def industries():
    return sorted(set(k for k, _ in D["ind"]))
