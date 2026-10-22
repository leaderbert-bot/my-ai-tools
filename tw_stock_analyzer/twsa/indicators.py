"""技術、籌碼、基本面指標。

最重要的一個原則：**回測不能偷看未來**。月營收要到次月 10 日才公告、季報要到法定期限才公布，
所以 ``build_features`` 會把基本面資料「對齊到公告日」才併進每日資料 —— 例如 8 月營收
在 9/10 之前的每一天都看不到。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import schema

MA_WINDOWS = (5, 10, 20, 60, 120)


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    diff = close.diff()
    up = diff.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-diff.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(dn != 0, 100.0).where(up.notna())


def streak(positive: pd.Series) -> pd.Series:
    """連續為 True 的天數（遇 False 歸零）。"""
    p = positive.fillna(False).astype(bool)
    grp = (~p).cumsum()
    return p.groupby(grp).cumsum().astype(int)


def revenue_available_date(month_start: pd.Timestamp) -> pd.Timestamp:
    """月營收法定公告期限：次月 10 日。"""
    nxt = month_start + pd.DateOffset(months=1)
    return pd.Timestamp(nxt.year, nxt.month, 10)


def financial_available_date(quarter_end: pd.Timestamp) -> pd.Timestamp:
    """季報法定公告期限：Q1→5/15、Q2→8/14、Q3→11/14、Q4→隔年 3/31。"""
    y, m = quarter_end.year, quarter_end.month
    return {3: pd.Timestamp(y, 5, 15), 6: pd.Timestamp(y, 8, 14),
            9: pd.Timestamp(y, 11, 14)}.get(m, pd.Timestamp(y + 1, 3, 31))


def _asof(daily_index: pd.DatetimeIndex, s: pd.Series) -> pd.Series:
    """把低頻序列（已經以「可取得日」為 index）攤到每個交易日，用最近一筆已知值。"""
    s = s.dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")]
    if s.empty:
        return pd.Series(np.nan, index=daily_index)
    return s.reindex(daily_index.union(s.index)).ffill().reindex(daily_index)


def build_features(price: pd.DataFrame,
                   institutional: pd.DataFrame | None = None,
                   holding: pd.DataFrame | None = None,
                   revenue: pd.DataFrame | None = None,
                   financials: pd.DataFrame | None = None,
                   chip_window: int = 10,
                   breakout_window: int = 20) -> pd.DataFrame:
    px = schema.normalize(price, schema.PRICE_COLS)
    f = px.copy()
    if f.empty:
        return f
    c = f["close"]
    for n in MA_WINDOWS:
        f[f"ma{n}"] = sma(c, n)
    f["ma20_slope"] = f["ma20"] / f["ma20"].shift(5) - 1           # 5 日前比，>0 代表月線上揚
    f["roc20"] = c / c.shift(20) - 1
    f["roc60"] = c / c.shift(60) - 1
    f["rsi14"] = rsi(c, 14)
    f["prior_high"] = f["high"].shift(1).rolling(breakout_window, min_periods=breakout_window).max()
    f["vol_ma20"] = sma(f["volume"], 20)
    f["vol_ratio"] = f["volume"] / f["vol_ma20"].shift(1)
    f["high_250"] = f["high"].rolling(250, min_periods=60).max()

    # ── 籌碼：三大法人 ──
    inst = schema.normalize(institutional, schema.INST_COLS).reindex(f.index)
    f["inst_total"] = inst["total"]
    f["foreign"] = inst["foreign"]
    f["trust"] = inst["trust"]
    has_inst = inst["total"].notna()
    net = inst["total"].fillna(0).rolling(chip_window, min_periods=chip_window).sum()
    vol_sum = f["volume"].rolling(chip_window, min_periods=chip_window).sum()
    conc = net / vol_sum.replace(0, np.nan) * 100.0
    enough = has_inst.rolling(chip_window, min_periods=chip_window).sum() >= chip_window * 0.8
    f["chip_conc"] = conc.where(enough)                              # N 日法人淨買超 / N 日成交量（%）
    f["foreign_buy_streak"] = streak(inst["foreign"] > 0).where(has_inst)
    f["trust_buy_streak"] = streak(inst["trust"] > 0).where(has_inst)

    # ── 籌碼：集保大戶（週資料，週五統計、下週一前公布 → 往後挪 1 個交易日） ──
    hold = schema.normalize(holding, schema.HOLDING_COLS)
    if not hold.empty:
        big = hold["big_holder_pct"].copy()
        big.index = big.index + pd.Timedelta(days=1)
        f["big_holder_pct"] = _asof(f.index, big)
        chg = hold["big_holder_pct"].diff(4)
        chg.index = chg.index + pd.Timedelta(days=1)
        f["big_holder_chg4w"] = _asof(f.index, chg)
    else:
        f["big_holder_pct"] = np.nan
        f["big_holder_chg4w"] = np.nan

    # ── 基本面：月營收（對齊到公告日） ──
    rev = schema.normalize(revenue, schema.REVENUE_COLS)
    if not rev.empty:
        avail = pd.DatetimeIndex([revenue_available_date(d) for d in rev.index])
        yoy = pd.Series(rev["yoy"].to_numpy(), index=avail)
        f["rev_yoy"] = _asof(f.index, yoy)
        yoy3 = pd.Series(rev["yoy"].rolling(3, min_periods=3).mean().to_numpy(), index=avail)
        f["rev_yoy_3m"] = _asof(f.index, yoy3)
        pos = pd.Series(streak(rev["yoy"] > 0).where(rev["yoy"].notna()).to_numpy(), index=avail)
        f["rev_yoy_streak"] = _asof(f.index, pos)
    else:
        f["rev_yoy"] = f["rev_yoy_3m"] = f["rev_yoy_streak"] = np.nan

    # ── 基本面：季報（對齊到法定公告期限） ──
    fin = schema.normalize(financials, schema.FIN_COLS)
    if not fin.empty:
        avail = pd.DatetimeIndex([financial_available_date(d) for d in fin.index])
        for col in ("eps", "gross_margin", "operating_margin"):
            f[col] = _asof(f.index, pd.Series(fin[col].to_numpy(), index=avail))
        ttm = fin["eps"].rolling(4, min_periods=4).sum()
        f["eps_ttm"] = _asof(f.index, pd.Series(ttm.to_numpy(), index=avail))
    else:
        f["eps"] = f["gross_margin"] = f["operating_margin"] = f["eps_ttm"] = np.nan
    f["pe"] = (c / f["eps_ttm"]).where(f["eps_ttm"] > 0)
    return f


def drawdown(equity: pd.Series) -> pd.Series:
    """每個時點相對前高的回落比例（負值）。"""
    peak = equity.cummax()
    return equity / peak - 1.0


def max_drawdown(equity: pd.Series) -> float:
    if equity is None or len(equity) == 0:
        return 0.0
    return float(drawdown(equity).min())
