"""服務層：Tkinter 介面與網頁儀表板共用。回傳的都是可直接轉 JSON 的 dict。"""

from __future__ import annotations

import math
import re
import threading

import pandas as pd

from . import report, strategies
from .backtest import BacktestConfig
from .config import Settings
from .data.hub import DataHub
from .screener import ScreenResult, analyze_stock, screen

_CODE_RE = re.compile(r"^[0-9A-Z]{4,6}$")


def clean(v):
    """把 numpy / pandas / NaN 轉成 JSON 可用的值。"""
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        try:
            v = v.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if v is pd.NaT:
        return None
    return v


def parse_codes(text: str) -> list[str]:
    out = []
    for tok in re.split(r"[\s,，;；、]+", str(text or "").upper()):
        tok = tok.strip()
        if _CODE_RE.match(tok) and tok not in out:
            out.append(tok)
    return out


def frame_records(df: pd.DataFrame, cols: list[str] | None = None, tail: int | None = None, digits: int = 2):
    if df is None or df.empty:
        return []
    d = df[cols] if cols else df
    if tail:
        d = d.tail(tail)
    out = []
    for idx, row in d.iterrows():
        rec = {"date": idx.date().isoformat() if isinstance(idx, pd.Timestamp) else str(idx)}
        for k, v in row.items():
            v = clean(v)
            rec[k] = round(v, digits) if isinstance(v, float) else v
        out.append(rec)
    return out


class AppService:
    def __init__(self, settings: Settings, hub: DataHub | None = None):
        self.settings = settings
        self.hub = hub or DataHub(settings)
        self.last_result: ScreenResult | None = None
        self._lock = threading.Lock()
        self.progress = {"running": False, "done": 0, "total": 0, "code": ""}

    # ---------- 基本資訊 ----------
    def status(self) -> dict:
        radar = self.hub.radar
        return clean({
            "mode": "模擬資料（離線展示）" if self.settings.demo else "實際資料",
            "radar_dir": self.settings.radar_dir,
            "radar_connected": radar is not None,
            "radar_files": radar.files() if radar else {},
            "finmind_token": bool(self.settings.finmind_token),
            "use_network": self.settings.use_network,
            "universes": {k: len(v) for k, v in self.hub.universes().items()},
        })

    def strategy_list(self) -> list[dict]:
        return [s.to_dict() for s in strategies.REGISTRY.values()]

    def universe_codes(self, universe: str | None, codes_text: str | None = None) -> list[str]:
        codes = parse_codes(codes_text) if codes_text else []
        if codes:
            return codes
        u = self.hub.universes()
        if universe in u:
            return list(u[universe])
        return list(next(iter(u.values())))

    # ---------- 個股查詢 ----------
    def stock_detail(self, code: str, strategy_key: str = "ma_bull", params: dict | None = None,
                     bt: dict | None = None, bars: int = 250) -> dict:
        code = parse_codes(code)[0] if parse_codes(code) else str(code).strip()
        b, feats, sig, res = analyze_stock(self.hub, code, strategy_key, params,
                                           BacktestConfig.from_dict(bt),
                                           kinds=("price", "institutional", "holding", "revenue", "financials"))
        if feats.empty:
            return clean({"code": code, "name": b.name, "ok": False, "sources": b.sources,
                          "message": f"找不到 {code} 的行情資料（{b.sources.get('price')}）"})
        last = feats.iloc[-1]
        snapshot = {k: clean(last.get(k)) for k in
                    ("close", "ma5", "ma10", "ma20", "ma60", "ma120", "roc20", "rsi14", "vol_ratio",
                     "chip_conc", "foreign_buy_streak", "trust_buy_streak", "big_holder_pct",
                     "big_holder_chg4w", "rev_yoy", "rev_yoy_3m", "eps_ttm", "pe", "gross_margin")}
        prev_close = feats["close"].iloc[-2] if len(feats) > 1 else float("nan")
        checks = {}
        for key, s in strategies.REGISTRY.items():
            checks[key] = {"label": s.label, "hit": bool(s.signal(feats).iloc[-1])}
        sig_dates = [d.date().isoformat() for d in sig.index[sig & ~sig.shift(1, fill_value=False)]]
        return clean({
            "ok": True, "code": code, "name": b.name, "sources": b.sources,
            "date": feats.index[-1].date().isoformat(),
            "change": last["close"] - prev_close,
            "change_pct": (last["close"] / prev_close - 1) * 100 if prev_close else None,
            "snapshot": snapshot,
            "checks": checks,
            "strategy": strategy_key,
            "signal_dates": sig_dates[-30:],
            "ohlc": frame_records(feats, ["open", "high", "low", "close", "volume", "ma5", "ma20", "ma60"], bars),
            "institutional": frame_records(b.institutional, None, 60, 0),
            "holding": frame_records(b.holding, None, 26),
            "revenue": frame_records(b.revenue, None, 24),
            "financials": frame_records(b.financials, None, 8),
            "backtest": res.stats,
            "trades": frame_records(res.trades.set_index("entry_date"), None, None, 2) if len(res.trades) else [],
            "equity": [{"date": d.date().isoformat(), "v": round(float(v), 4)}
                       for d, v in res.equity.iloc[::max(1, len(res.equity) // 300)].items()],
        })

    # ---------- 一鍵選股 ----------
    def run_screen(self, strategy_key: str, universe: str | None = None, codes_text: str | None = None,
                   params: dict | None = None, bt: dict | None = None, lookback: int = 0) -> dict:
        codes = self.universe_codes(universe, codes_text)
        with self._lock:
            self.progress = {"running": True, "done": 0, "total": len(codes), "code": ""}

            def prog(i, n, c):
                self.progress.update(done=i, total=n, code=c)

            try:
                res = screen(self.hub, codes, strategy_key, params, BacktestConfig.from_dict(bt),
                             lookback_days=int(lookback or 0), progress=prog)
            finally:
                self.progress["running"] = False
            self.last_result = res
        return self.result_dict(res)

    @staticmethod
    def result_dict(res: ScreenResult) -> dict:
        return clean({
            "strategy": res.strategy,
            "strategy_label": strategies.get(res.strategy).label,
            "params": res.params, "backtest": res.backtest, "summary": res.summary,
            "columns": list(res.table.columns),
            "rows": res.table.to_dict(orient="records"),
            "errors": res.errors[:30],
        })

    def export_last(self, fmt: str = "xlsx") -> tuple[bytes, str]:
        if self.last_result is None:
            raise RuntimeError("請先執行一次選股")
        fmt = fmt.lower()
        data = report.to_excel_bytes(self.last_result) if fmt == "xlsx" else report.to_csv_bytes(self.last_result)
        return data, report.default_filename(self.last_result, fmt)

    def export_last_to_disk(self, fmt: str = "xlsx"):
        if self.last_result is None:
            raise RuntimeError("請先執行一次選股")
        return report.export(self.last_result, self.settings.export_dir, fmt)
