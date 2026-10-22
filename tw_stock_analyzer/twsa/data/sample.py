"""模擬資料產生器（離線展示與單元測試用）。

用固定亂數種子產生「看起來像台股」的資料：有趨勢段、盤整段、回檔，法人買賣超與股價走勢
有正相關，月營收有季節性。**畫面上會明確標示「模擬資料」，不可當作真實行情。**
"""

from __future__ import annotations

import zlib

import numpy as np
import pandas as pd

from . import schema

SAMPLE_NAMES = {
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2308": "台達電", "3008": "大立光",
    "2382": "廣達", "3017": "奇鋐", "2421": "建準", "3324": "雙鴻", "6488": "環球晶",
    "1513": "中興電", "1519": "華城", "3711": "日月光投控", "2344": "華邦電", "8299": "群聯",
}


def _rng(code: str, salt: str = "") -> np.random.Generator:
    return np.random.default_rng(zlib.crc32(f"{code}:{salt}".encode()))


def trading_days(end: str | pd.Timestamp = "2026-10-21", n: int = 750) -> pd.DatetimeIndex:
    return pd.bdate_range(end=pd.Timestamp(end), periods=n, name="date")


def price(code: str, end="2026-10-21", n: int = 750) -> pd.DataFrame:
    rng = _rng(code, "px")
    idx = trading_days(end, n)
    # 分段漂移：上升、盤整、下跌交錯，讓策略有訊號也有失敗
    regimes = rng.choice([0.0016, 0.0, -0.0010, 0.0024], size=n // 60 + 1, p=[0.35, 0.3, 0.2, 0.15])
    drift = np.repeat(regimes, 60)[:n]
    ret = drift + rng.normal(0, 0.018, n)
    ret = np.clip(ret, -0.095, 0.095)  # 台股 ±10% 漲跌停
    base = 20 + (zlib.crc32(code.encode()) % 600)
    close = base * np.exp(np.cumsum(ret))
    prev = np.concatenate([[close[0]], close[:-1]])
    open_ = prev * (1 + rng.normal(0, 0.006, n))
    hi = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.008, n)))
    lo = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.008, n)))
    vol = (rng.lognormal(15, 0.5, n) * (1 + 8 * np.clip(ret, 0, None))).round(-3)
    df = pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close, "volume": vol}, index=idx)
    return schema.normalize(df.round(2), schema.PRICE_COLS)


def institutional(code: str, px: pd.DataFrame | None = None) -> pd.DataFrame:
    px = price(code) if px is None else px
    rng = _rng(code, "inst")
    ret = px["close"].pct_change().fillna(0).to_numpy()
    vol = px["volume"].to_numpy()
    n = len(px)
    f = (ret * 4 + rng.normal(0, 0.03, n)) * vol
    t = (ret * 2 + rng.normal(0, 0.01, n)) * vol * 0.3
    d = rng.normal(0, 0.01, n) * vol * 0.3
    df = pd.DataFrame({"foreign": f.round(-3), "trust": t.round(-3), "dealer": d.round(-3)}, index=px.index)
    df["total"] = df.sum(axis=1)
    return schema.normalize(df, schema.INST_COLS)


def holding(code: str, px: pd.DataFrame | None = None) -> pd.DataFrame:
    px = price(code) if px is None else px
    rng = _rng(code, "hold")
    weekly = px["close"].resample("W-FRI").last().dropna()
    trend = weekly.pct_change(4).fillna(0).to_numpy()
    pct = 55 + np.cumsum(trend * 3 + rng.normal(0, 0.25, len(weekly)))
    holders = 30000 * np.exp(np.cumsum(-trend * 0.5 + rng.normal(0, 0.01, len(weekly))))
    df = pd.DataFrame({"big_holder_pct": np.clip(pct, 5, 95), "holders": holders.round()}, index=weekly.index)
    return schema.normalize(df, schema.HOLDING_COLS)


def revenue(code: str, end="2026-09-01", months: int = 60) -> pd.DataFrame:
    rng = _rng(code, "rev")
    idx = pd.date_range(end=pd.Timestamp(end), periods=months, freq="MS", name="date")
    growth = rng.normal(0.008, 0.01)
    season = 1 + 0.08 * np.sin(np.arange(months) / 12 * 2 * np.pi)
    rev = (1e6 + zlib.crc32(code.encode()) % 5_000_000) * np.exp(growth * np.arange(months)) * season
    rev *= 1 + rng.normal(0, 0.05, months)
    df = pd.DataFrame({"revenue": rev.round()}, index=idx)
    return schema.add_revenue_growth(df)


def financials(code: str, quarters: int = 12) -> pd.DataFrame:
    rng = _rng(code, "fin")
    idx = pd.date_range(end="2026-06-30", periods=quarters, freq="QE", name="date")
    gm = 20 + rng.normal(0, 2, quarters).cumsum() * 0.3 + (zlib.crc32(code.encode()) % 30)
    om = gm * 0.55 + rng.normal(0, 1, quarters)
    nm = om * 0.8
    eps = np.round(nm / 10 * (1 + rng.normal(0, 0.1, quarters)), 2)
    df = pd.DataFrame({"eps": eps, "gross_margin": gm, "operating_margin": om, "net_margin": nm}, index=idx)
    return schema.normalize(df.round(2), schema.FIN_COLS)
