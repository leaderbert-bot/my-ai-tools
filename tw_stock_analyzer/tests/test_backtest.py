import numpy as np
import pandas as pd
import pytest

from twsa.backtest import BacktestConfig, portfolio_summary, run_backtest
from twsa.indicators import build_features

NOCOST = dict(fee_rate=0.0, tax_rate=0.0)


def frame(opens, highs, lows, closes):
    idx = pd.bdate_range("2026-03-02", periods=len(closes), name="date")
    f = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes,
                      "volume": 1000.0}, index=idx, dtype=float)
    f["ma20"] = np.nan
    return f


def sig_at(f, *pos):
    s = pd.Series(False, index=f.index)
    for p in pos:
        s.iloc[p] = True
    return s


def test_entry_next_open_and_hold_exit():
    c = [10, 10, 10, 11, 12, 13, 14, 15]
    f = frame([10, 10, 10.5, 11, 12, 13, 14, 15], [x + 0.5 for x in c], [x - 0.5 for x in c], c)
    r = run_backtest(f, sig_at(f, 1), BacktestConfig(hold_days=3, stop_loss=0, **NOCOST))
    t = r.trades.iloc[0]
    assert t["entry_date"] == f.index[2] and t["entry_price"] == 10.5   # 隔天開盤，不是當天收盤
    assert t["exit_date"] == f.index[4] and t["exit_price"] == 12        # 持有 3 個交易日收盤出
    assert t["return_pct"] == pytest.approx((12 / 10.5 - 1) * 100, abs=1e-3)
    assert r.stats["trades"] == 1 and r.stats["win_rate"] == 100.0


def test_stop_loss_with_gap_down_uses_open():
    f = frame([10, 10, 10, 8.0, 8], [10.2, 10.2, 10.2, 8.2, 8.2], [9.8, 9.8, 9.9, 7.8, 7.8], [10, 10, 10, 8, 8])
    r = run_backtest(f, sig_at(f, 1), BacktestConfig(hold_days=10, stop_loss=5, **NOCOST))
    t = r.trades.iloc[0]
    assert t["exit_reason"] == "停損"
    assert t["exit_price"] == 8.0            # 跳空開低，以開盤價（比停損價 9.5 更差）出場
    assert r.stats["win_rate"] == 0.0


def test_stop_loss_intraday_uses_stop_price():
    f = frame([10, 10, 10, 9.9, 9.9], [10.2, 10.2, 10.2, 10, 10], [9.8, 9.8, 9.9, 9.0, 9.0], [10, 10, 10, 9.9, 9.9])
    r = run_backtest(f, sig_at(f, 1), BacktestConfig(hold_days=10, stop_loss=5, **NOCOST))
    assert r.trades.iloc[0]["exit_price"] == pytest.approx(9.5)


def test_take_profit_and_stop_same_day_assumes_stop():
    f = frame([10, 10, 10, 10], [10, 10, 10, 12], [10, 10, 10, 9], [10, 10, 10, 11])
    r = run_backtest(f, sig_at(f, 1), BacktestConfig(hold_days=10, stop_loss=5, take_profit=10, **NOCOST))
    assert r.trades.iloc[0]["exit_reason"] == "停損"
    f2 = frame([10, 10, 10, 10], [10, 10, 10, 12], [10, 10, 10, 9.9], [10, 10, 10, 11])
    r2 = run_backtest(f2, sig_at(f2, 1), BacktestConfig(hold_days=10, stop_loss=5, take_profit=10, **NOCOST))
    assert r2.trades.iloc[0]["exit_reason"] == "停利"
    assert r2.trades.iloc[0]["exit_price"] == pytest.approx(11.0)


def test_exit_below_ma20():
    f = frame([10] * 6, [11] * 6, [9.6] * 6, [10, 10, 10, 10, 9.7, 9.7])
    f["ma20"] = 9.8
    r = run_backtest(f, sig_at(f, 1), BacktestConfig(hold_days=20, stop_loss=0, exit_below_ma20=True, **NOCOST))
    t = r.trades.iloc[0]
    assert t["exit_reason"] == "跌破月線" and t["exit_date"] == f.index[4]


def test_costs_reduce_return():
    f = frame([10] * 6, [10] * 6, [10] * 6, [10] * 6)
    cfg = BacktestConfig(hold_days=2, stop_loss=0, fee_rate=0.001425, fee_discount=1.0, tax_rate=0.003)
    r = run_backtest(f, sig_at(f, 0), cfg)
    expected = ((1 - 0.001425 - 0.003) / (1 + 0.001425) - 1) * 100
    assert r.trades.iloc[0]["return_pct"] == pytest.approx(expected, abs=1e-3)
    assert r.equity.iloc[-1] == pytest.approx(1 + expected / 100)


def test_open_trade_flagged_and_excluded_from_winrate():
    f = frame([10, 10, 11, 12], [10, 10, 11, 12], [10, 10, 11, 12], [10, 10, 11, 12])
    r = run_backtest(f, sig_at(f, 1), BacktestConfig(hold_days=50, stop_loss=0, **NOCOST))
    assert bool(r.trades.iloc[0]["is_open"]) and r.trades.iloc[0]["exit_reason"] == "未平倉"
    assert r.stats["trades"] == 0 and r.stats["open_trades"] == 1 and r.stats["win_rate"] is None


def test_only_rising_edge_and_no_overlap():
    f = frame([10] * 12, [10] * 12, [10] * 12, [10] * 12)
    s = pd.Series(True, index=f.index)   # 一路 True 只算一次進場
    r = run_backtest(f, s, BacktestConfig(hold_days=3, stop_loss=0, **NOCOST))
    assert len(r.trades) == 1


def test_win_rate_mdd_and_equity_curve():
    c = [10, 10, 12, 12, 12, 9, 9, 9, 9]
    f = frame(c, c, c, c)
    s = sig_at(f, 0, 4)
    r = run_backtest(f, s, BacktestConfig(hold_days=2, stop_loss=0, **NOCOST))
    # 交易1：開 10 → 收 12 (+20%)；交易2：第 5 根開 9 進場… 依序驗證
    rets = r.trades["return_pct"].tolist()
    assert rets[0] == pytest.approx(20.0)
    assert r.stats["trades"] == len(r.trades[~r.trades["is_open"]])
    assert r.stats["mdd"] <= 0
    assert r.equity.iloc[0] == pytest.approx(1.0)
    assert r.stats["buy_hold_return"] == pytest.approx(-10.0)


def test_mdd_matches_equity_drawdown():
    rng = np.random.default_rng(0)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, 300)))
    idx = pd.bdate_range("2025-01-01", periods=300)
    px = pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1e6}, index=idx)
    f = build_features(px)
    s = f["close"] > f["ma20"]
    r = run_backtest(f, s, BacktestConfig(hold_days=10))
    eq = r.equity
    assert r.stats["mdd"] == pytest.approx((eq / eq.cummax() - 1).min() * 100, abs=1e-3)


def test_portfolio_summary_pools_trades():
    f = frame([10, 10, 11, 12, 12], [10, 10, 11, 12, 12], [10, 10, 11, 12, 12], [10, 10, 11, 12, 12])
    g = frame([10, 10, 9, 8, 8], [10, 10, 9, 8, 8], [10, 10, 9, 8, 8], [10, 10, 9, 8, 8])
    cfg = BacktestConfig(hold_days=2, stop_loss=0, **NOCOST)
    res = {"A": run_backtest(f, sig_at(f, 0), cfg), "B": run_backtest(g, sig_at(g, 0), cfg)}
    s = portfolio_summary(res)
    assert s["stocks"] == 2 and s["trades"] == 2 and s["win_rate"] == 50.0
    assert s["portfolio_mdd"] <= 0
    assert portfolio_summary({})["stocks"] == 0


def test_config_from_dict():
    cfg = BacktestConfig.from_dict({"hold_days": "15", "stop_loss": "6.5", "exit_below_ma20": "true", "x": 1})
    assert cfg.hold_days == 15 and cfg.stop_loss == 6.5 and cfg.exit_below_ma20 is True


def test_empty_input():
    r = run_backtest(pd.DataFrame(), pd.Series(dtype=bool))
    assert r.trades.empty and r.stats["trades"] == 0
