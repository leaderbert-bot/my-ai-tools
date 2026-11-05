# 任務簡報：產業循環位置（循環課／優分析）能不能用在選股——10 年回測

工作目錄 SP = /tmp/claude-0/-home-user-my-ai-tools/bb9482f7-4c31-5f24-a06a-81bc958a76a4/scratchpad
所有腳本放在 SP/stagetest/，用 `cd SP && python3 stagetest/xxx.py`（不要加 -I，腳本開頭 `import sys; sys.path.insert(0, SP)`）。
資料是使用者自己的歷史資料（台股 2016-01-04～2026-10-30），不是外部下載，可以直接 import。
一支腳本控制在 20～30 分鐘內跑完（用 `timeout 1800`）；先用小範圍試跑再跑全部。結果一律寫到 SP/stagetest/<你的track>_out.txt，最後回傳 JSON。

## 背景（使用者是台股散戶，有一套自己的規則系統）
- ★（fundhi）：6 槽、抱 20 天，候選排序目前用「當天創新高優先、同級 20 日均量大先」。11/05 測過的排序結果（30 次同分隨機的中位數）：
  phi≥0.95 設定 現行 37.1%（33.1～45.3），純隨機 100 次中位 32.1～32.5%；phi≥0.99 設定 現行 43.2%（32.0～50.8），純隨機中位 35.7～36.2%。
  ROIC 當排序鍵只加 0.6～3 點、在隨機範圍內 → 沒改雷達。
- MGK（股價先漲 >20 點＋營收第一次跳升，抱 60 天、10 槽 × 10%、閒錢 0050 含息）：年化 50.5%、回撤 −38.1%、306 筆、每筆 +16.1%、11 年贏 0050 九年。這是系統裡最強的一條。
- 0050 含息 2016-06～2026-10：年化 23.8%、回撤 −33.9%。
- 循環課「單一股票剛進入價漲期」當獨立策略（11/05 測）：年化 18.9%、回撤 −60%，輸 0050。
- 優分析 14 條財報規則（ROIC、毛利率、營益率、資本支出…）全部測過：當買點都輸 0050；唯一站得住的是「股價先動」（公布前 60 日比 0050 多 20 點）。
- 這次要測的是課程「原本的用法」：**看產業在哪一期，再從那個產業裡挑股**。

## 使用者的驗證標準（一定要照做）
1. 兩個獨立時段都要看：前半 ≤ 2021-06-30、後半 ≥ 2021-07-01（★ 的引擎用 2021-12-31／2022-01-03 切）。
2. 同一天候選多時的買進順序要隨機化：規則只決定第一排序，同分打亂，跑 30 個 seed 看中位／最低／最高；對照是「純隨機 100 次」的中位數。
3. 相鄰參數要看（門檻 ±）；一兩年撐起來的不算（看逐年、數「贏 0050 含息」的年數）。
4. 一律跟「只抱 0050 含息」比，不是跟 0 比。報每個數字時附 n。
5. 不准編數字；跑不出來就說跑不出來。

## 資料與引擎（全部在 SP）
- px.pkl：(px, cal, mk)。px[code][date] = [open, high, low, close, volume(張)]；cal = 交易日 list（'YYYY-MM-DD'）；mk[code] = 'sii'/'otc'。
- tr50.pkl：(tr50, divs)。tr50 = 0050 含息淨值 list，對齊 cal。
- dl/rev10.json：{"m": {YYYYMM: {code: 月營收(仟元)}}}。月營收在下個月 10 日公布 → 腳本一律用「下月 11 日後第一個交易日」才可用（mgk_test.py 的 avail(ym)）。
- mopsfin/mopsfin_<sii|otc>_<民國年>_<季>.json：{"rows": {code: {rev, gross, op, pretax, net, eps, assets, liab, equity, ca, cl, bvps}}}，損益數字是「年初到該季累計」。法定公布期限 Q1 5/15、Q2 8/14、Q3 11/14、Q4 隔年 3/31。
- cands.pkl：★ 的每日候選 13,708 筆（2017-08～2026-10），每筆 dict(d, code, tag, phi, v20, px, r3, yoy, mom, hi12, eg, mgk, fei105, fei807, jump, first, ret20, ret60, ret60x, eps2up)。
- star_rank.py：★ 帳戶引擎。重用方式見 star_rank_roic.py 前 10 行：
    sys.argv = ["star_rank.py", "cands.pkl", "0.95"]   # 或 "0.99"
    exec(open("star_rank.py").read().split("def main():")[0])
  之後有 C（候選 list）、byday、days、run(keyfn=None, seed=None, cap=3, slots=6, start=None, end=None) → (eq_curve, trades)、stats(eq, tr) → dict(cagr, mdd, n, win, avg, yr)。
  keyfn 回傳 tuple 當排序鍵（小的先買）；seed 給了會先打亂再排序（同分隨機）。濾網＝直接改 C / byday / days（star_rank_roic_filt.py 的 setC 示範）。
- mgk_test.py：MGK 引擎。重用方式見 cycle_stage_test.py 第 5 行：
    exec(open('mgk_test.py').read().split('b = run([])')[0])
  之後有 px, cal, idx, tr50, rev, ym_prev(ym,k), avail(ym), c50（0050 收盤 list）, close_near(code,d), COST=0.0047, HOLD=60,
  sig（MGK 訊號 list，每筆 dict(code, d, px, r60x, yoy)；先漲版＝[s for s in sig if s['r60x']>20]），
  run(S, seed=None, slots=10, frac=0.10, start="2016-06-01", end=cal[-1]) → dict(cagr, mdd, n, avg, win, yr)；沒給 seed 時同一天照 −r60x 排。
  訊號 dict 至少要有 code, d, px（買價＝d 收盤）, r60x。想改抱的天數就在 exec 之後改全域變數 HOLD。
- stage_lib.py：產業位置查詢（docstring 有完整欄位說明）。import stage_lib as S；S.ym_at(d)、S.ind_of(code)、S.ind_stage(code, d, lag=0)、S.grp_stages(code, d)、S.stock_stage(code, d, lag=0)、S.members(產業名)、S.ind_series(產業名)、S.industries()；原始表在 S.D['ind'] / S.D['grp'] / S.D['stock']（鍵是 (名稱或代號, 'YYYYMM')），原始 rev3/breadth/gm_d/mom60 都在，可以自己換門檻。
  位置定義：price 價漲期＝產業 rev3 中位數 ≥ 10 且 gm_d 中位數 ≥ 1.0；vol 量增＝rev3 ≥ 10 且 gm_d < 1.0；vol? ＝rev3 ≥ 10 但 gm_d 不明（主要是 2016 年）；down 衰退＝rev3 < 0；flat 其他。new_price＝這個月 price、3 個月前不是。
  個股 stock stage：up＝r3 ≥ 10 且累計季毛利率比去年同季高 ≥ 1.5 點（跟 11/05 循環課測試同定義）。
- ind_stage.py：產生 stage_data.pkl 的程式（稽核用）。ua_roic_test.py：事件統計（60 天超額 vs 0050 中位／平均／勝率／前後半）的寫法範例。

## 已知的坑
- 同分排序的偷渡：Python sort 穩定，同分會照原順序（代號小先）→ 一定要先 shuffle 再 sort（引擎的 seed 參數）。
- 槽位瓶頸：★ 大多數日子只有 1～3 檔候選、6 槽常是空的，所以「排序」能改的有限，「濾網」會直接少交易。要報交易數變化。
- 產業成員用的是今天的上市名單（industry_map 只有現役 1,981 檔）→ 下市股不在產業中位數裡（倖存者偏差），★ 候選與 MGK 訊號本身有下市股（px 有），查不到產業時當 None 處理並報筆數。
- groups.csv 是使用者今天定的主題族群（CPO、RUBIN、SpaceX、散熱…），拿來回測 2016～2026 有事後之見，結果只能當參考，要標明。
- 2016 年的產業 gm_d 多半是 None（季報快取從 2015Q4 起），price 位置從 2017-04 才可靠。
- 事件擠在每月 11 日後那一天與季報期限後 → 10 槽一下就滿；帳戶模擬的年化只代表一種排序，事件統計（每筆 60 天超額）比較可信，兩個都要報。
- 流動性門檻一律：進場日前 20 日均量 ≥ 500 張、收盤 ≥ 10 元、當天沒鎖漲停（mgk_test.py 的寫法）。
