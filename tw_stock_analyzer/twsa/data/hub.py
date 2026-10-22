"""DataHub：統一的資料入口，依優先序嘗試各來源。

    模擬模式：一律用 sample（離線展示）
    一般模式：台股雷達本機資料 → 今日快取 → FinMind → 證交所/櫃買官方 → 過期快取

每一種資料最後從哪裡來，記在 ``StockBundle.sources``，畫面與報表都會顯示，
不會在你不知情的情況下拿舊資料或模擬資料充數。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from ..config import Settings
from . import fetchers, sample, schema
from .cache import CsvCache
from .radar_adapter import RadarSource

KINDS = {
    "price": schema.PRICE_COLS,
    "institutional": schema.INST_COLS,
    "holding": schema.HOLDING_COLS,
    "revenue": schema.REVENUE_COLS,
    "financials": schema.FIN_COLS,
}


@dataclass
class StockBundle:
    code: str
    name: str
    price: pd.DataFrame
    institutional: pd.DataFrame
    holding: pd.DataFrame
    revenue: pd.DataFrame
    financials: pd.DataFrame
    sources: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)


class DataHub:
    def __init__(self, settings: Settings, session=None, today: date | None = None):
        self.settings = settings
        self.today = today or date.today()
        self.cache = CsvCache(settings.cache_dir)
        rd = settings.radar_data_dir
        self.radar = RadarSource(rd, settings.extra.get("radar_columns")) if rd and rd.is_dir() else None
        self._session = session
        self._finmind = None
        self._official = None
        self._names: dict[str, str] | None = None

    # ---------- 網路 client（延遲建立，離線模式完全不 import requests） ----------
    @property
    def finmind(self) -> fetchers.FinMindClient:
        if self._finmind is None:
            self._finmind = fetchers.FinMindClient(self.settings.finmind_token, self._session,
                                                   self.settings.request_timeout)
        return self._finmind

    @property
    def official(self) -> fetchers.OfficialClient:
        if self._official is None:
            self._official = fetchers.OfficialClient(self._session, self.settings.request_timeout,
                                                     self.settings.request_gap)
        return self._official

    # ---------- 名稱與名單 ----------
    def names(self) -> dict[str, str]:
        if self._names is None:
            n = dict(sample.SAMPLE_NAMES)
            if self.radar:
                n.update(self.radar.names())
            self._names = n
        return self._names

    def name(self, code: str) -> str:
        return self.names().get(code, "")

    def universes(self) -> dict[str, list[str]]:
        """可選的選股範圍。有台股雷達時包含「我的族群」各組與「自選股」。"""
        out: dict[str, list[str]] = {}
        if self.radar and not self.settings.demo:
            wl = self.radar.watchlist()
            if wl:
                out["自選股"] = wl
            groups = self.radar.groups()
            if groups:
                allg = []
                for codes in groups.values():
                    allg.extend(c for c in codes if c not in allg)
                out["我的族群（全部）"] = allg
                for g, codes in groups.items():
                    out[f"族群：{g}"] = codes
        if not out:
            out["範例清單"] = list(sample.SAMPLE_NAMES)
        return out

    # ---------- 取資料 ----------
    def get(self, kind: str, code: str, years: float = 3.0) -> tuple[pd.DataFrame, str]:
        cols = KINDS[kind]
        code = str(code).strip()
        if self.settings.demo:
            return self._sample(kind, code), "模擬資料"

        if self.radar and kind in ("price", "institutional", "revenue"):
            df = getattr(self.radar, kind)(code)
            if not df.empty:
                return df, "台股雷達本機資料"

        if self.cache.is_fresh(kind, code, max_age_hours=6 if kind == "price" else 24):
            df = self.cache.load(kind, code)
            if df is not None and not df.empty:
                return schema.normalize(df, cols), "本機快取"

        errors = []
        if self.settings.use_network:
            start = self.today - timedelta(days=int(365 * years))
            for label, fn in self._network_plan(kind, code):
                try:
                    df = fn(code, start, self.today)
                except fetchers.FetchError as e:
                    errors.append(f"{label}: {e}")
                    continue
                if not df.empty:
                    self.cache.save(kind, code, df)
                    return df, label

        stale = self.cache.load(kind, code)
        if stale is not None and not stale.empty:
            return schema.normalize(stale, cols), "過期快取（網路失敗）"
        return schema.empty(cols), ("無資料：" + "；".join(errors)) if errors else "無資料"

    def _network_plan(self, kind: str, code: str):
        fm = self.finmind
        plan = {
            "price": [("FinMind", fm.price), ("證交所", self.official.price_twse), ("櫃買中心", self.official.price_tpex)],
            "institutional": [("FinMind", fm.institutional)],
            "holding": [("FinMind 集保股權分散", fm.holding)],
            "revenue": [("FinMind", fm.revenue)],
            "financials": [("FinMind", fm.financials)],
        }[kind]
        if kind == "price" and self.radar:
            mk = self.radar.markets().get(code)
            if mk == "otc":
                plan = [plan[0], plan[2], plan[1]]
        return plan

    @staticmethod
    def _sample(kind: str, code: str) -> pd.DataFrame:
        if kind == "price":
            return sample.price(code)
        if kind == "institutional":
            return sample.institutional(code)
        if kind == "holding":
            return sample.holding(code)
        if kind == "revenue":
            return sample.revenue(code)
        return sample.financials(code)

    def bundle(self, code: str, kinds=tuple(KINDS), years: float = 3.0) -> StockBundle:
        data, sources = {}, {}
        for k in KINDS:
            if k in kinds:
                data[k], sources[k] = self.get(k, code, years)
            else:
                data[k], sources[k] = schema.empty(KINDS[k]), "未載入"
        if sources.get("institutional") == "台股雷達本機資料":
            unit = self.settings.extra.get("radar_inst_unit", "auto")
            data["institutional"] = fix_inst_unit(data["institutional"], data["price"], unit)
        return StockBundle(code=code, name=self.name(code), sources=sources, **data)


def fix_inst_unit(inst: pd.DataFrame, px: pd.DataFrame, unit: str = "auto") -> pd.DataFrame:
    """台股雷達的法人買賣超若以「張」記錄，換成「股」與成交量一致。

    unit = "shares"：不動；"lots"：一律 ×1000；"auto"：自動判斷 ——
    法人有進出那幾天的 |買賣超| 中位數不到成交股數中位數的 0.2% → 判定為張。
    （以股計時這個比值通常在 2%～20%；以張計會再小 1000 倍，約 0.002%～0.02%，兩者差距很大。）
    """
    if inst.empty or unit == "shares":
        return inst
    if unit == "lots":
        return inst * 1000.0
    if px.empty:
        return inst
    vol_med = px["volume"].median()
    inst_med = inst["total"].abs().replace(0, pd.NA).dropna().median()
    if pd.notna(vol_med) and pd.notna(inst_med) and vol_med > 0 and inst_med / vol_med < 2e-3:
        return inst * 1000.0
    return inst
