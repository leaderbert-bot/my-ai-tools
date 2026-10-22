import numpy as np
import pandas as pd
import pytest

from twsa import strategies
from twsa.indicators import build_features
from conftest import make_price


def test_registry_has_required_strategies():
    for k in ("ma_bull", "momentum_breakout", "chip_concentration", "revenue_growth", "combo"):
        assert k in strategies.REGISTRY
    with pytest.raises(KeyError):
        strategies.get("nope")


def test_ma_bull_up_vs_down(uptrend, downtrend):
    s = strategies.get("ma_bull")
    assert s.signal(build_features(uptrend)).iloc[-1]
    assert not s.signal(build_features(downtrend)).any()


def test_ma_bull_require_ma120(uptrend):
    s = strategies.get("ma_bull")
    sig = s.signal(build_features(uptrend), require_ma120=True)
    # MA120 要 120 根才有值，之前不可能成立
    assert not sig.iloc[:119].any()
    assert sig.iloc[-1]


def test_momentum_breakout_on_volume_spike():
    closes = np.concatenate([np.linspace(90, 100, 80), np.full(30, 100.0), [110.0]])
    px = make_price(closes, vol=1_000_000)
    px.iloc[-1, px.columns.get_loc("volume")] = 3_000_000
    f = build_features(px)
    s = strategies.get("momentum_breakout")
    assert s.signal(f).iloc[-1]
    assert not s.signal(f, vol_mult=5).iloc[-1]       # 量不夠
    px.iloc[-1, px.columns.get_loc("volume")] = 1_000_000
    assert not s.signal(build_features(px)).iloc[-1]  # 沒爆量不算


def _with_inst(px, net_per_day):
    inst = pd.DataFrame({"foreign": float(net_per_day), "trust": 0.0, "dealer": 0.0}, index=px.index)
    inst["total"] = inst.sum(axis=1)
    return inst


def test_chip_concentration_threshold(uptrend):
    s = strategies.get("chip_concentration")
    f_hi = build_features(uptrend, institutional=_with_inst(uptrend, 80_000))   # 8%
    f_lo = build_features(uptrend, institutional=_with_inst(uptrend, 20_000))   # 2%
    assert s.signal(f_hi).iloc[-1]
    assert not s.signal(f_lo).iloc[-1]
    assert s.signal(f_lo, min_conc=1.5).iloc[-1]
    assert not s.signal(f_hi, min_foreign_streak=500).iloc[-1]
    # 要求大戶增加但沒有集保資料 → 不成立
    assert not s.signal(f_hi, need_big_holder_up=True).iloc[-1]


def test_revenue_growth_and_combo(uptrend):
    months = pd.date_range("2024-01-01", "2026-06-01", freq="MS")
    rev = pd.DataFrame({"revenue": np.linspace(100, 200, len(months))}, index=months)
    from twsa.data.schema import add_revenue_growth
    rev = add_revenue_growth(rev)
    px = make_price(np.linspace(50, 100, 200), start="2026-01-05")
    f = build_features(px, institutional=_with_inst(px, 50_000), revenue=rev)
    assert strategies.get("revenue_growth").signal(f, min_yoy=10, min_yoy_3m=10).iloc[-1]
    assert not strategies.get("revenue_growth").signal(f, min_yoy=90).iloc[-1]
    assert strategies.get("combo").signal(f).iloc[-1]


def test_param_casting():
    s = strategies.get("chip_concentration")
    r = s.resolve({"min_conc": "7.5", "min_foreign_streak": "3.0", "need_big_holder_up": "true", "junk": 1})
    assert r == {"min_conc": 7.5, "min_foreign_streak": 3, "need_big_holder_up": True}
    assert s.resolve({"min_conc": ""})["min_conc"] == 5.0


def test_signal_on_empty_frame():
    assert strategies.get("ma_bull").signal(pd.DataFrame()).empty
