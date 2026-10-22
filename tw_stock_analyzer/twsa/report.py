"""匯出 Excel / CSV 報表。

Excel 一個檔案四張工作表：選股結果、符合清單、回測交易明細、參數與彙總。
CSV 用 utf-8-sig 編碼，直接用 Excel 開中文不會亂碼。
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import strategies
from .screener import ScreenResult

TRADE_LABELS = {
    "entry_date": "進場日", "entry_price": "進場價", "exit_date": "出場日", "exit_price": "出場價",
    "exit_reason": "出場原因", "hold_days": "持有天數", "return_pct": "報酬%", "is_open": "未平倉",
}
SUMMARY_LABELS = {
    "scanned": "掃描檔數", "matched": "今日符合檔數", "stocks": "有資料檔數", "trades": "回測總交易數",
    "win_rate": "整體勝率%", "avg_return": "每筆平均報酬%", "portfolio_return": "等權組合總報酬%",
    "portfolio_mdd": "等權組合MDD%", "worst_stock_mdd": "個股最差MDD%",
}


def _meta_frame(res: ScreenResult) -> pd.DataFrame:
    strat = strategies.get(res.strategy)
    rows = [("策略", strat.label), ("說明", strat.description),
            ("產生時間", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))]
    for p in strat.params:
        rows.append((f"參數：{p.label}", res.params.get(p.key)))
    for k, v in res.backtest.items():
        rows.append((f"回測：{k}", v))
    for k, v in res.summary.items():
        rows.append((SUMMARY_LABELS.get(k, k), v))
    if res.errors:
        rows.append(("錯誤", "；".join(res.errors[:50])))
    rows.append(("聲明", "本報表僅為公開資料的機械式篩選與歷史回測，不構成投資建議。"))
    return pd.DataFrame(rows, columns=["項目", "值"])


def _trades_frame(res: ScreenResult) -> pd.DataFrame:
    if res.trades is None or res.trades.empty:
        return pd.DataFrame(columns=["代號", "名稱"] + list(TRADE_LABELS.values()))
    t = res.trades.rename(columns=TRADE_LABELS)
    for c in ("進場日", "出場日"):
        t[c] = pd.to_datetime(t[c]).dt.date
    front = [c for c in ("代號", "名稱") if c in t.columns]
    return t[front + [c for c in t.columns if c not in front]]


def to_excel_bytes(res: ScreenResult) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        res.table.to_excel(xw, sheet_name="選股結果", index=False)
        res.matched.to_excel(xw, sheet_name="符合清單", index=False)
        _trades_frame(res).to_excel(xw, sheet_name="回測交易明細", index=False)
        _meta_frame(res).to_excel(xw, sheet_name="參數與彙總", index=False)
        for ws in xw.book.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max(8, width * 1.6), 60)
    return buf.getvalue()


def to_csv_bytes(res: ScreenResult, which: str = "table") -> bytes:
    df = {"table": res.table, "matched": res.matched, "trades": _trades_frame(res)}[which]
    return df.to_csv(index=False).encode("utf-8-sig")


def default_filename(res: ScreenResult, ext: str) -> str:
    return f"選股_{strategies.get(res.strategy).label}_{datetime.now():%Y%m%d_%H%M}.{ext}"


def export(res: ScreenResult, out_dir: str | Path, fmt: str = "xlsx") -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = fmt.lower()
    if fmt not in ("xlsx", "csv"):
        raise ValueError("fmt 只支援 xlsx / csv")
    p = out_dir / default_filename(res, fmt)
    p.write_bytes(to_excel_bytes(res) if fmt == "xlsx" else to_csv_bytes(res))
    return p
