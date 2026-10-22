"""策略篩選引擎。

每個策略都是「指標表 → 每日 True/False 訊號」的純函式，參數可在畫面上調整。
新增策略只要寫一個函式並用 ``@register`` 登記，GUI、網頁、回測、匯出會自動帶到。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd


@dataclass
class Param:
    key: str
    label: str
    default: float
    kind: str = "float"   # float / int / bool

    def cast(self, v):
        if v is None or v == "":
            return self.default
        if self.kind == "bool":
            return v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
        if self.kind == "int":
            return int(float(v))
        return float(v)


@dataclass
class Strategy:
    key: str
    label: str
    category: str
    description: str
    fn: Callable[..., pd.Series]
    params: list[Param] = field(default_factory=list)
    show_cols: list[str] = field(default_factory=list)

    def defaults(self) -> dict:
        return {p.key: p.default for p in self.params}

    def resolve(self, overrides: dict | None = None) -> dict:
        out = self.defaults()
        for p in self.params:
            if overrides and p.key in overrides:
                out[p.key] = p.cast(overrides[p.key])
        return out

    def signal(self, feats: pd.DataFrame, **overrides) -> pd.Series:
        if feats is None or feats.empty:
            return pd.Series(dtype=bool)
        sig = self.fn(feats, **self.resolve(overrides))
        return sig.fillna(False).astype(bool)

    def to_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "category": self.category,
                "description": self.description,
                "params": [p.__dict__ for p in self.params]}


REGISTRY: dict[str, Strategy] = {}


def register(key, label, category, description, params=(), show_cols=()):
    def deco(fn):
        REGISTRY[key] = Strategy(key, label, category, description, fn, list(params), list(show_cols))
        return fn
    return deco


def get(key: str) -> Strategy:
    if key not in REGISTRY:
        raise KeyError(f"未知策略：{key}（可用：{', '.join(REGISTRY)}）")
    return REGISTRY[key]


def _col(f: pd.DataFrame, name: str) -> pd.Series:
    return f[name] if name in f.columns else pd.Series(float("nan"), index=f.index)


# ───────────────────────────── 動能 ─────────────────────────────

def ma_bull_condition(f: pd.DataFrame, require_ma120: bool = False) -> pd.Series:
    cond = (f["close"] > f["ma5"]) & (f["ma5"] > f["ma10"]) & (f["ma10"] > f["ma20"]) & \
           (f["ma20"] > f["ma60"]) & (f["ma20_slope"] > 0)
    if require_ma120:
        cond &= f["ma60"] > f["ma120"]
    return cond


@register(
    "ma_bull", "均線多頭排列", "動能",
    "收盤 > MA5 > MA10 > MA20 > MA60，且月線（MA20）比 5 日前高。可加選 MA60 > MA120 長線也多頭。",
    params=[Param("require_ma120", "也要求 MA60 > MA120", False, "bool")],
    show_cols=["close", "ma5", "ma20", "ma60", "ma20_slope"],
)
def ma_bull(f, require_ma120=False):
    return ma_bull_condition(f, require_ma120)


@register(
    "momentum_breakout", "動能突破", "動能",
    "收盤突破前 N 日最高價（N 預設 20，見指標設定），當日量 ≥ 均量 × 倍數，20 日漲幅 > 0，且站上季線。",
    params=[Param("vol_mult", "成交量 ≥ 20 日均量 × 倍數", 1.5),
            Param("min_roc20", "20 日漲幅下限（%）", 0.0)],
    show_cols=["close", "prior_high", "vol_ratio", "roc20"],
)
def momentum_breakout(f, vol_mult=1.5, min_roc20=0.0):
    return (f["close"] > f["prior_high"]) & (f["vol_ratio"] >= vol_mult) & \
           (f["roc20"] * 100 > min_roc20) & (f["close"] > f["ma60"])


# ───────────────────────────── 籌碼 ─────────────────────────────

@register(
    "chip_concentration", "籌碼集中度", "籌碼",
    "近 N 日三大法人合計淨買超占同期成交量 ≥ 門檻（%）。有集保股權分散資料時，"
    "可再要求 400 張以上大戶持股比例 4 週內增加。",
    params=[Param("min_conc", "法人淨買超 / 成交量 ≥（%）", 5.0),
            Param("min_foreign_streak", "外資連買天數 ≥", 0, "int"),
            Param("need_big_holder_up", "大戶持股比例需 4 週增加", False, "bool")],
    show_cols=["close", "chip_conc", "foreign_buy_streak", "big_holder_pct", "big_holder_chg4w"],
)
def chip_concentration(f, min_conc=5.0, min_foreign_streak=0, need_big_holder_up=False):
    cond = _col(f, "chip_conc") >= min_conc
    if min_foreign_streak > 0:
        cond &= _col(f, "foreign_buy_streak") >= min_foreign_streak
    if need_big_holder_up:
        cond &= _col(f, "big_holder_chg4w") > 0
    return cond


# ───────────────────────────── 基本面 ─────────────────────────────

@register(
    "revenue_growth", "營收成長", "基本面",
    "最新已公告月營收年增 ≥ 門檻，且近 3 個月平均年增 ≥ 門檻（資料對齊公告日，回測不偷看）。",
    params=[Param("min_yoy", "最新月營收年增 ≥（%）", 20.0),
            Param("min_yoy_3m", "近 3 月平均年增 ≥（%）", 10.0)],
    show_cols=["close", "rev_yoy", "rev_yoy_3m", "rev_yoy_streak"],
)
def revenue_growth(f, min_yoy=20.0, min_yoy_3m=10.0):
    return (_col(f, "rev_yoy") >= min_yoy) & (_col(f, "rev_yoy_3m") >= min_yoy_3m)


# ───────────────────────────── 綜合 ─────────────────────────────

@register(
    "combo", "綜合：多頭 + 籌碼 + 營收", "綜合",
    "均線多頭排列，且法人淨買超占量 ≥ 門檻，且最新月營收年增 > 門檻。三個面向同時成立才算。",
    params=[Param("min_conc", "法人淨買超 / 成交量 ≥（%）", 3.0),
            Param("min_yoy", "最新月營收年增 >（%）", 0.0)],
    show_cols=["close", "ma20", "chip_conc", "rev_yoy"],
)
def combo(f, min_conc=3.0, min_yoy=0.0):
    return ma_bull_condition(f) & (_col(f, "chip_conc") >= min_conc) & (_col(f, "rev_yoy") > min_yoy)


@register(
    "breakout_with_chips", "突破 + 法人進場", "綜合",
    "動能突破當天，近 N 日法人淨買超占量 ≥ 門檻。過濾掉沒有籌碼支撐的假突破。",
    params=[Param("vol_mult", "成交量 ≥ 均量 × 倍數", 1.5),
            Param("min_conc", "法人淨買超 / 成交量 ≥（%）", 2.0)],
    show_cols=["close", "prior_high", "vol_ratio", "chip_conc"],
)
def breakout_with_chips(f, vol_mult=1.5, min_conc=2.0):
    return momentum_breakout(f, vol_mult=vol_mult) & (_col(f, "chip_conc") >= min_conc)


COLUMN_LABELS = {
    "code": "代號", "name": "名稱", "date": "日期", "close": "收盤", "ma5": "MA5", "ma10": "MA10",
    "ma20": "MA20", "ma60": "MA60", "ma120": "MA120", "ma20_slope": "月線斜率",
    "prior_high": "前高", "vol_ratio": "量比", "roc20": "20日漲幅", "roc60": "60日漲幅",
    "rsi14": "RSI14", "chip_conc": "法人淨買超占量%", "foreign_buy_streak": "外資連買",
    "trust_buy_streak": "投信連買", "big_holder_pct": "大戶持股%", "big_holder_chg4w": "大戶4週變化",
    "rev_yoy": "營收年增%", "rev_yoy_3m": "近3月年增%", "rev_yoy_streak": "連續年增月",
    "eps_ttm": "近四季EPS", "pe": "本益比", "gross_margin": "毛利率%",
}
