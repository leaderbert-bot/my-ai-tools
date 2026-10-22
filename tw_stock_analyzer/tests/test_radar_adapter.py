import json

import pandas as pd
import pytest

from twsa.config import Settings, load_settings
from twsa.data.hub import DataHub, fix_inst_unit
from twsa.data.radar_adapter import RadarSource, extract_series, parse_month_key


def test_parse_month_key_variants():
    assert parse_month_key("2026-08") == pd.Timestamp("2026-08-01")
    assert parse_month_key("202608") == pd.Timestamp("2026-08-01")
    assert parse_month_key("11508") == pd.Timestamp("2026-08-01")
    assert parse_month_key("115/08") == pd.Timestamp("2026-08-01")
    assert parse_month_key("2330") is None


@pytest.mark.parametrize("raw", [
    {"2330": [["2026-10-01", 1, 2, 0.5, 1.5, 100]]},                          # 以代號為主 + list
    {"2026-10-01": {"2330": [1, 2, 0.5, 1.5, 100]}},                           # 以日期為主 + list
    {"2026-10-01": {"2330": {"o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100}}},  # 以日期為主 + dict
    {"2330": {"20261001": {"開盤": 1, "最高": 2, "最低": 0.5, "收盤": 1.5, "成交股數": "100"}}},
    {"meta": {"x": 1}, "data": {"2330": [{"date": "2026/10/01", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100}]}},
])
def test_extract_series_shapes(raw):
    df = extract_series(raw, "2330", ["open", "high", "low", "close", "volume"])
    assert len(df) == 1
    assert df.index[0] == pd.Timestamp("2026-10-01")
    assert df.iloc[0].tolist() == [1, 2, 0.5, 1.5, 100]


def test_extract_series_missing_code():
    assert extract_series({"2330": []}, "9999", ["close"]).empty


def test_radar_price_merges_kline_and_filters_bad_bars(radar_dir):
    src = RadarSource(radar_dir / "data")
    px = src.price("2330")
    assert px.index[0] == pd.Timestamp("2025-12-30")          # 來自 kline/ 補抓檔
    assert len(px) == 150 + 2 - 1                             # 一根壞 K 棒被濾掉
    assert (px["low"] <= px[["open", "close"]].min(axis=1)).all()
    assert src.price("9999").empty


def test_radar_institutional_and_revenue(radar_dir):
    src = RadarSource(radar_dir / "data")
    inst = src.institutional("2330")
    assert inst.iloc[0].tolist() == [300, 50, -20, 330]       # total 自動加總
    inst2 = src.institutional("3017")
    assert inst2.iloc[0].tolist() == [-10, 5, 0, -5]          # dict 中文欄名
    rev = src.revenue("2330")
    assert rev.index[0] == pd.Timestamp("2025-01-01")
    assert rev.loc["2026-01-01", "yoy"] == pytest.approx((1130 / 1010 - 1) * 100)


def test_radar_lists(radar_dir):
    src = RadarSource(radar_dir / "data")
    g = src.groups()
    assert g == {"權值重點": ["2330"], "散熱族群": ["3017", "2421"], "記憶體": ["6531"]}
    assert src.watchlist() == ["2330", "3017"]
    names = src.names()
    assert names["2421"] == "建準" and names["3017"] == "奇鋐" and names["6531"] == "愛普"
    assert src.markets()["6488"] == "otc"
    assert all(src.files().values())


def test_groups_csv_cp950(tmp_path):
    (tmp_path / "groups.csv").write_bytes("產業,公司代號,公司名稱\r\n重電,1513,中興電\r\n".encode("cp950"))
    assert RadarSource(tmp_path).groups() == {"重電": ["1513"]}


def test_hub_prefers_radar_and_builds_universes(radar_dir, tmp_path):
    s = Settings(radar_dir=str(radar_dir), data_dir=str(tmp_path / "d"), use_network=False)
    hub = DataHub(s)
    df, src = hub.get("price", "2330")
    assert src == "台股雷達本機資料" and len(df) == 151
    u = hub.universes()
    assert u["自選股"] == ["2330", "3017"]
    assert u["我的族群（全部）"] == ["2330", "3017", "2421", "6531"]
    assert u["族群：散熱族群"] == ["3017", "2421"]
    b = hub.bundle("2330")
    # 法人資料是「張」，成交量是「股」→ 自動換算
    assert b.institutional["total"].iloc[0] == 330_000
    assert b.name == "台積電"


def test_fix_inst_unit_leaves_shares_alone():
    idx = pd.bdate_range("2026-01-01", periods=5)
    px = pd.DataFrame({"volume": 1_000_000.0}, index=idx)
    inst = pd.DataFrame({"foreign": 50_000.0, "trust": 0.0, "dealer": 0.0, "total": 50_000.0}, index=idx)
    assert fix_inst_unit(inst, px)["total"].iloc[0] == 50_000.0
    assert fix_inst_unit(inst / 1000, px)["total"].iloc[0] == 50_000.0
    assert fix_inst_unit(inst, px, "lots")["total"].iloc[0] == 50_000_000.0
    assert fix_inst_unit(inst / 1000, px, "shares")["total"].iloc[0] == 50.0


def test_settings_file_and_env(tmp_path, monkeypatch):
    cfg = tmp_path / "s.json"
    cfg.write_text(json.dumps({"radar_dir": "X:/nowhere", "port": 9999,
                               "radar_columns": {"inst": ["trust", "foreign", "dealer"]}}), encoding="utf-8")
    s = load_settings(cfg)
    assert s.port == 9999 and s.radar_dir == "X:/nowhere"
    assert s.extra["radar_columns"]["inst"][0] == "trust"
    monkeypatch.setenv("TWSA_RADAR_DIR", str(tmp_path))
    monkeypatch.setenv("FINMIND_TOKEN", "abc")
    s2 = load_settings(cfg)
    assert s2.radar_dir == str(tmp_path) and s2.finmind_token == "abc"
    assert s2.to_dict()["finmind_token"] == "***"


def test_custom_column_order(radar_dir, tmp_path):
    s = Settings(radar_dir=str(radar_dir), data_dir=str(tmp_path / "d"), use_network=False,
                 extra={"radar_columns": {"inst": ["trust", "foreign", "dealer"]}})
    df, _ = DataHub(s).get("institutional", "2330")
    assert df.iloc[0]["trust"] == 300 and df.iloc[0]["foreign"] == 50
