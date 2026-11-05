# -*- coding: utf-8 -*-
"""
作戰手冊更新（2026-11-05 晚上版）＋ MGK 名單卡 ＋ 策略分類的狀態更新。對 tw_radar.py 做三件事：
  1. 「📘 作戰手冊」卡片換成最新內容：可用策略 10 個（加 MGK）、流程加 MGK／停用線、資金桶加「事件小帳戶 C」、待辦換新、新增 Ⓔ 停用線分頁。
     （還沒加過作戰手冊的電腦會先自動跑 patch_playbook.py。）
  2. 「今天要做什麼」多一張「MGK 名單（紙上）」卡：每月 11 日後列出「單月營收年增 ≥ 30% 且創 24 月新高、12 個月內第一次、近 60 日比 0050 多 20 點」的股票，
     今天買／持有中剩幾天／今天賣／等 11 日，資料來自雷達自己的 history.json（月營收）與 px_history.json（日 K）。新增 /api/mgk。
  3. 策略分類（SB_ITEMS）：MGK 升到「可以用」（紙上）、基本面 1／D 與融資斷頭貨移到暫存區、★／季報意外獲利／信用恢復／循環課／菲比斯的待辦改成 11/05 的結果。
  4. 11/05 晚更正：★ 停用線照均量大先、100 種買進順序重定（−33% 減半、−40% 退回紙上），作廢「本月 −5% 停開新倉」與「回落 30% 全部停」（實戰頁警示、帳戶規則說明、心理卡、盤前檢查一起改）。
     排序維持 1024zh 的「均量大先」；還沒套 1024zh 的雷達會一起改回。
每一步都先檢查錨點，找不到就跳過那一步並說明，不會改壞；會先備份 tw_radar.py.bak_playbook2。
用法：雙擊「作戰手冊更新.bat」（再跑一次會說已經更新過）。改完重新啟動雷達。
"""
import os, sys, io, re, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "tw_radar.py")
MARK1 = "tdPlaybookCard"
MARK2 = "PB_KILL"
MARK3 = "mgkTodayCard"

# ---------------------------------------------------------------- 1. 作戰手冊內容
PB_STRATS = r'''var PB_STRATS = [
  ['★ 基本面＋近一年高', '任一點位＋近 3 月均營收創 12 月高＋TTM EPS 成長＋近 3 月營收年增 ≥ 0＋收盤 ≥ 一年高 95%＋0050 季線上；候選多時 20 日均量大的先；13:25 掛收盤價買，抱 20 個交易日收盤賣；6 槽、不停損、不加碼', '★ 帳戶', '實單', '兩段都驗過：早年（2003～2015）17～24%、近年 41～45%，回撤 −21～−31%。排序：11/05 試過創新高優先，2026/7 那段回撤 −46.5%，改回均量大先（−30.5%）'],
  ['MGK：營收第一次跳升＋股價先漲', '單月營收年增 ≥ 30% 且創 24 個月新高、近 12 個月第一次；隔月 11 日後第一個交易日，近 60 日漲幅比 0050 多 20 點以上 → 收盤買，抱 60 個交易日收盤賣；10 槽 × 10%、閒錢放 0050。下面的「MGK 名單」卡每天列', '事件小帳戶 C（先紙上一季）', '紙上', '2016～2026 年化 50.5%、回撤 −38.1%、306 筆、每筆 +16.1%、11 年贏 0050 九年、隨機 30 次 43.9～55.8%；早年 10.6%（0050 5.5%）但回撤 −54%，放錢時用 −54% 反推部位'],
  ['景氣燈號調 0050 倍數', '藍／黃藍且分數回升 → 1.5 倍（正2）；綠燈轉弱 → 0.5 倍；其他 1 倍。每月底看第 ④ 張卡', '長期底倉', '上線', '1990 起三段都不輸'],
  ['季報意外獲利', '單季 EPS 轉虧為盈或意外大賺、公布前 20 天沒先漲 10%；雷達現在：期限後第 2 個交易日收盤買、抱 16 天。11/05 用實際公告日重驗：「公告隔天收盤買」帳戶 31.8%／−31.8%、10/11 年贏 0050，比期限版 27.2% 好 → 紙上並行一季再切', '事件小帳戶 A（10%／筆）', '上線', '只有十年；每筆 +3.2%（公告日版 +4.4%）'],
  ['信用交易恢復', '上季淨值 5～10、本季 ≥ 10；期限後第 1 個交易日收盤買、第 6 個交易日開盤賣。11/05 重驗：優勢就在期限後那 5 天（公告日版只剩 +0.5%），一個字都不要改', '事件小帳戶 A（5%／筆）', '上線', '只有十年；每筆 +4.3%、67% 賺'],
  ['MSCI 新增股', '公告當天收盤買、生效日收盤賣，一年 4 次', '事件小帳戶 B', '上線', '只有十年；11 年 9 年贏'],
  ['財報爆發跳空', '董事會通過財報、單季 EPS 真的爆發、公布後第一個開盤跳空 3～9.5%：當天收盤買、抱 20 天；最多 10 檔', '事件小帳戶 B（先紙上）', '紙上', '11/04 起紙上，滿 20～30 筆對得上回測（+6.1%、62.6%）再放錢'],
  ['新春行情', '封關日收盤買 0050、紅盤第 5 天收盤賣', '長期底倉的錢', '上線', '12 年 11 年正、平均 +3.1%'],
  ['底倉：0050 定期定值＋VTI／QQQ', '照現在的計畫；美國部位到 100 萬為止', '長期底倉', '進行中', '10 年以上才用的錢'],
  ['融資維持率 <140% 崩盤加碼', '「加碼時點」卡片變「●」而且跌到 140% 以下或反彈 5 點：用崩盤加碼金買 0050、抱半年、不用融資', '崩盤加碼金', '觸發', '十年 4 次，120 天中位 +27%；是觸發不是策略']
];
'''
PB_FLOW = r'''var PB_FLOW = [
  ['每天 13:15', '看「① 今天要買」。有的話 13:25 掛收盤價（整張掛高一點、零股 13:29 前後）。沒有就不買。'],
  ['每天 13:30 後', '按「✓ 我買了／我賣了」。漏買 → 隔天收盤直接補，不等低價；收漲停買不到 → 跳過買下一個。'],
  ['每天 13:15', '看「② 今天要賣」：第 20 個交易日收盤賣，不早賣、不晚賣。'],
  ['每月 11 日後', '看「MGK 名單」卡：有「今天買」的就 13:25 掛收盤價（紙上先記在實戰紀錄備註或傳給 Claude）；持有中的到「今天賣」那天收盤賣。先紙上一季。'],
  ['每筆', '在「實際 vs 模擬」記成交價，順手算「成交價 − 收盤價」（滑價）。30 筆後就知道回測要打幾折。'],
  ['本月淨值 −5%', '照買，不要停（11/05 晚更正：這條沒有保護作用——在你現在的設定（95%、均量大先）會讓最大回撤從 −30.5% 變 −39.2%；年化多的 1.6 點只靠 2020、2021、2026 三年；換成 99% 或別的排序就變成少 3～11 點）。連輸減半、回落減碼也都不要。'],
  ['每月底', '第 ④ 張卡：景氣燈號幾倍，0050 底倉照它調。順便對一次 Ⓔ 停用線（滾動 30 筆勝率、連虧、回撤）。'],
  ['每季 5/15、8/14、11/14、3/31 前後', '事件小帳戶：季報意外獲利（期限後第 2 天收盤買；公告隔天版先紙上並行）、信用交易恢復（期限後第 1 天買、第 6 天開盤賣）、MSCI（公告日）。'],
  ['崩盤時', '「加碼時點」卡片跌到 140% 以下才動崩盤加碼金；跌破 150 當天、第 10 天、<145 都不要動。'],
  ['任何時候都不做', '個股加碼、母子單、拉回加碼、再訊號加碼、★ 加停損停利、★ 加法人條件、空槽放 0050、事件策略合成一池、當沖（等 1 分 K 驗完）、拿課程的財報規則當買點（14 條都測過輸 0050）。'],
  ['人工判斷（沒寫進程式）', '★ 候選裡 ROIC（近 4 季營業利益 ÷ 投入資本）已經 ≥ 40% 的排後面（10 年 60 天中位 −6.5 點）；產業在哪一期只當研究，不當進出場。']
];
'''
PB_BUCKETS = r'''var PB_BUCKETS = [
  ['reserve', '預備金（活存定存，不動）', 101.6], ['star', '★ 帳戶（6 槽，全照規則）', 55], ['evA', '事件小帳戶 A（0050 底＋季報意外獲利 10%／信用恢復 5%）', 25],
  ['evB', '事件小帳戶 B（0050 底＋財報爆發跳空，先紙上；MSCI 之後接進來）', 25], ['evC', '事件小帳戶 C（0050 底＋MGK，先紙上一季；放錢時用早年 −54% 回撤反推）', 0], ['crash', '崩盤加碼金（現金，只在維持率 <140 或景氣藍燈時買 0050）', 30],
  ['core_tw', '長期底倉：0050（定期定值）', 29], ['core_us', '長期底倉：VTI／QQQ（每月續投到 100 萬）', 50.8], ['other', '規則外持股（泰合、台積電、台塑、00981A…每檔寫理由）', 31], ['fut', '期貨保證金（留最低，其餘回現金）', 20.4]
];
'''
PB_TODO = r'''var PB_TODO = [
  ['t_cap', '定 ★ 帳戶大小（44～66 萬），到「實戰紀錄」把本金改成它、「實際下單每檔」改成 本金 ÷ 6；從那天起照股數買'],
  ['t_slip', '「實際 vs 模擬」每筆記成交價；滿 30 筆看滑價'],
  ['t_mgk', 'MGK 紙上一季：每月 11 日後照「MGK 名單」卡記下買賣（代號、日期、收盤價），滿 30 筆看平均與勝率（門檻：平均 ≥ +5%、勝率 ≥ 45%）再決定放錢'],
  ['t_xlev', '季報意外獲利「公告隔天收盤買」版紙上並行一季（11/14 那次開始），一季後決定切不切'],
  ['t_dbx', 'Dropbox 只讓一台寫（另一台用瀏覽器連主機），清掉 data 裡的衝突複本（fin_ext 有 10 份）'],
  ['t_1m', '兩台都再雙擊「下載個股分K.bat」直到它說全部抓完（流量上限會分幾天）；抓完雙擊「當沖盤中驗證.bat」'],
  ['t_bgap', '財報爆發跳空紙上滿 20～30 筆、對得上回測，再把事件小帳戶 B 的錢放進去'],
  ['t_kill', '每月底對一次 Ⓔ 停用線；碰警戒線部位減半、碰停用線退回紙上'],
  ['t_us', '美股 12 檔個股：每檔寫下留的理由，沒有理由的賣掉併回 VTI'],
  ['t_other', '泰合、台積電、台塑、00981A：寫理由或併回底倉；帳本修華擎 −1 股、泰合成本'],
  ['t_fut', '期貨保證金 20.4 萬只留最低，其餘回活存']
];
var PB_KILL = [
  ['★（6 槽、抱 20 天）', '滾動 30 筆只贏 ≤ 7 筆（23%）；30 筆平均每筆 < −5%；連虧 12 筆；帳戶從高點回撤 −33%', '只贏 ≤ 5 筆（17%）；平均 < −7%；連虧 15 筆；回撤 −40%', '11/05 晚照均量大先、100 種買進順序重定：回撤中位 −27%、最差 −31%（99% 版最差 −39%）；30 筆勝率最低 23%；平均最低 −4.5%（99% 版 −5.9%）；連虧最多 11 筆。原本「回撤 −25% 警戒、平均 < −4% 停用」一半以上的順序都會碰到，作廢；落後 0050 不當停用條件（2026 年 0050 +63% 會誤觸）'],
  ['季報意外獲利（10 槽、抱 16 天）', '30 筆勝率 < 30%；平均 < −2.5%；連虧 11 筆；連 2 年輸 0050', '勝率 < 20%；平均 < −4%；連虧 13 筆；連 3 年輸', '歷史最差：勝率 23%、連虧 10 筆；2025 輸過'],
  ['信用交易恢復（5%／筆、抱 5 天）', '滾動 20 筆勝率 < 40%；20 筆合計 < 0；連虧 8 筆', '勝率 < 30%；合計 < −10%；連虧 10 筆', '只有 99 筆、一年約 11 筆'],
  ['MGK（紙上）', '紙上 30 筆平均 < +5% 或勝率 < 45% → 不放錢', '放錢後照季報意外獲利那列', '回測每筆 +16.1%、勝率 59%'],
  ['財報爆發跳空（紙上）', '紙上前 30 筆平均 < 0 或勝率 < 45% → 不放錢', '放錢後照季報意外獲利那列', '回測 +6.1%、62.6%'],
  ['MSCI、新春、景氣燈號（一年幾次）', '連 2 個日曆年輸「什麼都不做」（0050 含息／1 倍 0050）', '連 3 年輸', '筆數太少，用年度'],
  ['全部共用', '實際 vs 模擬 30 筆後平均滑價 > 0.5% → 先修執行（13:25 掛單、改整張），不改策略；雷達連 3 個交易日沒更新或出現衝突複本 → 當天不下單', '一個月內 2 筆「規則外」買賣 → 那個月全部退回紙上', '最後這條比上面任何一條都重要']
];
'''

PB_REPL = [
    # (錨點起, 錨點迄, 新內容)：把舊陣列整個換掉
    ("var PB_STRATS = [", "];\nvar PB_FLOW", PB_STRATS + "var PB_FLOW"),
    ("var PB_FLOW = [", "];\nvar PB_BUCKETS", PB_FLOW + "var PB_BUCKETS"),
    ("var PB_BUCKETS = [", "];\nvar PB_TODO", PB_BUCKETS + "var PB_TODO"),
    ("var PB_TODO = [", "];\nfunction pbNum", PB_TODO + "function pbNum"),
]
PB_SMALL = [
    ("pbToggle()\">📘 作戰手冊<span class=\"sub\">9 個可用策略・", "pbToggle()\">📘 作戰手冊<span class=\"sub\">' + PB_STRATS.length + ' 個可用策略・"),
    ("var tabs = [['buckets', 'Ⓒ 資金桶'], ['strats', 'Ⓐ 可用策略'], ['flow', 'Ⓑ 流程'], ['todo', 'Ⓓ 待辦']];",
     "var tabs = [['buckets', 'Ⓒ 資金桶'], ['strats', 'Ⓐ 可用策略'], ['flow', 'Ⓑ 流程'], ['kill', 'Ⓔ 停用線'], ['todo', 'Ⓓ 待辦']];"),
    ("    eq = vals.star + vals.evA + vals.evB + vals.core_tw + vals.core_us + vals.other;",
     "    eq = vals.star + vals.evA + vals.evB + (vals.evC || 0) + vals.core_tw + vals.core_us + vals.other;"),
    ("        else if(b[0] === 'evB') each = '每筆 ' + (v / 10).toFixed(1) + ' 萬';",
     "        else if(b[0] === 'evB') each = '每筆 ' + (v / 10).toFixed(1) + ' 萬';\n        else if(b[0] === 'evC') each = v ? '每筆 ' + (v / 10).toFixed(1) + ' 萬' : '紙上一季，先不放錢';"),
    ("  }else if(tab === 'todo'){\n",
     "  }else if(tab === 'kill'){\n    h += '<div style=\"overflow:auto\"><table class=\"sttbl\"><tr><th>策略</th><th>警戒（部位減半、不改規則、30 筆後再看）</th><th>停用（退回紙上、查資料／執行／市場）</th><th>依據</th></tr>' +\n      PB_KILL.map(function(k){ return '<tr><td style=\"white-space:nowrap\"><b>' + esc(k[0]) + '</b></td><td style=\"white-space:normal;min-width:240px;line-height:1.6\">' + esc(k[1]) + '</td><td style=\"white-space:normal;min-width:200px;line-height:1.6\">' + esc(k[2]) + '</td><td style=\"white-space:normal;min-width:160px\" class=\"mut\">' + esc(k[3]) + '</td></tr>'; }).join('') + '</table></div>' +\n      '<div class=\"mut\" style=\"font-size:12px;margin-top:6px;line-height:1.7\">原則：停用線放在「歷史上從來沒發生過」的地方（★ 用 100 種買進順序算），警戒線放在很少碰到的地方；回測裡不會誤觸，實單碰到就代表行為已經超出歷史經驗。每月底對一次（★ 的滾動數字「實戰紀錄」算得出來）。依據「停用條件_建議.md」與 11/05 晚「★回撤與月停_更正.md」。</div>';\n  }else if(tab === 'todo'){\n"),
]
NOTE_OLD_PREFIX = "'<div class=\"mut\" style=\"font-size:12px;margin-top:6px;line-height:1.7\">工具（不是策略）："
NOTE_NEW = ("'<div class=\"mut\" style=\"font-size:12px;margin-top:6px;line-height:1.7\">工具（不是策略）：DR 套利監控、台指期三兄弟價差、持股警示、美股 ETF 買哪邊、加碼時點。有條件可用：可轉債穿雲箭／CBAS、★ 多空版、季報 z 值。"
            "11/05 否決或暫存的不列：基本面 1／D（早年 6.8～12.9%）、融資斷頭貨帳戶版（15.1%／−47.7%）、循環課「剛進入價漲期」（18.9%／−60%）與產業循環位置（★／MGK 排序濾網、獨立選股 100 多組都不穩）、優分析 14 條財報規則（ROIC、毛利率、營益率、資本支出上修…當買點都輸 0050）、老白早年、台指期盤中、法人條件、加碼、停損停利。</div>'")
TODO_NOTE_OLD_PREFIX = "'<div class=\"mut\" style=\"font-size:12px;margin-top:6px\">打勾只記在這台電腦的瀏覽器。"
TODO_NOTE_NEW = "'<div class=\"mut\" style=\"font-size:12px;margin-top:6px\">打勾只記在這台電腦的瀏覽器。Claude 那邊還在跑：1 分 K 抓完後的當沖三招。11/05 收掉的：★ 排序、季報公告日版、基本面 1／D 早年、融資斷頭貨帳戶版、優分析全部講義、產業循環位置（100 多組都不穩，不拿來選股）。</div>'"

# ---------------------------------------------------------------- 2. MGK 名單卡
PY_MGK = r'''
# ==================== 1105m：MGK 名單（紙上，第三個事件小帳戶）：營收第一次跳升＋股價先漲 ====================
_MGK_MEM = {"key": None, "data": None}
MGK_HOLD = 60                      # 抱 60 個交易日收盤賣
MGK_LEAD = 20.0                    # 公布後第一個交易日，近 60 日漲幅要比 0050 多 20 點


def _mgk_ym_prev(ym, k):
    y, m = int(ym[:4]), int(ym[4:]); m -= k
    while m <= 0:
        m += 12; y -= 1
    return "%04d%02d" % (y, m)


def mgk_payload():
    """每月 11 日後：單月營收年增 ≥ 30% 且 ≥ 前 23 個月最高、近 12 個月內第一次（跳升）；隔月 11 日後第一個交易日，
    近 60 日漲幅比 0050 多 20 點以上、20 日均量 ≥ 500 張、收盤 ≥ 10、當天沒鎖漲停 → 收盤買，第 60 個交易日收盤賣。
    回測（2016～2026，10 槽 × 10%、閒錢 0050 含息）：年化 50.5%、回撤 −38.1%、306 筆、每筆 +16.1%、11 年贏 0050 九年。先紙上一季。"""
    import bisect as _bis
    now = datetime.now(TZ); today = now.date().isoformat()
    mon = load_history() or {}
    H = load_px_history_all() or {}
    key = (today, len(mon), _PXH_MEM.get("mtime"))
    if _MGK_MEM["key"] == key and _MGK_MEM["data"]:
        return _MGK_MEM["data"]
    r50 = _ms_adj_series(H.get("0050") or {})
    cal = [r[0] for r in r50]; c50 = [r[4] for r in r50]
    idx = dict((d, i) for i, d in enumerate(cal))
    if len(cal) < 80:
        return {"ok": False, "err": "0050 日 K 不足（px_history 還沒回補）"}
    n = len(cal) - 1; last = cal[-1]
    try:
        hol = _lt_holidays()
    except Exception:
        hol = set()
    is_td = _lt_is_td(today, hol) if "_lt_is_td" in globals() else (now.weekday() < 5)
    yms_all = [ym for R in mon.values() if isinstance(R, dict) for ym in R if isinstance(ym, str) and len(ym) == 6 and ym.isdigit()]
    if not yms_all:
        return {"ok": False, "err": "沒有月營收資料（history.json）"}
    latest = max(yms_all)
    lo, lo20 = _mgk_ym_prev(latest, 6), _mgk_ym_prev(latest, 20)
    names = load_stock_names() or {}

    def nm(c):
        v = names.get(c)
        return v if isinstance(v, str) else (((v or {}).get("name") or "") if isinstance(v, dict) else "")

    def avail(ym):
        """營收月份 ym → 隔月 11 日後第一個交易日；還沒到就回 (None, d0)"""
        y, m = int(ym[:4]), int(ym[4:]); m += 1
        if m > 12:
            m -= 12; y += 1
        d0 = "%04d-%02d-11" % (y, m)
        i = _bis.bisect_left(cal, d0)
        return (cal[i] if i < len(cal) else None), d0

    rows = []
    for c, R in mon.items():
        if not (isinstance(c, str) and len(c) == 4 and c.isdigit()) or c.startswith("00") or not isinstance(R, dict):
            continue

        def val(k):
            v = R.get(k)
            return float(v) if isinstance(v, (int, float)) and v > 0 else None
        jumps = set()
        for ym in sorted(k for k in R if isinstance(k, str) and len(k) == 6 and k.isdigit() and k >= lo20):
            v, ly = val(ym), val(_mgk_ym_prev(ym, 12))
            if not v or not ly:
                continue
            h = [val(_mgk_ym_prev(ym, k)) for k in range(1, 24)]; h = [x for x in h if x]
            if not (v / ly - 1 >= 0.30 and len(h) >= 18 and v >= max(h)):
                continue
            first = not any(_mgk_ym_prev(ym, k) in jumps for k in range(1, 13))
            jumps.add(ym)
            if ym < lo or not first:
                continue
            row = {"c": c, "n": nm(c), "ym": ym, "yoy": round((v / ly - 1) * 100)}
            d, d0 = avail(ym)
            s = _ms_adj_series(H.get(c) or {})
            if not s:
                continue
            sm = dict((r[0], r) for r in s)
            if d is None:
                if d0 > today or not is_td:
                    row.update(st="wait", d=d0); rows.append(row); continue
                # 今天就是 11 日後第一個交易日，但今天的日 K 還沒進來：用最新一根估先漲
                i = n; b = s[-1]; est = True
            else:
                i = idx[d]; b = sm.get(d); est = False
                if not b:
                    continue
            if i < 60:
                continue
            b60 = sm.get(cal[i - 60])
            if not b60 or not c50[i] or not c50[i - 60]:
                continue
            r60x = (b[4] / b60[4] - 1) * 100 - (c50[i] / c50[i - 60] - 1) * 100
            vols = [sm[x][5] for x in cal[max(0, i - 20):i] if x in sm]
            liq = len(vols) >= 15 and sum(vols) / 20.0 >= 500000 and b[4] >= 10
            pb = sm.get(cal[i - 1]); locked = bool(pb and b[4] >= pb[4] * 1.094 and b[4] >= b[2] * 0.999)
            row.update(d=(today if est else d), px=round(b[4], 2), r60x=round(r60x, 1), est=est,
                       now=round(s[-1][4], 2), ret=round((s[-1][4] / b[4] - 1) * 100, 1))
            if r60x <= MGK_LEAD or not liq or (locked and not est):
                row["st"] = "skip"; row["why"] = ("先漲只有 %+.0f 點" % r60x) if r60x <= MGK_LEAD else ("均量不足 500 張或股價 < 10" if not liq else "當天鎖漲停")
                if ym == latest:
                    rows.append(row)
                continue
            if est:
                row["st"] = "today"; row["left"] = MGK_HOLD
                try:
                    row["x_d"] = _lt_weekdays_after(today, MGK_HOLD)
                except Exception:
                    row["x_d"] = None
                rows.append(row); continue
            held = n - i
            try:
                x_d = _lt_weekdays_after(d, MGK_HOLD)
            except Exception:
                x_d = cal[i + MGK_HOLD] if i + MGK_HOLD <= n else None
            row["x_d"] = x_d; row["held"] = held; row["left"] = max(0, MGK_HOLD - held)
            if x_d and x_d == today:
                row["st"] = "sell"
            elif x_d and x_d < today:
                row["st"] = "done"
                xi = i + MGK_HOLD
                if xi <= n:
                    xb = sm.get(cal[xi])
                    if xb:
                        row["x_px"] = round(xb[4], 2); row["ret"] = round((xb[4] / b[4] - 1) * 100, 1)
                if held > MGK_HOLD + 25:
                    continue
            elif held == 0 and d == today:
                row["st"] = "today"
            else:
                row["st"] = "hold"
            rows.append(row)
    order = {"today": 0, "sell": 1, "hold": 2, "wait": 3, "done": 4, "skip": 5}
    rows.sort(key=lambda r: (order.get(r["st"], 9), r.get("left", 0) if r["st"] == "hold" else 0, -(r.get("r60x") or 0)))
    rows = [r for r in rows if r["st"] != "skip"] + [r for r in rows if r["st"] == "skip"][:12]
    out = {"ok": True, "today": today, "last": last, "latest_ym": latest, "is_td": is_td,
           "n_hold": sum(1 for r in rows if r["st"] in ("hold", "sell")), "rows": rows[:60],
           "hold": MGK_HOLD, "lead": MGK_LEAD}
    _MGK_MEM["key"], _MGK_MEM["data"] = key, out
    return out

'''
PY_ANCHOR = "\ndef ltrade_today():\n"
API_ANCHOR = '            elif path == "/api/today":\n'
API_NEW = ('            elif path == "/api/mgk":\n'
           '                try:\n'
           '                    self._json(mgk_payload())\n'
           '                except Exception as e:\n'
           '                    self._json({"err": "%s: %s" % (type(e).__name__, str(e)[:200])})\n')

JS_MGK = r'''/* ==================== 1105m：MGK 名單卡（紙上，第三個事件小帳戶） ==================== */
var MGKX = {d: null, busy: false, t: 0};
function mgkLoad(cb){
  if(MGKX.busy) return;
  MGKX.busy = true;
  fetch('/api/mgk').then(function(r){ return r.json(); }).then(function(j){ MGKX.busy = false; MGKX.d = j || {}; MGKX.t = Date.now(); if(cb) cb(); })
    .catch(function(e){ MGKX.busy = false; MGKX.d = {ok: false, err: String(e)}; MGKX.t = Date.now(); if(cb) cb(); });
}
function mgkTodayCard(){
  if(!SERVED) return '';
  if(MGKX.d === null){ mgkLoad(function(){ if(S.page === 'today') renderToday(); }); return ''; }
  if(!MGKX.busy && Date.now() - (MGKX.t || 0) > 600000) mgkLoad(function(){ if(S.page === 'today') renderToday(); });
  var P = MGKX.d || {};
  var open = store('mgk_open') !== '0';
  var h = '<div class="tdcard" id="tdMgk"><h3 style="cursor:pointer" onclick="store(\'mgk_open\', store(\'mgk_open\') === \'0\' ? \'1\' : \'0\'); renderToday();">MGK 名單（紙上，事件小帳戶 C）<span class="sub">營收第一次跳升＋股價先漲・抱 ' + (P.hold || 60) + ' 個交易日' + (P.ok ? '・持有 ' + (P.n_hold || 0) + '／10' : '') + '　' + (open ? '▲ 收合' : '▼ 展開') + '</span></h3>';
  if(!open) return h + '</div>';
  if(!P.ok) return h + '<div class="mut" style="font-size:12.5px">' + esc(P.err || '讀取中…') + '</div></div>';
  var R = P.rows || [], ST = {today: ['今天收盤買', 'pos'], sell: ['今天收盤賣', 'neg'], hold: ['持有中', ''], wait: ['等 11 日', 'mut'], done: ['已出場', 'mut'], skip: ['不買', 'mut']};
  var f1 = function(v, s){ return v == null ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(1) + (s || ''); };
  var act = R.filter(function(r){ return r.st === 'today' || r.st === 'sell'; });
  if(act.length) h += '<div class="tdnote"><b>' + act.map(function(r){ return (r.st === 'today' ? '買 ' : '賣 ') + esc(r.c + ' ' + (r.n || '')) + (r.st === 'today' && r.est ? '（先漲用昨收估 ' + f1(r.r60x, ' 點') + '，13:25 再確認）' : ''); }).join('、') + '</b>　每檔＝小帳戶 1/10；13:25 掛收盤價。紙上階段先記在實戰紀錄備註或傳給 Claude。</div>';
  if(!R.length) h += '<div class="mut" style="font-size:12.5px">最近 6 個月沒有符合「第一次跳升」的營收；下次 11 日後再看。</div>';
  else h += '<div style="overflow:auto"><table class="sttbl"><tr><th>狀態</th><th>股票</th><th>營收月</th><th>年增</th><th>買進日</th><th>買價</th><th>先漲（60 日比 0050）</th><th>現價／報酬</th><th>賣出日</th></tr>' +
    R.map(function(r){ var s = ST[r.st] || [r.st, '']; return '<tr><td class="' + s[1] + '" style="white-space:nowrap"><b>' + s[0] + '</b>' + (r.st === 'hold' ? '<br><span class="mut">剩 ' + r.left + ' 天</span>' : (r.st === 'skip' ? '<br><span class="mut">' + esc(r.why || '') + '</span>' : '')) + '</td>' +
      '<td style="white-space:nowrap">' + esc(r.c + ' ' + (r.n || '')) + '</td><td>' + esc(String(r.ym || '').slice(0, 4) + '/' + String(r.ym || '').slice(4)) + '</td><td>' + (r.yoy != null ? '+' + r.yoy + '%' : '—') + '</td>' +
      '<td style="white-space:nowrap">' + esc(r.d || '—') + '</td><td>' + (r.px != null ? r.px : '—') + '</td><td>' + f1(r.r60x, ' 點') + '</td><td style="white-space:nowrap">' + (r.now != null ? r.now + '　' + f1(r.ret, '%') : '—') + (r.x_px != null ? '<br><span class="mut">出場 ' + r.x_px + '</span>' : '') + '</td><td style="white-space:nowrap">' + esc(r.x_d || '—') + '</td></tr>'; }).join('') + '</table></div>';
  h += '<div class="mut" style="font-size:12px;margin-top:6px;line-height:1.7">規則：單月營收年增 ≥ 30% 且創 24 個月新高、近 12 個月第一次；隔月 11 日後第一個交易日，近 60 日漲幅比 0050 多 ' + (P.lead || 20) + ' 點以上、20 日均量 ≥ 500 張、收盤 ≥ 10、沒鎖漲停 → 收盤買，第 ' + (P.hold || 60) + ' 個交易日收盤賣；10 槽 × 10%、閒錢放 0050；同一天候選多先買先漲最多的。' +
    '回測 2016～2026：年化 50.5%、回撤 −38.1%、306 筆、每筆 +16.1%、11 年贏 0050 九年；早年（2003～2015）10.6% 但回撤 −54%。0050 季線濾網在這裡是反效果，不要套。<b>先紙上一季</b>：30 筆平均 < +5% 或勝率 < 45% 就不放錢。資料到 ' + esc(P.last || '') + '（月營收到 ' + esc(String(P.latest_ym || '')) + '）。這是歷史回測，不是投資建議。</div>';
  return h + '</div>';
}
'''
JS_ANCHOR = "function renderToday(){\n"
JS_CALL_OLD = "+ c7 + c8 + c9 + c3 +"
JS_CALL_NEW = "+ c7 + c8 + c9 + mgkTodayCard() + c3 +"

# ---------------------------------------------------------------- 3. 策略分類（SB_ITEMS）
def _find_block(src, head_pat):
    """找 SB_ITEMS 裡以 head_pat（正則，對第一行）開頭的那一筆；回傳 (start, end)"""
    m = re.search(head_pat, src)
    if not m:
        return None
    start = m.start()
    m2 = re.compile(r"\n  \{k: '|\n  /\* ----------|\n\];").search(src, m.end())
    return (start, m2.start() if m2 else None)


def _set_field(block, name, value):
    v = value.replace("\\", "").replace("'", "’")
    pat = re.compile(r"(\n   %s: ')((?:[^'\\]|\\.)*)(')" % name)
    if pat.search(block):
        return pat.sub(lambda m: m.group(1) + v + m.group(3), block, count=1)
    j = block.rstrip().rfind("}")
    if j < 0:
        return block
    before = block[:j].rstrip()
    if before.endswith(","):
        before = before[:-1]
    return before + ",\n   %s: '%s'" % (name, v) + block[j:]


def _set_head(block, cat=None, at=None, page=None, drop_lt=False):
    first, rest = block.split("\n", 1)
    if cat:
        first = re.sub(r"cat: '[a-z]*'", "cat: '%s'" % cat, first, count=1)
    if at:
        first = re.sub(r"at: '\d{4}-\d{2}-\d{2}'", "at: '%s'" % at, first, count=1)
    if page:
        first = re.sub(r"page: '[a-z_0-9]*'", "page: '%s'" % page, first, count=1)
    if drop_lt:
        first = re.sub(r", lt: '[a-z_0-9]*'", "", first, count=1)
    return first + "\n" + rest


SB_UPDATES = [
    # (第一行的正則, 表頭改動 dict, 欄位 dict)
    (r"  \{k: 's:mgk', t: 's', cat: 'fix'", dict(cat="ok", at="2026-11-05", page="today", drop_lt=True),
     dict(rule="單月營收年增 ≥ 30% 且 ≥ 前 23 個月最高、近 12 個月內第一次；隔月 11 日後第一個交易日，近 60 日漲幅比 0050 多 20 點以上 → 收盤買，抱 60 個交易日收盤賣；10 槽 × 10%、閒錢放 0050。「今天要做什麼」的 MGK 名單卡每天列。",
          num="11/05 帳戶重做（2016～2026）：年化 50.5%、回撤 −38.1%、306 筆、每筆 +16.1%、勝率 59%，隨機 30 次 43.9～55.8%，前半 53.8%／後半 41.1%，11 年贏 0050 九年；不加「先漲」只有 35.6%。早年（2003～2015）10.6%（0050 5.5%）但回撤 −54%。",
          why="過三條標準（不靠順序、不靠半段、不靠一兩年）；跟 ★ 候選只重疊 4%，是另一群股票，適合當第三個小帳戶。0050 季線濾網在這裡是反效果（50% → 27%），不要套。",
          todo="先紙上一季（事件小帳戶 C）；放錢時用早年 −54% 反推部位。紙上 30 筆平均 < +5% 或勝率 < 45% 就不放錢。")),
    (r"  \{k: 's:fundall', t: 's', cat: 'fix'", dict(cat="park", at="2026-11-05"),
     dict(num="基本面版 2017～2026 年化 40.1%；2003～2015 7.3～16.7%（0050 含息 3.8%）、回撤 −29～−33%。1／D 近十年 27%、回撤最小，但早年只有 6.8～10.7%（加 95% 一年高 12～13%），每個設定都輸 ★（早年 17～24%、回撤 −21～−23%）。",
          why="早年不贏或遠輸 ★。實單只做 ★。", todo="11/05 早年回測做完（基本面1D早年驗證.md）：不用。")),
    (r"  \{k: 's:credit', t: 's', cat: 'fix'", dict(cat="park", at="2026-11-05"),
     dict(todo="11/05 帳戶版做完：V3（維持率 <130＋融資減 20%＋跌 20%）10 槽抱 60 天 15.1%／−47.7%（0050 23.6%／−33.9%）；只在大盤維持率 <140 時（V4）25.8%／−34.1%，但十年只碰到 2 次。暫存；大盤 <140 時用「加碼時點」卡買 0050 就好。")),
    (r"  \{k: 's:cycnew', t: 's', cat: '[a-z]+'", dict(cat="park", at="2026-11-05"),
     dict(todo="11/05：剛進入價漲期（＋股價先漲）當獨立策略 18.9%／−60%，不行。整個產業在哪一期（證交所 33 產業、每月）也測完：當 ★ 排序／濾網、MGK 排序／濾網、產業剛進入某一期再從裡面挑股（6 種訊號 × 5 種挑法 × 抱 60／120 天），100 多組 0 組穩；課程原版 12.9%／−52.6%。產業轉成價漲期時股價差不多在高點（中位早 1 個月、營收再晚 1 個月才知道）。只當研究：優先看剛轉成長期（營收先轉正、毛利率還沒動）的產業，不當進出場。見 產業循環位置_能不能選股.md。")),
    (r"  \{k: 's:fei_ok', t: 's', cat: 'fix'", dict(at="2026-11-05"),
     dict(todo="11/05 試過：菲比斯 105／807、MGK 當 ★ 排序鍵都沒用（★ 候選裡只有 4% 是它們），排序試過「創新高優先」，回撤太深又改回均量大先。617 當事件提醒。")),
    (r"  \{k: 's:xlev', t: 's', cat: 'ok'", dict(at="2026-11-05"),
     dict(todo="11/05 用實際公告日重驗：期限後第 2 天 +3.23%／筆、公告隔天收盤買 +4.39%；帳戶 10 槽 A 27.2%／−36.2%、C（公告隔天）31.8%／−31.8%、10/11 年贏 0050 → 「公告隔天收盤買」版先紙上並行一季，再決定切不切。")),
    (r"  \{k: 's:[a-z_0-9]+', t: 's', cat: 'ok', nm: '信用交易恢復", dict(at="2026-11-05"),
     dict(todo="11/05 重驗：期限後第 1 天買 +4.28%／筆；改公告日版只剩 +0.50% → 優勢就在期限後那 5 天，一個字都不要改。")),
    (r"  \{k: 's:[a-z_0-9]+', t: 's', cat: 'ok', nm: '★ 基本面", dict(at="2026-11-05"),
     dict(todo="11/05：候選排序試過「當天創新高優先」（近年比隨機多 5～7 點），但 2026 年 7 月那段回撤 −46.5%（均量大先 −30.5%），晚上改回均量大先；早年 2003～2015 17～24%／回撤 −21～−23% 驗過；1／D 早年測了不用；ROIC ≥ 40% 的候選自己排後面（10 年 60 天中位 −6.5 點，沒寫進程式）。11/05 晚：「本月 −5% 停開新倉」作廢（會讓回撤從 −30.5% 變 −39.2%）；停用線照 100 種買進順序重定（−33% 減半、−40% 退回紙上）。見 ★回撤與月停_更正.md。")),
]


STALE = [
    ("Claude 那邊還在跑：產業循環位置（整個產業在哪一期）當 ★／MGK 加權與獨立選股；1 分 K 抓完後的當沖三招。11/05 收掉的：★ 排序、季報公告日版、基本面 1／D 早年、融資斷頭貨帳戶版、優分析全部講義。",
     "Claude 那邊還在跑：1 分 K 抓完後的當沖三招。11/05 收掉的：★ 排序、季報公告日版、基本面 1／D 早年、融資斷頭貨帳戶版、優分析全部講義、產業循環位置（100 多組都不穩，不拿來選股）。"),
    ("、循環課「剛進入價漲期」（18.9%／−60%）、優分析", "、循環課「剛進入價漲期」（18.9%／−60%）與產業循環位置（★／MGK 排序濾網、獨立選股 100 多組都不穩）、優分析"),
]


STALE += [("['本月淨值 −5%', '★ 停開新倉到下個月（年化 +1.6 點、9/10 年）。連輸減半、回落減碼都不要。'],", "['本月淨值 −5%', '照買，不要停（11/05 晚更正：這條沒有保護作用——在你現在的設定（95%、均量大先）會讓最大回撤從 −30.5% 變 −39.2%；年化多的 1.6 點只靠 2020、2021、2026 三年；換成 99% 或別的排序就變成少 3～11 點）。連輸減半、回落減碼也都不要。'],"), ("['★（6 槽、抱 20 天）', '滾動 30 筆勝率 < 33%；30 筆平均每筆 < −2%；連虧 12 筆；帳戶回撤 −25%；滾動 12 個月落後 0050 含息 26 點', '勝率 < 25%；平均 < −4%；連虧 14 筆；回撤 −35%；落後 45 點', '歷史最差：勝率 27%、連虧 11 筆、回撤 −30.5%（2022），之後活回來；35% 這種線會誤殺'],", "['★（6 槽、抱 20 天）', '滾動 30 筆只贏 ≤ 7 筆（23%）；30 筆平均每筆 < −5%；連虧 12 筆；帳戶從高點回撤 −33%', '只贏 ≤ 5 筆（17%）；平均 < −7%；連虧 15 筆；回撤 −40%', '11/05 晚照均量大先、100 種買進順序重定：回撤中位 −27%、最差 −31%（99% 版最差 −39%）；30 筆勝率最低 23%；平均最低 −4.5%（99% 版 −5.9%）；連虧最多 11 筆。原本「回撤 −25% 警戒、平均 < −4% 停用」一半以上的順序都會碰到，作廢；落後 0050 不當停用條件（2026 年 0050 +63% 會誤觸）'],"), ('原則：停用線放在「歷史上從來沒發生過」的地方，警戒線放歷史 5 百分位；回測裡不會誤觸，實單碰到就代表行為已經超出歷史經驗。每月底對一次（★ 的滾動數字「實戰紀錄」算得出來）。依據 11/05「停用條件_建議.md」。', '原則：停用線放在「歷史上從來沒發生過」的地方（★ 用 100 種買進順序算），警戒線放在很少碰到的地方；回測裡不會誤觸，實單碰到就代表行為已經超出歷史經驗。每月底對一次（★ 的滾動數字「實戰紀錄」算得出來）。依據「停用條件_建議.md」與 11/05 晚「★回撤與月停_更正.md」。')]
RADAR_TXT = [("warn.push('帳戶規則：本月淨值 −5% 就不開新倉到下個月；總淨值從高點回落 30% 全部停下來。不停損、不加碼、不攤平。');", "warn.push('帳戶規則：不停損、不加碼、不攤平；本月虧多少都照買（月 −5% 停開新倉 11/05 晚測過沒有保護作用）。★ 帳戶從高點回撤 −33% 部位減半、−40% 退回紙上（回測最差 −31%）。');"), ('帳戶層級的規則（本月淨值 −5% 不開新倉、從高點回落 30% 全部停）沒有自動套用：紀錄照每個訊號記，要不要停你自己判斷。', '帳戶層級的規則（★ 從高點回撤 −33% 部位減半、−40% 退回紙上；見作戰手冊 Ⓔ 停用線）沒有自動套用：紀錄照每個訊號記，要不要停你自己判斷。'), ('"a": "本月不再開新倉，等下個月；總淨值從高點回落 30% 就全部停下來檢討。這是事先寫好的撤退線，不看心情。"', '"a": "照買，不要停：月 −5% 停開新倉在你現在的設定會讓最大回撤更深（−30.5% → −39.2%），沒有保護作用。事先寫好的撤退線是 ★ 帳戶從高點 −33% 部位減半、−40% 退回紙上，不看心情。"'), ('"a": "先看有沒有碰到事先寫好的撤退線（你的是從高點回落 30%）；沒碰到就照規則走。恐慌砍在低點，之後常不敢買回。"', '"a": "先看有沒有碰到事先寫好的撤退線（★ 帳戶是從高點 −33% 部位減半、−40% 退回紙上）；沒碰到就照規則走。恐慌砍在低點，之後常不敢買回。"'), ('"x": "帳戶規則：本月淨值 −5% 就不開新倉；從高點回落 30% 全部停"', '"x": "帳戶規則：月虧照買；★ 帳戶從高點 −33% 部位減半、−40% 退回紙上"'), ('；候選比空位多時先買 20 日均量大的；本月 −5% 就停到下個月；總淨值從高點回落 30% 全部停下來重來。', '；候選比空位多時先買 20 日均量大的；月虧照買（「本月 −5% 停開新倉」11/05 晚測過沒有保護作用）；★ 帳戶從高點回撤 −33% 部位減半、−40% 退回紙上。'), ('沒有套用上面「本月 −5% 停開新倉、回落 30% 重來」兩條。', '沒有套用「本月 −5% 停開新倉、回落 30% 重來」兩條（11/05 晚改成：月虧照買；★ 從高點 −33% 減半、−40% 退回紙上）。'), ('    if k in ("fundhi", "fundall", "fund1D", "best"):\n        return lambda z: (0 if (z[1].get("phi") or 0) >= 0.9999 else 1, -(z[1].get("vol") or 0))\n', '')]



def apply_sb(src, only=None):
    done, miss = [], []
    for head, hd, fields in SB_UPDATES:
        if only and not any(k in head for k in only):
            continue
        rng = _find_block(src, head)
        if not rng or rng[1] is None:
            miss.append(head[:40]); continue
        s, e = rng
        block = src[s:e]
        block = _set_head(block, **hd)
        for k, v in fields.items():
            block = _set_field(block, k, v)
        src = src[:s] + block + src[e:]
        done.append(head[:40])
    return src, done, miss


def main():
    if not os.path.exists(TARGET):
        print("  找不到 %s" % TARGET); return 1
    with io.open(TARGET, "r", encoding="utf-8") as f:
        src = f.read()
    if MARK1 not in src:
        sys.path.insert(0, HERE)
        try:
            import patch_playbook
            print("  還沒加過作戰手冊，先跑 patch_playbook.py …")
            r = patch_playbook.main()
            if r:
                print("  patch_playbook 沒成功（%s），停止。" % r); return 2
            with io.open(TARGET, "r", encoding="utf-8") as f:
                src = f.read()
        except ImportError:
            print("  找不到 patch_playbook.py（要跟這支放同一個資料夾）"); return 2
    if MARK2 in src and MARK3 in src:
        out = src
        for a, b in STALE + RADAR_TXT:
            if a in out:
                out = out.replace(a, b)
        out, done, miss = apply_sb(out, only=("s:cycnew", "★ 基本面"))
        if out == src:
            print("  已經是最新的了（tw_radar.py 裡有 %s 和 %s）。重新啟動雷達即可。" % (MARK2, MARK3)); return 0
        try:
            compile(out, TARGET, "exec")
        except SyntaxError as e:
            print("  改完語法有錯（%s），沒有存檔。" % e); return 3
        shutil.copyfile(TARGET, TARGET + ".bak_playbook2b")
        with io.open(TARGET + ".tmp", "w", encoding="utf-8", newline="") as f:
            f.write(out)
        os.replace(TARGET + ".tmp", TARGET)
        print("  已經更新過，這次換成 11/05 晚的最終結論：產業循環位置、★ 停用線重定、作廢「本月 −5% 停開新倉」與「回落 30% 全停」（備份 tw_radar.py.bak_playbook2b）。重新啟動雷達即可。"); return 0
    bak = TARGET + ".bak_playbook2"
    shutil.copyfile(TARGET, bak)
    out = src; notes = []
    # 1. 作戰手冊
    if MARK2 not in out:
        ok = True
        for a, b, new in PB_REPL:
            i = out.find(a); j = out.find(b, i) if i >= 0 else -1
            if i < 0 or j < 0 or out.count(a) != 1:
                notes.append("作戰手冊：找不到 %s，這一段沒換" % a); ok = False; continue
            out = out[:i] + new + out[j + len(b):]
        for a, b in PB_SMALL:
            if out.count(a) == 1:
                out = out.replace(a, b, 1)
            else:
                notes.append("作戰手冊：找不到「%s…」（%d 處）" % (a[:28], out.count(a)))
        for pre, new in ((NOTE_OLD_PREFIX, NOTE_NEW), (TODO_NOTE_OLD_PREFIX, TODO_NOTE_NEW)):
            i = out.find(pre)
            if i >= 0:
                j = out.find("</div>'", i)
                if j > 0:
                    out = out[:i] + new + out[j + len("</div>'"):]
                    continue
            notes.append("作戰手冊：說明文字沒換（%s…）" % pre[-20:])
        notes.append("作戰手冊：%s" % ("已更新" if ok else "部分更新"))
    for a, b in RADAR_TXT:
        if a in out:
            out = out.replace(a, b)
    # 2. MGK 卡
    if MARK3 not in out:
        c1, c2, c3, c4 = out.count(PY_ANCHOR), out.count(API_ANCHOR), out.count(JS_ANCHOR), out.count(JS_CALL_OLD)
        if c1 == 1 and c2 == 1 and c3 == 1 and c4 == 1:
            out = out.replace(PY_ANCHOR, PY_MGK + PY_ANCHOR, 1).replace(API_ANCHOR, API_NEW + API_ANCHOR, 1)
            out = out.replace(JS_ANCHOR, JS_MGK + JS_ANCHOR, 1).replace(JS_CALL_OLD, JS_CALL_NEW, 1)
            notes.append("MGK 名單卡：已加（/api/mgk）")
        else:
            notes.append("MGK 名單卡：錨點不符（ltrade_today %d、/api/today %d、renderToday %d、卡片順序 %d），沒加" % (c1, c2, c3, c4))
    # 3. 策略分類
    out, done, miss = apply_sb(out)
    notes.append("策略分類：更新 %d 筆%s" % (len(done), ("，找不到：" + "、".join(miss)) if miss else ""))
    try:
        compile(out, TARGET, "exec")
    except SyntaxError as e:
        print("  改完語法有錯（%s），沒有存檔。備份在 %s" % (e, os.path.basename(bak))); return 3
    with io.open(TARGET + ".tmp", "w", encoding="utf-8", newline="") as f:
        f.write(out)
    os.replace(TARGET + ".tmp", TARGET)
    for s in notes:
        print("  " + s)
    print("  完成。備份在 %s。重新啟動台股雷達 → 「今天要做什麼」：作戰手冊多了 Ⓔ 停用線和 MGK，往下多一張「MGK 名單」卡；「策略分類」MGK 在「可以用」。" % os.path.basename(bak))
    return 0


if __name__ == "__main__":
    sys.exit(main())
