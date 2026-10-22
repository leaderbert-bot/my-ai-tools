import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from twsa.config import Settings  # noqa: E402
from twsa.data.radar_adapter import RadarSource  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    for k in ("TWSA_RADAR_DIR", "TWSA_DATA_DIR", "FINMIND_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    RadarSource._cache.clear()


@pytest.fixture
def demo_settings(tmp_path):
    return Settings(demo=True, data_dir=str(tmp_path / "twsa_data"), use_network=False)


def make_price(closes, start="2026-01-05", vol=1_000_000, spread=0.01):
    closes = np.asarray(closes, dtype=float)
    idx = pd.bdate_range(start, periods=len(closes), name="date")
    opens = np.concatenate([[closes[0]], closes[:-1]])
    return pd.DataFrame({
        "open": opens,
        "high": np.maximum(opens, closes) * (1 + spread),
        "low": np.minimum(opens, closes) * (1 - spread),
        "close": closes,
        "volume": np.full(len(closes), float(vol)),
    }, index=idx)


@pytest.fixture
def uptrend():
    return make_price(np.linspace(50, 100, 200))


@pytest.fixture
def downtrend():
    return make_price(np.linspace(100, 50, 200))


class FakeResp:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeSession:
    """依 URL 子字串（以及可選的 dataset 參數）回傳預先準備好的 JSON。"""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, dict(params or {}), headers))
        for key, payload in self.routes.items():
            u, _, ds = key.partition("#")
            if u in url and (not ds or (params or {}).get("dataset") == ds):
                if isinstance(payload, Exception) and not isinstance(payload, ValueError):
                    raise payload
                if callable(payload):
                    return payload(url, params)
                return payload if isinstance(payload, FakeResp) else FakeResp(payload)
        return FakeResp({"msg": "not found"}, 404)


@pytest.fixture
def radar_dir(tmp_path):
    """模擬台股雷達的 00money 資料夾（格式取自實際檔案：kline、groups.csv、watchlist.json）。"""
    root = tmp_path / "00money"
    d = root / "data"
    (d / "kline").mkdir(parents=True)
    days = pd.bdate_range("2026-01-05", periods=150)
    closes = np.linspace(100, 160, len(days))
    px = {}
    for code, mult in (("2330", 1.0), ("3017", 0.5)):
        rows = []
        for t, c in zip(days, closes * mult):
            o = c * 0.995
            rows.append([t.strftime("%Y-%m-%d"), round(o, 2), round(c * 1.01, 2), round(o * 0.99, 2), round(c, 2), 2_000_000.0])
        px[code] = rows
    # 一根「最高 < 收盤」的壞 K 棒，要被物理檢查濾掉
    px["2330"][10] = [px["2330"][10][0], 100.0, 90.0, 80.0, 95.0, 1.0]
    (d / "px_history.json").write_text(json.dumps(px), encoding="utf-8")
    # 單檔補抓的 K 線（比 px_history 更早的兩天）
    (d / "kline" / "2330-202512.json").write_text(json.dumps([
        ["2025-12-30", 95.0, 97.0, 94.0, 96.0, 1000.0],
        ["2025-12-31", 96.0, 99.0, 95.5, 98.0, 1200.0],
    ]), encoding="utf-8")
    # 法人：以日期為主、單位為「張」
    inst = {t.strftime("%Y-%m-%d"): {"2330": [300, 50, -20], "3017": {"外資": -10, "投信": 5, "自營": 0}}
            for t in days}
    (d / "inst_hist.json").write_text(json.dumps({"data": inst, "meta": {"v": 2}}), encoding="utf-8")
    # 月營收：民國年月 key、以代號為主
    hist = {"2330": {f"{114 + (m - 1) // 12}{(m - 1) % 12 + 1:02d}": 1000 + 10 * m for m in range(1, 22)}}
    (d / "history.json").write_text(json.dumps(hist), encoding="utf-8")
    (d / "groups.csv").write_bytes("產業,公司代號,公司名稱\r\n權值重點,2330,台積電\r\n散熱族群,3017,奇鋐\r\n散熱族群,2421,建準*\r\n記憶體,6531,愛普*\r\n".encode("utf-8-sig"))
    (d / "watchlist.json").write_text(json.dumps(["2330", "3017"]), encoding="utf-8")
    (d / "stock_names.json").write_text(json.dumps({"2330": "台積電", "3017": {"name": "奇鋐"}}), encoding="utf-8")
    (d / "markets.json").write_text(json.dumps({"2330": "sii", "3017": "sii", "6488": "otc"}), encoding="utf-8")
    return root
