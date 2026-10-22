"""系統內部統一的資料表格式。所有來源（官方 API、FinMind、台股雷達本機檔、模擬資料）
最後都轉成這幾種 DataFrame，策略與回測只認這個格式。

price        index=date  欄位 open, high, low, close, volume（成交股數）
institutional index=date 欄位 foreign, trust, dealer, total（買賣超股數，正=買超）
holding      index=date  欄位 big_holder_pct（持股 400 張以上大戶比例 %）, holders（股東人數，可缺）
revenue      index=月份第一天  欄位 revenue（仟元）, yoy（%）, mom（%）
financials   index=季底日  欄位 eps, gross_margin, operating_margin, net_margin（%）
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PRICE_COLS = ["open", "high", "low", "close", "volume"]
INST_COLS = ["foreign", "trust", "dealer", "total"]
HOLDING_COLS = ["big_holder_pct", "holders"]
REVENUE_COLS = ["revenue", "yoy", "mom"]
FIN_COLS = ["eps", "gross_margin", "operating_margin", "net_margin"]


def empty(cols: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(columns=cols, dtype="float64")
    df.index = pd.DatetimeIndex([], name="date")
    return df


def normalize(df: pd.DataFrame | None, cols: list[str]) -> pd.DataFrame:
    """補齊欄位、轉成 float、日期排序並去除重複日期（保留最後一筆）。"""
    if df is None or len(df) == 0:
        return empty(cols)
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    out.index.name = "date"
    for c in cols:
        if c not in out.columns:
            out[c] = float("nan")
    out = out[cols].apply(pd.to_numeric, errors="coerce").astype("float64")
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def add_revenue_growth(df: pd.DataFrame) -> pd.DataFrame:
    """依 revenue 欄位重算年增（vs 去年同月）與月增（vs 上月）。

    跟台股雷達同一個原則：不吃官方百分比欄位，一律自己重算，官方改欄名也不會錯。
    去年同月／上月缺資料或 <= 0 時給 NaN，不給一個假的天文數字。
    """
    out = normalize(df, REVENUE_COLS)
    if out.empty:
        return out
    rev = out["revenue"]
    idx = out.index
    prev_year = rev.reindex(idx - pd.DateOffset(years=1)).to_numpy()
    prev_month = rev.reindex(idx - pd.DateOffset(months=1)).to_numpy()
    cur = rev.to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        yoy = np.where(prev_year > 0, (cur / prev_year - 1.0) * 100.0, np.nan)
        mom = np.where(prev_month > 0, (cur / prev_month - 1.0) * 100.0, np.nan)
    out["yoy"] = yoy
    out["mom"] = mom
    return out
