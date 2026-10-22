"""台股動能、基本面財報與籌碼分佈綜合分析系統（Taiwan Stock Strategy Analyzer, TWSA）。

模組一覽：
    twsa.config        —— 路徑與設定（含原本「台股雷達」資料夾位置）
    twsa.data          —— 資料擷取（requests）、台股雷達本機資料轉接、快取、模擬資料
    twsa.indicators    —— 均線、動能、籌碼集中度、營收年增等指標
    twsa.strategies    —— 均線多頭排列／動能突破／籌碼集中／營收成長／綜合策略
    twsa.backtest      —— 回測引擎：勝率、最大回撤（MDD）、報酬、交易明細
    twsa.screener      —— 對一整池股票跑策略 + 回測
    twsa.report        —— 匯出 Excel / CSV
    twsa.service       —— GUI 與網頁共用的服務層
    twsa.web.server    —— 本地網頁儀表板（只用標準庫 http.server）
    twsa.gui_tk        —— Tkinter 桌面介面（選用）
"""

__version__ = "1.0.0"
