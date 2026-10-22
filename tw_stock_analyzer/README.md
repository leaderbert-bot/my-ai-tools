# 台股動能、基本面財報與籌碼分佈綜合分析系統（TWSA）

用 Python 打造的台股選股與回測工具，整合三個面向：

| 面向 | 看什麼 | 資料 |
|---|---|---|
| **動能** | 均線多頭排列、突破前高、量能放大 | 個股日線開高低收量 |
| **籌碼** | 三大法人買賣超、法人淨買超占成交量（籌碼集中度）、外資／投信連買、集保 400 張以上大戶持股比例 | 三大法人、集保股權分散表 |
| **基本面** | 月營收年增／月增、近 3 月平均年增、連續年增月數、EPS、毛利率、本益比 | 月營收、季報 |

而且**直接接上你原本的「台股雷達」**（`C:\Users\leade\Desktop\Dropbox\00money`）：
台股雷達每天收盤後累積在 `data/` 裡的全市場行情、三大法人、月營收、族群分類、自選股，
這套系統會優先讀那份本機資料，**不用再向交易所重抓一次**，族群分類也直接拿來當選股範圍。

> 本工具僅做公開資料的機械式篩選與歷史回測，**不構成任何投資建議**。

> **這是跟台股雷達分開的另一套系統**，放在 `C:\Users\leade\Desktop\Dropbox\00_TWSA`，
> 網址是 8900（台股雷達是 8899）。兩者的關係見 [`與台股雷達的關係.md`](與台股雷達的關係.md)。

---

## 目錄

1. [功能總覽](#功能總覽)
2. [安裝](#安裝)
3. [快速開始](#快速開始)
4. [與台股雷達整合](#與台股雷達整合)
5. [網頁儀表板使用說明](#網頁儀表板使用說明)
6. [Tkinter 桌面版](#tkinter-桌面版)
7. [命令列用法](#命令列用法)
8. [策略說明](#策略說明)
9. [回測規則（勝率與 MDD 怎麼算）](#回測規則勝率與-mdd-怎麼算)
10. [資料來源與優先順序](#資料來源與優先順序)
11. [設定檔](#設定檔)
12. [資料夾結構](#資料夾結構)
13. [單元測試](#單元測試)
14. [新增自己的策略](#新增自己的策略)
15. [常見問題](#常見問題)

---

## 功能總覽

- **資料擷取與處理**（pandas + requests）
  - 個股歷史價量：FinMind → 證交所 `STOCK_DAY` → 櫃買中心個股日成交（自動備援）
  - 三大法人買賣超：FinMind（個股歷史）、證交所 `T86`（單日全市場）
  - 籌碼分佈：FinMind 集保股權分散表 → 400 張以上大戶持股比例、股東人數
  - 月營收與季報：FinMind（EPS、毛利率、營益率、淨利率）
  - **台股雷達本機資料轉接**：`px_history.json`、`kline/*.json`、`inst_hist.json`、`history.json`、`groups.csv`、`watchlist.json`、`stock_names.json`、`markets.json`
  - CSV 快取（收盤後只採信 15:00 之後寫入的行情快取）
- **策略篩選引擎**：6 個內建策略，參數可在畫面上調整，一行 `@register` 就能新增
- **回測引擎**：隔日開盤進場、停損／停利／跌破月線／持有 N 日出場、含手續費與證交稅；
  算出**勝率、最大回撤（MDD）**、總報酬、年化報酬、獲利因子、持股時間比例，並與「買進持有」對照；
  整池股票另算**合併勝率**與**等權重組合的 MDD**
- **介面**
  - **本地網頁儀表板**（主要介面，只用標準庫，免裝 Flask）：輸入代號查詢、K 線＋均線＋訊號標記、法人／營收／財報表格、回測權益曲線、一鍵選股、匯出 Excel / CSV
  - **Tkinter 桌面版**（選用）：同樣的查詢、選股、匯出
  - **命令列**：適合排程或批次
- **80 個單元測試**，已在雲端環境實際執行全部通過

---

## 安裝

### 需求

- Python **3.10 以上**（開發與測試使用 3.13）
- Windows / macOS / Linux 皆可

### 步驟

```bat
:: 1. 進入專案資料夾
cd C:\Users\leade\Desktop\Dropbox\00_TWSA

:: 2. 安裝套件（Windows 也可以直接雙擊 install.bat）
python -m pip install -r requirements.txt
```

`requirements.txt` 只有五個套件：`pandas`、`numpy`、`requests`、`openpyxl`（寫 Excel）、`pytest`（跑測試）。

> 建議使用虛擬環境：`python -m venv .venv` → `.venv\Scripts\activate`（macOS/Linux 為 `source .venv/bin/activate`）再安裝。

### FinMind 金鑰（選用）

沒有金鑰也能用，但每小時請求次數較少。到 [FinMind](https://finmindtrade.com/) 註冊後取得 token，擇一設定：

```bat
:: 方法一：環境變數（目前視窗有效）
set FINMIND_TOKEN=你的token

:: 方法二：寫進設定檔 twsa_settings.json（見「設定檔」一節）
```

---

## 快速開始

### 先用模擬資料看看長什麼樣子（不連網）

```bat
python -m twsa --demo web
```

或雙擊 **`start_demo.bat`**。瀏覽器會自動打開 `http://127.0.0.1:8900/`，
右上角會標示「**模擬資料（離線展示）**」—— 這些數字是程式產生的，不是真實行情。

### 用你的台股雷達資料

```bat
python -m twsa web
```

或雙擊 **`start_dashboard.bat`**。程式會自動找 `C:\Users\leade\Desktop\Dropbox\00money`；
放在別的地方就加 `--radar-dir`：

```bat
python -m twsa --radar-dir "D:\Dropbox\00money" web
```

右上角顯示「**實際資料｜已連結台股雷達**」就代表接上了。

---

## 與台股雷達整合

### 讀哪些檔案

| 台股雷達檔案 | 內容 | 在這套系統裡的用途 |
|---|---|---|
| `data/px_history.json` | 全市場每日開高低收量 | 個股行情（K 線、均線、回測） |
| `data/kline/<代號>-<年月>.json` | 單檔補抓的日 K | 補 px_history 沒有的日期 |
| `data/inst_hist.json` | 三大法人買賣超歷史 | 籌碼集中度、外資／投信連買 |
| `data/history.json` | 月營收歷史 | 營收年增、近 3 月平均年增 |
| `data/groups.csv` | 你的族群分類（64 組） | 選股範圍「我的族群（全部）」與每一組「族群：○○」 |
| `data/watchlist.json` | 自選股 | 選股範圍「自選股」 |
| `data/stock_names.json`、`groups.csv` 名稱欄 | 代號 → 名稱 | 顯示名稱（自動去掉你加的 `*` 記號） |
| `data/markets.json` | 代號 → 上市／上櫃 | 網路備援時決定先問證交所還是櫃買 |

**只讀不寫**：這套系統不會修改台股雷達的任何檔案，自己的快取與匯出放在 `00_TWSA\data\`。
兩個程式可以同時開（台股雷達 8899、這套 8900）。

### 自動辨識資料格式

台股雷達的 JSON 有兩種常見排法，程式都會自動辨識：

```jsonc
// 以代號為主（kline/*.json、lend_hist.json 都是這種）
{"2330": [["2026-10-01", 開, 高, 低, 收, 量], ...]}

// 以日期為主
{"2026-10-01": {"2330": [開, 高, 低, 收, 量], ...}}
```

每一列可以是 list（依欄位順序）或 dict（依欄名，`open`/`o`/`開盤` 這類中英文別名都認）；
月營收的月份 key 認得 `2026-08`、`202608`、民國 `11508`、`115/08`；外層包了 `{"data": …}` 也會自動拆開。

讀進來的 K 棒會做跟台股雷達「資料檢核」一樣的物理檢查（最低 ≤ 開／收 ≤ 最高、價格 > 0），不合理的直接略過。

### 欄位順序不同時

如果你的 `inst_hist.json` 每列是 `[投信, 外資, 自營]` 這種不同順序，在 `twsa_settings.json` 指定：

```json
{"radar_columns": {"inst": ["trust", "foreign", "dealer", "total"]}}
```

### 法人買賣超的單位（張 / 股）

成交量是「股」，法人買賣超若以「張」記錄，籌碼集中度會小 1000 倍。程式預設**自動判斷**
（法人有進出那幾天的 |買賣超| 中位數不到成交股數中位數的 0.2% → 判定為張並 ×1000）。
想指定就在設定檔加 `"radar_inst_unit": "lots"` 或 `"shares"`。

### 一個要先講清楚的限制

我在雲端環境透過 Dropbox 讀了你的 `00money` 資料夾：`README.md`、`groups.csv`、`watchlist.json`、
`px_days.json`、`kline/*.json`、`lend_hist.json` 的格式都實際看過，轉接器照著寫，也用相同格式做了測試資料。
但 **`px_history.json`（55MB）、`inst_hist.json`（2.2MB）、`history.json`（2MB）與 `tw_radar.py`（3.5MB）太大，
無法在雲端完整讀取**，所以這三個檔案的內部排法是依 `kline/` 的格式與常見寫法推定、並做成自動辨識。
第一次在你電腦上執行時，請到儀表板的「**系統狀態**」與「個股查詢」看資料來源是不是「台股雷達本機資料」；
若某一項顯示走網路或無資料，用 `radar_columns` 調整或把那個檔案開頭幾行貼給我，我再對上格式。

---

## 網頁儀表板使用說明

啟動後會開 `http://127.0.0.1:8900/`（只綁本機，別台電腦連不到）。三個分頁：

### 1. 個股查詢

- 輸入代號（例如 `2330`）按 Enter 或「查詢」
- 最上面：收盤價、漲跌（**台股慣例紅漲綠跌**，並附 ▲▼ 符號，色盲也看得出方向）、每一種資料各來自哪個來源
- **今日策略檢查**：6 個策略今天各自成立（✔）或不成立（✗）
- **K 線圖**：近 250 根日 K、MA5／MA20／MA60、成交量，**▲ 標出所選策略的歷史進場訊號**
- 指標快照：均線、20 日漲幅、RSI、量比、法人淨買超占量、外資／投信連買、大戶持股與 4 週變化、營收年增、近四季 EPS、本益比、毛利率
- 三大法人近 20 日（張）、月營收近 12 個月（億元，年增／月增自己重算）、財報近 8 季、集保大戶
- **回測績效**：交易次數、勝率、平均報酬、獲利因子、總報酬、年化、**MDD**、持股時間比例、買進持有對照，加上權益曲線與每一筆交易明細

### 2. 策略選股

1. 選**策略**（下面會顯示白話說明與可調參數）
2. 選**選股範圍**：自選股／我的族群（全部）／族群：○○（每一組都可以單獨選）；或在右邊**自行輸入代號**（逗號、空白都可以）
3. **最近幾根內出現訊號**：0 = 只看今天；填 5 = 最近 5 根內出現過都算，表格會標「幾根前」
4. 調整**回測設定**：持有天數、停損 %、停利 %、手續費折扣、是否跌破月線出場
5. 按 **▶ 一鍵執行選股**，旁邊會顯示進度
6. 上方彙總：掃描檔數、今日符合、回測總交易數、**整體勝率**、每筆平均報酬、**等權組合總報酬與 MDD**、個股最差 MDD
7. 表格可點欄名排序；**點任一列直接跳到該檔的個股查詢**
8. **⤓ 匯出 Excel** 或 **⤓ 匯出 CSV**

### 3. 系統狀態

顯示目前模式、台股雷達資料夾、偵測到哪些檔案、是否有 FinMind 金鑰、每個選股範圍有幾檔。連不上或資料怪怪的時候先看這頁。

### 匯出的 Excel 長什麼樣

一個 `.xlsx` 檔四張工作表：

| 工作表 | 內容 |
|---|---|
| 選股結果 | 範圍內每一檔：是否符合、指標值、回測交易次數／勝率／平均報酬／總報酬／MDD、買進持有對照、資料來源 |
| 符合清單 | 只有今天符合的 |
| 回測交易明細 | 每一筆：代號、名稱、進場日／價、出場日／價、出場原因、持有天數、報酬% |
| 參數與彙總 | 策略、參數、回測設定、整池彙總、略過的股票與原因、免責聲明 |

CSV 用 **UTF-8 with BOM** 編碼，Excel 直接雙擊開中文不會亂碼。

---

## Tkinter 桌面版

```bat
python -m twsa gui
```

或雙擊 **`start_gui.bat`**。有「個股查詢」與「策略選股」兩個分頁，選股在背景執行緒跑、視窗不會卡，
匯出時會跳出存檔對話框。Windows 官方 Python 內建 Tkinter；Linux 若出現 `No module named tkinter`，
請安裝 `python3-tk`（或直接用網頁版，功能較完整）。

---

## 命令列用法

```bat
python -m twsa list                                   :: 列出策略與選股範圍
python -m twsa stock 2330                             :: 單一個股：策略檢查 + 回測
python -m twsa stock 2330 --strategy combo
python -m twsa screen --strategy combo --universe 自選股
python -m twsa screen --strategy chip_concentration --universe "族群：散熱族群" --export xlsx
python -m twsa screen --strategy momentum_breakout --codes 2330,2317,2454 --lookback 5 --hold-days 10 --stop-loss 6
python -m twsa web --port 9100 --no-open              :: 換埠、不自動開瀏覽器
python -m twsa gui

:: 共用選項（放在子指令前面）
python -m twsa --demo ...                             :: 模擬資料
python -m twsa --offline ...                          :: 不連網，只用台股雷達與快取
python -m twsa --radar-dir "D:\Dropbox\00money" ...   :: 指定台股雷達位置
python -m twsa --config my_settings.json ...          :: 指定設定檔
```

`--export` 的檔案存在 `00_TWSA\data\exports\`。

---

## 策略說明

| 代號 | 名稱 | 條件 | 可調參數 |
|---|---|---|---|
| `ma_bull` | 均線多頭排列 | 收盤 > MA5 > MA10 > MA20 > MA60，且 MA20 比 5 日前高（月線上揚） | 是否也要求 MA60 > MA120 |
| `momentum_breakout` | 動能突破 | 收盤 > 前 20 日最高價、當日量 ≥ 20 日均量 × 倍數、20 日漲幅 > 下限、收盤站上 MA60 | 量能倍數（1.5）、20 日漲幅下限 |
| `chip_concentration` | 籌碼集中度 | 近 10 日三大法人合計淨買超 ÷ 近 10 日成交量 ≥ 門檻；可加外資連買天數、集保大戶 4 週增加 | 門檻（5%）、外資連買天數、是否要求大戶增加 |
| `revenue_growth` | 營收成長 | 最新已公告月營收年增 ≥ 門檻，且近 3 月平均年增 ≥ 門檻 | 年增門檻（20%）、近 3 月門檻（10%） |
| `combo` | 綜合：多頭 + 籌碼 + 營收 | 均線多頭排列 **且** 法人淨買超占量 ≥ 門檻 **且** 營收年增 > 門檻 | 籌碼門檻（3%）、營收門檻（0%） |
| `breakout_with_chips` | 突破 + 法人進場 | 動能突破當天，法人淨買超占量 ≥ 門檻（過濾沒有籌碼支撐的假突破） | 量能倍數、籌碼門檻（2%） |

### 「主力籌碼集中度」的定義

傳統的「主力集中度」要用券商分點進出資料（前 15 大買超分點 − 前 15 大賣超分點），
那份資料官方不免費提供。這裡用兩個**可以免費、穩定取得**的替代指標：

1. **法人籌碼集中度** ＝ 近 N 日三大法人合計淨買超股數 ÷ 近 N 日成交股數 × 100%。
   數字越高，代表這段時間成交量裡有越大比例被法人吃下。
2. **集保大戶持股比例** ＝ 集保股權分散表中持股 400 張（40 萬股）以上級距的持股比例合計，
   以及它 4 週內的變化。大戶比例上升、股東人數下降，通常代表籌碼往少數人集中。

有分點資料的話，可以照「新增自己的策略」一節加一個欄位即可。

---

## 回測規則（勝率與 MDD 怎麼算）

刻意保守，避免回測數字好看但實際做不到：

1. **不偷看未來**
   - 訊號由「不成立」轉「成立」那天收盤後才知道 → **隔天開盤價進場**
   - 月營收要到**次月 10 日**才看得到；季報要到法定期限（Q1 5/15、Q2 8/14、Q3 11/14、Q4 隔年 3/31）；集保週資料隔一個交易日才採用
2. 一次只持有一筆；持有中出現的新訊號忽略
3. **出場**（先到先出）
   - 停損：盤中最低觸及停損價 → 以停損價出場；**跳空開低則以開盤價出場**（更差的價格）
   - 停利：盤中最高觸及停利價 → 以停利價出場（跳空開高以開盤價）
   - 同一天停損停利都碰到 → **假設先停損**
   - 跌破月線（選用）：收盤 < MA20 當日收盤出場
   - 持有滿 N 個交易日 → 當日收盤出場
   - 資料結束仍持有 → 標「未平倉」，**不計入勝率**
4. **成本**：手續費 0.1425% × 折扣（預設 6 折，買賣各一次）＋ 證交稅 0.3%（賣出）
5. **指標定義**
   - **勝率** ＝ 報酬 > 0 的已平倉交易 ÷ 已平倉交易數
   - **MDD（最大回撤）** ＝ 權益曲線上「從前一個高點往下跌最多的比例」。權益曲線逐日以收盤價計值，
     持有時 100% 資金在該檔、空手時是現金
   - 總報酬、年化報酬（CAGR）、獲利因子（總獲利 ÷ 總虧損）、平均持有天數、持股時間比例
   - **買進持有**：同期間一直抱著的報酬與 MDD，用來判斷策略到底有沒有比較好
   - **整池彙總**：所有股票的交易合併算勝率；把每檔的權益曲線取平均當作「等權重組合」，再算組合的報酬與 MDD

---

## 資料來源與優先順序

| 模式 | 順序 |
|---|---|
| 一般 | **台股雷達本機資料** → 今日快取 → FinMind → 證交所 → 櫃買中心 → 過期快取（並標明「網路失敗」） |
| `--offline` | 台股雷達本機資料 → 快取，不連網 |
| `--demo` | 一律模擬資料（固定亂數種子，每次結果相同） |

每一種資料最後從哪裡來都會顯示在畫面上與 Excel「選股結果」的「資料來源」欄，
**不會在你不知情的情況下拿舊資料或模擬資料充數**。

台股雷達目前沒有的資料（集保大戶、季報），會自動改走 FinMind。

網路請求之間預設間隔 1.2 秒（`request_gap`），避免被交易所鎖 IP。

---

## 設定檔

把 `twsa_settings.example.json` 複製成 `twsa_settings.json` 再修改（這個檔已列在 `.gitignore`，金鑰不會被提交）：

```json
{
  "radar_dir": "C:\\Users\\leade\\Desktop\\Dropbox\\00money",
  "finmind_token": "",
  "use_network": true,
  "request_gap": 1.2,
  "port": 8900,
  "radar_inst_unit": "auto",
  "radar_columns": {
    "price": ["open", "high", "low", "close", "volume"],
    "inst": ["foreign", "trust", "dealer", "total"],
    "revenue": ["revenue"]
  }
}
```

| 設定 | 說明 | 預設 |
|---|---|---|
| `radar_dir` | 台股雷達資料夾（含 `data/` 的那一層） | 自動找 `C:\Users\leade\Desktop\Dropbox\00money` |
| `finmind_token` | FinMind 金鑰 | 無 |
| `use_network` | 是否連網 | `true` |
| `request_gap` | 請求間隔秒數 | `1.2` |
| `port` | 網頁埠號 | `8900` |
| `radar_inst_unit` | 台股雷達法人資料單位：`auto` / `lots`（張）/ `shares`（股） | `auto` |
| `radar_columns` | 台股雷達 JSON 每列的欄位順序 | 見上 |

環境變數會覆蓋設定檔：`TWSA_RADAR_DIR`、`FINMIND_TOKEN`、`TWSA_DATA_DIR`。

---

## 資料夾結構

```
00_TWSA/（在 repo 裡叫 tw_stock_analyzer/）
├── README.md                     ← 本說明書
├── 與台股雷達的關係.md            ← 兩套系統的分工、位置、網址
├── requirements.txt              ← 相依套件
├── pyproject.toml                ← 套件設定（含 pytest 設定，可 pip install -e .）
├── twsa_settings.example.json    ← 設定檔範本
├── install.bat                   ← 雙擊安裝套件
├── start_dashboard.bat           ← 雙擊開網頁儀表板（實際資料）
├── start_demo.bat                ← 雙擊開網頁儀表板（模擬資料）
├── start_gui.bat                 ← 雙擊開 Tkinter 桌面版
├── run_tests.bat                 ← 雙擊跑單元測試
├── twsa/
│   ├── __init__.py
│   ├── __main__.py               ← 命令列入口（python -m twsa）
│   ├── config.py                 ← 設定：路徑、台股雷達位置、金鑰
│   ├── data/                     ← 【模組一】資料擷取與處理
│   │   ├── schema.py             ←   統一的資料表格式、營收年增月增重算
│   │   ├── fetchers.py           ←   requests：FinMind、證交所、櫃買中心
│   │   ├── radar_adapter.py      ←   讀台股雷達本機資料（格式自動辨識）
│   │   ├── cache.py              ←   CSV 快取
│   │   ├── sample.py             ←   模擬資料（離線展示／測試）
│   │   └── hub.py                ←   DataHub：依優先序整合各來源
│   ├── indicators.py             ← 【模組二】指標：均線、動能、籌碼集中度、營收（對齊公告日）
│   ├── strategies.py             ← 【模組二】策略篩選引擎（可註冊新策略）
│   ├── backtest.py               ← 【模組二】回測：勝率、MDD、報酬、交易明細
│   ├── screener.py               ← 【模組二】整池選股 + 回測
│   ├── report.py                 ← 匯出 Excel / CSV
│   ├── service.py                ← GUI 與網頁共用的服務層
│   ├── gui_tk.py                 ← 【模組三】Tkinter 桌面版
│   └── web/                      ← 【模組三】本地網頁儀表板
│       ├── server.py             ←   標準庫 http.server + JSON API
│       └── index.html            ←   單頁介面（K 線用 SVG 畫，不需外部套件）
├── tests/                        ← 單元測試（80 個）
│   ├── conftest.py               ←   共用 fixture：假台股雷達資料夾、假網路 session
│   ├── test_indicators.py
│   ├── test_strategies.py
│   ├── test_backtest.py
│   ├── test_fetchers.py
│   ├── test_radar_adapter.py
│   ├── test_hub.py
│   ├── test_screener_report.py
│   └── test_web_cli.py
└── data/                         ← 執行時自動建立（快取 cache/、匯出 exports/），不進版控
```

---

## 單元測試

```bat
python -m pytest        :: 精簡輸出
python -m pytest -v     :: 逐一列出每個測試
```

或雙擊 **`run_tests.bat`**。測試**完全不連網**：網路一律用假的 session 回應，台股雷達用暫存資料夾模擬。

| 測試檔 | 驗證什麼 |
|---|---|
| `test_indicators.py` | 均線、RSI、連續天數；法人集中度精確值；**營收在公告日前看不到**、季報 TTM 與本益比、集保延後一天；MDD 已知值 |
| `test_strategies.py` | 六個策略在上升／下跌／爆量突破／法人買超等情境的成立與不成立；參數轉型 |
| `test_backtest.py` | **隔日開盤進場**、持有 N 日出場、停損（含跳空開低用開盤價）、停利、同日停損停利先停損、跌破月線、手續費與證交稅、未平倉不計勝率、MDD 與權益曲線一致、整池彙總 |
| `test_fetchers.py` | FinMind 價量／法人／集保／營收／財報解析、token 標頭；證交所民國日期與千分位、櫃買張轉股、T86；HTTP 錯誤、斷線、非 JSON |
| `test_radar_adapter.py` | 台股雷達五種 JSON 排法、kline 合併、壞 K 棒過濾、法人張／股自動換算、民國月份、groups.csv（UTF-8 BOM 與 Big5）、自選股、名稱、自訂欄位順序 |
| `test_hub.py` | 來源優先序、FinMind 失敗改走證交所、全部失敗用過期快取、離線不連網、收盤後快取判斷 |
| `test_screener_report.py` | 六策略整池選股、lookback、Excel 四張工作表內容、CSV BOM、服務層輸出可轉 JSON |
| `test_web_cli.py` | 實際啟動網頁伺服器打每個 API、下載 Excel/CSV、錯誤回 JSON；命令列 list/stock/screen/匯出、接台股雷達資料夾 |

在雲端環境（Linux、Python 3.13、pandas 3.0）的實際執行結果：

```
$ python -m pytest
........................................................................ [ 91%]
.......                                                                  [100%]
80 passed in 5.42s
```

另外也實際啟動了網頁儀表板，用無頭瀏覽器操作「個股查詢」與「一鍵選股」，畫面正常、瀏覽器主控台沒有錯誤。

> 雲端環境連不到證交所、櫃買與 FinMind（網路政策封鎖），所以網路擷取是用模擬回應測的；
> 實際連線請在你自己的電腦上跑一次 `python -m twsa stock 2330` 確認。

---

## 新增自己的策略

在 `twsa/strategies.py` 加一個函式即可，網頁、桌面版、命令列、回測、匯出會自動出現：

```python
@register(
    "trust_follow", "投信認養", "籌碼",
    "投信連續買超 N 天以上，且股價站上月線。",
    params=[Param("days", "投信連買天數 ≥", 3, "int")],
    show_cols=["close", "ma20", "trust_buy_streak"],
)
def trust_follow(f, days=3):
    return (f["trust_buy_streak"] >= days) & (f["close"] > f["ma20"])
```

可用的指標欄位（`f[...]`）：`open high low close volume`、`ma5 ma10 ma20 ma60 ma120`、`ma20_slope`、
`roc20 roc60`、`rsi14`、`prior_high`、`vol_ma20 vol_ratio`、`high_250`、`inst_total foreign trust`、
`chip_conc`、`foreign_buy_streak trust_buy_streak`、`big_holder_pct big_holder_chg4w`、
`rev_yoy rev_yoy_3m rev_yoy_streak`、`eps gross_margin operating_margin eps_ttm pe`。

若新策略需要特定資料，在 `twsa/screener.py` 的 `NEEDS` 加一行（例如 `"trust_follow": ("price", "institutional")`），
整池掃描時就只會抓需要的資料。

---

## 常見問題

**Q：右上角沒有出現「已連結台股雷達」？**
到「系統狀態」看 `radar_dir`。不是你的路徑就用 `--radar-dir` 或設定檔指定（指到 `00money` 那一層即可，程式會自己找 `data/`）。

**Q：個股查詢顯示「無資料：FinMind: …」？**
台股雷達沒有這一檔（例如 ETF 或你沒補過的股票），網路備援也失敗。看訊息是哪一種錯誤：
`HTTP 402` 是 FinMind 額度用完（設定 token 或等一小時）、`連線失敗` 是網路被擋。

**Q：籌碼集中度全部是空的？**
代表沒有法人資料。台股雷達的 `inst_hist.json` 沒有這一檔時會改問 FinMind；離線模式下就會是空的。

**Q：「集保大戶」是空的？**
台股雷達沒有存集保股權分散表，這一項一律走 FinMind，需要連網。

**Q：回測勝率很高，可以直接照做嗎？**
不行。回測只代表**過去**在這組規則下的結果，而且 MDD 很大的策略實際上很難抱得住。
請一併看「買進持有」對照、交易次數（太少沒有統計意義）、以及 MDD。

**Q：埠號 8900 被占用？**
`python -m twsa web --port 9100`。

**Q：中文 .bat 亂碼？**
`.bat` 檔內容全部是英文並加了 `chcp 65001`，跟台股雷達踩過的坑是同一個原因。

---

本工具僅整理公開資料並提供機械式篩選與歷史回測，不構成任何投資建議。
