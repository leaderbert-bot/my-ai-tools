import os
from datetime import date, datetime

import pandas as pd

from twsa.config import Settings
from twsa.data.cache import CsvCache
from twsa.data.hub import DataHub
from conftest import FakeResp, FakeSession

FM_PRICE = {"status": 200, "data": [
    {"date": "2026-10-01", "Trading_Volume": 1000, "open": 10, "max": 11, "min": 9, "close": 10.5}]}


def _settings(tmp_path, **kw):
    return Settings(data_dir=str(tmp_path / "d"), radar_dir=None, **kw)


def test_network_then_cache(tmp_path):
    sess = FakeSession({"finmindtrade#TaiwanStockPrice": FM_PRICE})
    hub = DataHub(_settings(tmp_path), session=sess, today=date(2026, 10, 21))
    df, src = hub.get("price", "2330")
    assert src == "FinMind" and len(df) == 1
    assert hub.cache.path("price", "2330").is_file()
    hub2 = DataHub(_settings(tmp_path), session=FakeSession({}), today=date(2026, 10, 21))
    hub2.cache.is_fresh = lambda *a, **k: True
    df2, src2 = hub2.get("price", "2330")
    assert src2 == "本機快取" and df2["close"].iloc[0] == 10.5


def test_fallback_to_official_then_stale_cache(tmp_path):
    twse = {"stat": "OK", "fields": ["日期", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價"],
            "data": [["115/10/01", "1,000", "x", "10", "11", "9", "10.5"]]}
    sess = FakeSession({"finmindtrade": FakeResp({}, 503), "twse.com.tw": twse})
    s = _settings(tmp_path, request_gap=0)
    hub = DataHub(s, session=sess, today=date(2026, 10, 2))
    df, src = hub.get("price", "2330", years=0.01)
    assert src == "證交所" and df["close"].iloc[0] == 10.5

    dead = FakeSession({"finmindtrade": ConnectionError("x"), "twse": ConnectionError("x"), "tpex": ConnectionError("x")})
    hub2 = DataHub(s, session=dead, today=date(2026, 10, 2))
    hub2.cache.is_fresh = lambda *a, **k: False
    df2, src2 = hub2.get("price", "2330", years=0.01)
    assert src2.startswith("過期快取") and len(df2) == 1


def test_no_data_reports_errors(tmp_path):
    hub = DataHub(_settings(tmp_path), session=FakeSession({}), today=date(2026, 10, 2))
    df, src = hub.get("revenue", "2330")
    assert df.empty and src.startswith("無資料") and "FinMind" in src


def test_offline_never_touches_network(tmp_path):
    sess = FakeSession({"finmindtrade": FM_PRICE})
    hub = DataHub(_settings(tmp_path, use_network=False), session=sess)
    df, src = hub.get("price", "2330")
    assert df.empty and src == "無資料" and sess.calls == []


def test_demo_mode(demo_settings):
    hub = DataHub(demo_settings)
    b = hub.bundle("2330")
    assert set(b.sources.values()) == {"模擬資料"}
    assert len(b.price) == 750 and not b.institutional.empty and not b.revenue.empty
    assert "範例清單" in hub.universes()
    assert (b.price["low"] <= b.price[["open", "close"]].min(axis=1)).all()


def test_cache_freshness_after_close(tmp_path):
    c = CsvCache(tmp_path)
    c.save("price", "2330", pd.DataFrame({"close": [1.0]}, index=pd.to_datetime(["2026-10-01"])))
    p = c.path("price", "2330")
    noon = datetime(2026, 10, 21, 12, 0).timestamp()
    os.utime(p, (noon, noon))
    assert c.is_fresh("price", "2330", now=datetime(2026, 10, 21, 13, 0))
    assert not c.is_fresh("price", "2330", now=datetime(2026, 10, 21, 16, 0))   # 中午的快取不算今天收盤
    c.save("revenue", "2330", pd.DataFrame({"revenue": [1.0]}, index=pd.to_datetime(["2026-09-01"])))
    os.utime(c.path("revenue", "2330"), (noon, noon))
    assert c.is_fresh("revenue", "2330", now=datetime(2026, 10, 21, 16, 0))   # 營收不受收盤時點限制
    assert not c.is_fresh("price", "9999")
