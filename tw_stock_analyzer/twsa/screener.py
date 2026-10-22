"""選股器：對一整池股票跑策略，列出「今天符合」的股票並附上每檔的歷史回測績效。"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import strategies
from .backtest import BacktestConfig, portfolio_summary, run_backtest
from .data.hub import DataHub
from .indicators import build_features

# 每個策略需要哪些資料；只抓需要的，全市場掃描時省很多請求
NEEDS = {
    "ma_bull": ("price",),
    "momentum_breakout": ("price",),
    "chip_concentration": ("price", "institutional", "holding"),
    "revenue_growth": ("price", "revenue"),
    "combo": ("price", "institutional", "revenue"),
    "breakout_with_chips": ("price", "institutional"),
}


@dataclass
class ScreenResult:
    strategy: str
    table: pd.DataFrame                 # 每檔一列（含回測績效）
    trades: pd.DataFrame                # 所有交易明細
    summary: dict
    params: dict
    backtest: dict
    errors: list = field(default_factory=list)

    @property
    def matched(self) -> pd.DataFrame:
        return self.table[self.table["符合"]] if len(self.table) else self.table


def analyze_stock(hub: DataHub, code: str, strategy_key: str, params: dict | None = None,
                  bt_cfg: BacktestConfig | None = None, kinds=None, years: float = 3.0):
    strat = strategies.get(strategy_key)
    kinds = kinds or NEEDS.get(strategy_key, ("price", "institutional", "holding", "revenue", "financials"))
    b = hub.bundle(code, kinds=kinds, years=years)
    feats = build_features(b.price, b.institutional, b.holding, b.revenue, b.financials)
    sig = strat.signal(feats, **(params or {}))
    res = run_backtest(feats, sig, bt_cfg)
    return b, feats, sig, res


def screen(hub: DataHub, codes: list[str], strategy_key: str, params: dict | None = None,
           bt_cfg: BacktestConfig | None = None, lookback_days: int = 0, progress=None) -> ScreenResult:
    """lookback_days=0 只看最新一根；=3 代表最近 3 根內出現過訊號都算符合。"""
    strat = strategies.get(strategy_key)
    resolved = strat.resolve(params)
    bt_cfg = bt_cfg or BacktestConfig()
    rows, results, errors = [], {}, []
    for i, code in enumerate(codes):
        if progress:
            progress(i, len(codes), code)
        try:
            b, feats, sig, res = analyze_stock(hub, code, strategy_key, resolved, bt_cfg)
        except Exception as e:  # 單檔失敗不影響整批
            errors.append(f"{code}: {type(e).__name__}: {e}")
            continue
        if feats.empty:
            errors.append(f"{code}: 無行情資料（{b.sources.get('price')}）")
            continue
        results[code] = res
        last = feats.iloc[-1]
        recent = sig.iloc[-(lookback_days + 1):] if len(sig) else sig
        hit = bool(recent.any())
        days_ago = int(len(recent) - 1 - np.flatnonzero(recent.to_numpy())[-1]) if hit else None
        row = {
            "代號": code, "名稱": b.name, "日期": feats.index[-1].date().isoformat(),
            "符合": hit, "幾根前": days_ago,
            "收盤": round(float(last["close"]), 2),
            "20日漲幅%": _pct(last.get("roc20")),
        }
        for col in strat.show_cols:
            if col in ("close", "roc20"):
                continue
            label = strategies.COLUMN_LABELS.get(col, col)
            v = last.get(col)
            if col in ("ma20_slope",):
                row[label] = _pct(v)
            else:
                row[label] = None if v is None or pd.isna(v) else round(float(v), 2)
        s = res.stats
        row.update({
            "回測交易次數": s["trades"], "回測勝率%": s["win_rate"], "平均報酬%": s["avg_return"],
            "策略總報酬%": s["total_return"], "策略MDD%": s["mdd"],
            "買進持有報酬%": s["buy_hold_return"], "買進持有MDD%": s["buy_hold_mdd"],
            "資料來源": b.sources.get("price"),
        })
        rows.append(row)
    if progress:
        progress(len(codes), len(codes), "")

    table = pd.DataFrame(rows)
    if len(table):
        table = table.sort_values(["符合", "回測勝率%"], ascending=[False, False], na_position="last")
        table = table.reset_index(drop=True)
    trades = pd.concat([r.trades.assign(代號=c, 名稱=hub.name(c)) for c, r in results.items() if len(r.trades)],
                       ignore_index=True) if results else pd.DataFrame()
    summary = portfolio_summary(results)
    summary.pop("equity", None)
    summary["matched"] = int(table["符合"].sum()) if len(table) else 0
    summary["scanned"] = len(codes)
    return ScreenResult(strategy_key, table, trades, summary, resolved, bt_cfg.to_dict(), errors)


def _pct(v):
    return None if v is None or pd.isna(v) else round(float(v) * 100, 2)

