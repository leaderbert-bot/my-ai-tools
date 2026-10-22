import numpy as np
import pandas as pd
import pytest

from twsa import indicators as ind
from twsa.data import schema
from conftest import make_price


def test_sma_and_min_periods():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    out = ind.sma(s, 3)
    assert out.isna().sum() == 2
    assert out.iloc[-1] == pytest.approx(4.0)


def test_rsi_bounds_and_extremes():
    up = pd.Series(np.arange(1, 40, dtype=float))
    assert ind.rsi(up).iloc[-1] == pytest.approx(100.0)
    zig = pd.Series([10, 11, 10, 11, 10, 11] * 6, dtype=float)
    r = ind.rsi(zig).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_streak_resets():
    s = pd.Series([True, True, False, True, True, True, False])
    assert ind.streak(s).tolist() == [1, 2, 0, 1, 2, 3, 0]


def test_publication_dates():
    assert ind.revenue_available_date(pd.Timestamp("2026-08-01")) == pd.Timestamp("2026-09-10")
    assert ind.revenue_available_date(pd.Timestamp("2026-12-01")) == pd.Timestamp("2027-01-10")
    assert ind.financial_available_date(pd.Timestamp("2026-03-31")) == pd.Timestamp("2026-05-15")
    assert ind.financial_available_date(pd.Timestamp("2026-06-30")) == pd.Timestamp("2026-08-14")
    assert ind.financial_available_date(pd.Timestamp("2026-09-30")) == pd.Timestamp("2026-11-14")
    assert ind.financial_available_date(pd.Timestamp("2025-12-31")) == pd.Timestamp("2026-03-31")


def test_moving_averages_columns(uptrend):
    f = ind.build_features(uptrend)
    for n in ind.MA_WINDOWS:
        assert f"ma{n}" in f
    assert f["ma5"].iloc[-1] > f["ma20"].iloc[-1] > f["ma60"].iloc[-1]
    assert f["ma20_slope"].iloc[-1] > 0
    assert f["prior_high"].iloc[-1] == pytest.approx(uptrend["high"].iloc[-21:-1].max())


def test_chip_concentration_exact():
    px = make_price(np.full(30, 100.0), vol=1_000_000)
    inst = pd.DataFrame({"foreign": 40_000.0, "trust": 10_000.0, "dealer": 0.0}, index=px.index)
    inst["total"] = inst.sum(axis=1)
    f = ind.build_features(px, institutional=inst, chip_window=10)
    # 每天淨買 5 萬股 / 每天量 100 萬股 = 5%
    assert f["chip_conc"].iloc[-1] == pytest.approx(5.0)
    assert f["chip_conc"].iloc[:9].isna().all()
    assert f["foreign_buy_streak"].iloc[-1] == 30


def test_chip_concentration_missing_inst_is_nan():
    px = make_price(np.full(30, 100.0))
    f = ind.build_features(px)
    assert f["chip_conc"].isna().all()


def test_revenue_no_lookahead():
    px = make_price(np.full(60, 100.0), start="2026-08-03")
    rev = pd.DataFrame({"revenue": [100.0, 150.0]}, index=pd.to_datetime(["2025-08-01", "2026-08-01"]))
    rev = schema.add_revenue_growth(rev)
    f = ind.build_features(px, revenue=rev)
    assert f.loc["2026-09-09", "rev_yoy"] != f.loc["2026-09-09", "rev_yoy"]  # NaN：還沒公告
    assert f.loc["2026-09-10", "rev_yoy"] == pytest.approx(50.0)
    assert f.loc["2026-10-20", "rev_yoy"] == pytest.approx(50.0)


def test_financials_ttm_and_pe():
    px = make_price(np.full(400, 100.0), start="2025-01-02")
    fin = pd.DataFrame({"eps": [1.0, 1.0, 1.0, 2.0], "gross_margin": 30.0, "operating_margin": 10.0, "net_margin": 8.0},
                       index=pd.to_datetime(["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"]))
    f = ind.build_features(px, financials=fin)
    assert np.isnan(f.loc["2026-03-30", "eps_ttm"])
    assert f.loc["2026-03-31", "eps_ttm"] == pytest.approx(5.0)
    assert f.loc["2026-03-31", "pe"] == pytest.approx(20.0)


def test_holding_shifted_one_day():
    px = make_price(np.full(40, 100.0), start="2026-01-05")
    hold = pd.DataFrame({"big_holder_pct": [50.0, 51.0, 52.0, 53.0, 54.0, 55.0], "holders": 1000.0},
                        index=pd.date_range("2026-01-09", periods=6, freq="W-FRI"))
    f = ind.build_features(px, holding=hold)
    assert np.isnan(f.loc["2026-01-09", "big_holder_pct"])   # 週五當天還看不到
    assert f.loc["2026-01-12", "big_holder_pct"] == pytest.approx(50.0)
    assert f.loc["2026-02-16", "big_holder_chg4w"] == pytest.approx(4.0)


def test_max_drawdown_known_value():
    eq = pd.Series([1.0, 1.2, 0.9, 1.1, 0.6, 1.5])
    assert ind.max_drawdown(eq) == pytest.approx(0.6 / 1.2 - 1)
    assert ind.max_drawdown(pd.Series([1.0, 2.0, 3.0])) == 0.0
    assert ind.max_drawdown(pd.Series(dtype=float)) == 0.0


def test_empty_price_returns_empty():
    assert ind.build_features(schema.empty(schema.PRICE_COLS)).empty
