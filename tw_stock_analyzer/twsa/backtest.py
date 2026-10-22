"""回測引擎：勝率、最大回撤（MDD）、報酬、交易明細。

規則（刻意保守，避免回測美化）：
    * 訊號由 False 轉 True 的那天收盤後才知道 → **隔天開盤價**進場
    * 一次只持有一筆，持有中出現的新訊號忽略
    * 出場（先到先出）：
        1. 停損：盤中最低觸及 進場價×(1−停損%) → 以停損價出場；跳空開低則以開盤價出場
        2. 停利：盤中最高觸及 進場價×(1+停利%) → 以停利價出場；跳空開高則以開盤價
           同一天停損停利都觸及時，**假設先停損**（保守）
        3. 跌破月線：收盤 < MA20 → 當日收盤出場（選用）
        4. 持有滿 N 個交易日 → 當日收盤出場
        5. 資料結束仍持有 → 以最後收盤計價，標記「未平倉」
    * 成本：手續費 0.1425% × 折扣（買賣各一次）、證交稅 0.3%（賣出）
    * 權益曲線：有部位時 100% 資金在該檔，逐日以收盤價計值；MDD 由權益曲線計算
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from .indicators import max_drawdown


@dataclass
class BacktestConfig:
    hold_days: int = 20
    stop_loss: float = 8.0          # %，0 = 不停損
    take_profit: float = 0.0        # %，0 = 不停利
    exit_below_ma20: bool = False
    fee_rate: float = 0.001425
    fee_discount: float = 0.6
    tax_rate: float = 0.003

    @property
    def fee(self) -> float:
        return self.fee_rate * self.fee_discount

    @classmethod
    def from_dict(cls, d: dict | None) -> "BacktestConfig":
        cfg = cls()
        for k, v in (d or {}).items():
            if hasattr(cfg, k) and v not in (None, ""):
                cur = getattr(cfg, k)
                if isinstance(cur, bool):
                    v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
                else:
                    v = type(cur)(float(v))
                setattr(cfg, k, v)
        return cfg

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    equity: pd.Series
    stats: dict


TRADE_COLS = ["entry_date", "entry_price", "exit_date", "exit_price", "exit_reason",
              "hold_days", "return_pct", "is_open"]


def run_backtest(feats: pd.DataFrame, signal: pd.Series, cfg: BacktestConfig | None = None) -> BacktestResult:
    cfg = cfg or BacktestConfig()
    if feats is None or feats.empty:
        return BacktestResult(pd.DataFrame(columns=TRADE_COLS), pd.Series(dtype=float), summarize_trades(pd.DataFrame(columns=TRADE_COLS), pd.Series(dtype=float), None))

    sig = signal.reindex(feats.index).fillna(False).astype(bool).to_numpy()
    o = feats["open"].to_numpy(float)
    h = feats["high"].to_numpy(float)
    lo = feats["low"].to_numpy(float)
    c = feats["close"].to_numpy(float)
    ma20 = feats["ma20"].to_numpy(float) if "ma20" in feats else np.full(len(c), np.nan)
    dates = feats.index
    n = len(c)
    fee, tax = cfg.fee, cfg.tax_rate

    equity = np.empty(n)
    cash = 1.0
    shares = 0.0
    trades = []
    entry_idx = -1
    entry_px = 0.0
    pending_entry = False

    for j in range(n):
        if pending_entry and shares == 0.0:
            px = o[j] if np.isfinite(o[j]) and o[j] > 0 else c[j]
            entry_px = px
            shares = cash / (px * (1 + fee))
            cash = 0.0
            entry_idx = j
            pending_entry = False

        if shares > 0.0:
            exit_px, reason = None, None
            sl = entry_px * (1 - cfg.stop_loss / 100) if cfg.stop_loss > 0 else None
            tp = entry_px * (1 + cfg.take_profit / 100) if cfg.take_profit > 0 else None
            if sl is not None and lo[j] <= sl:
                exit_px, reason = (min(o[j], sl) if j > entry_idx else sl), "停損"
            elif tp is not None and h[j] >= tp:
                exit_px, reason = (max(o[j], tp) if j > entry_idx else tp), "停利"
            elif cfg.exit_below_ma20 and np.isfinite(ma20[j]) and c[j] < ma20[j]:
                exit_px, reason = c[j], "跌破月線"
            elif j - entry_idx + 1 >= cfg.hold_days:
                exit_px, reason = c[j], f"持有{cfg.hold_days}日"
            if exit_px is not None:
                cash = shares * exit_px * (1 - fee - tax)
                trades.append(_trade(dates, entry_idx, entry_px, j, exit_px, reason, fee, tax, False))
                shares = 0.0
        equity[j] = cash + shares * c[j]

        # 今天收盤出現新訊號（前一天沒有）→ 明天開盤進場
        if shares == 0.0 and sig[j] and (j == 0 or not sig[j - 1]) and j + 1 < n:
            pending_entry = True

    if shares > 0.0:
        trades.append(_trade(dates, entry_idx, entry_px, n - 1, c[-1], "未平倉", fee, tax, True))

    tdf = pd.DataFrame(trades, columns=TRADE_COLS)
    eq = pd.Series(equity, index=dates, name="equity")
    return BacktestResult(tdf, eq, summarize_trades(tdf, eq, feats["close"]))


def _trade(dates, ei, epx, xi, xpx, reason, fee, tax, is_open):
    ret = (xpx * (1 - fee - tax)) / (epx * (1 + fee)) - 1
    return [dates[ei], round(float(epx), 4), dates[xi], round(float(xpx), 4), reason,
            int(xi - ei + 1), round(ret * 100, 3), is_open]


def summarize_trades(trades: pd.DataFrame, equity: pd.Series, close: pd.Series | None) -> dict:
    closed = trades[~trades["is_open"].astype(bool)] if len(trades) else trades
    rets = closed["return_pct"].astype(float) if len(closed) else pd.Series(dtype=float)
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    total_ret = float(equity.iloc[-1] - 1) * 100 if len(equity) else 0.0
    years = (equity.index[-1] - equity.index[0]).days / 365.25 if len(equity) > 1 else 0
    cagr = ((equity.iloc[-1]) ** (1 / years) - 1) * 100 if years > 0 and equity.iloc[-1] > 0 else 0.0
    gross_win = wins.sum()
    gross_loss = -losses.sum()
    stats = {
        "trades": int(len(closed)),
        "open_trades": int(len(trades) - len(closed)),
        "win_rate": round(len(wins) / len(rets) * 100, 2) if len(rets) else None,
        "avg_return": round(float(rets.mean()), 3) if len(rets) else None,
        "avg_win": round(float(wins.mean()), 3) if len(wins) else None,
        "avg_loss": round(float(losses.mean()), 3) if len(losses) else None,
        "profit_factor": round(float(gross_win / gross_loss), 3) if gross_loss > 0 else None,
        "total_return": round(total_ret, 3),
        "cagr": round(float(cagr), 3),
        "mdd": round(max_drawdown(equity) * 100, 3) if len(equity) else 0.0,
        "avg_hold_days": round(float(closed["hold_days"].mean()), 2) if len(closed) else None,
        "exposure": None,
        "buy_hold_return": None,
        "buy_hold_mdd": None,
    }
    if len(equity) and len(trades):
        in_pos = pd.Series(False, index=equity.index)
        for _, t in trades.iterrows():
            in_pos.loc[t["entry_date"]:t["exit_date"]] = True
        stats["exposure"] = round(in_pos.mean() * 100, 2)
    if close is not None and len(close.dropna()) > 1:
        cl = close.dropna()
        stats["buy_hold_return"] = round(float(cl.iloc[-1] / cl.iloc[0] - 1) * 100, 3)
        stats["buy_hold_mdd"] = round(max_drawdown(cl / cl.iloc[0]) * 100, 3)
    return stats


def portfolio_summary(results: dict[str, BacktestResult]) -> dict:
    """整池股票的彙總：所有交易合併算勝率；等權重組合的權益曲線算 MDD。"""
    valid = {k: r for k, r in results.items() if len(r.equity)}
    if not valid:
        return {"stocks": 0, "trades": 0, "win_rate": None, "avg_return": None,
                "portfolio_return": None, "portfolio_mdd": None, "worst_stock_mdd": None}
    all_trades = pd.concat([r.trades.assign(code=k) for k, r in valid.items()], ignore_index=True)
    closed = all_trades[~all_trades["is_open"].astype(bool)]
    rets = closed["return_pct"].astype(float)
    eq = pd.concat({k: r.equity for k, r in valid.items()}, axis=1, sort=True).ffill()
    eq = eq.fillna(1.0)   # 尚未上市／資料還沒開始的期間視為持有現金
    port = eq.mean(axis=1)
    return {
        "stocks": len(valid),
        "trades": int(len(closed)),
        "win_rate": round(float((rets > 0).mean() * 100), 2) if len(rets) else None,
        "avg_return": round(float(rets.mean()), 3) if len(rets) else None,
        "portfolio_return": round(float(port.iloc[-1] - 1) * 100, 3),
        "portfolio_mdd": round(max_drawdown(port) * 100, 3),
        "worst_stock_mdd": round(min(r.stats["mdd"] for r in valid.values()), 3),
        "equity": port,
    }
