import io

import pandas as pd
import pytest

from twsa import report
from twsa.data.hub import DataHub
from twsa.screener import screen
from twsa.service import AppService, clean, parse_codes


@pytest.fixture
def demo_hub(demo_settings):
    return DataHub(demo_settings)


def test_screen_all_strategies(demo_hub):
    codes = ["2330", "2317", "3017", "2454"]
    for key in ("ma_bull", "momentum_breakout", "chip_concentration", "revenue_growth", "combo", "breakout_with_chips"):
        r = screen(demo_hub, codes, key)
        assert len(r.table) == 4
        assert {"代號", "名稱", "符合", "回測勝率%", "策略MDD%"} <= set(r.table.columns)
        assert r.summary["scanned"] == 4
        if r.summary["win_rate"] is not None:
            assert 0 <= r.summary["win_rate"] <= 100
        assert (r.table["策略MDD%"].dropna() <= 0).all()


def test_lookback_widens_matches(demo_hub):
    codes = list(demo_hub.universes()["範例清單"])
    r0 = screen(demo_hub, codes, "momentum_breakout", lookback_days=0)
    r10 = screen(demo_hub, codes, "momentum_breakout", lookback_days=10)
    assert r10.summary["matched"] >= r0.summary["matched"]
    assert r10.table.loc[r10.table["符合"], "幾根前"].between(0, 10).all()


def test_screen_reports_missing_stocks(tmp_path):
    from twsa.config import Settings
    hub = DataHub(Settings(data_dir=str(tmp_path), use_network=False))
    r = screen(hub, ["2330"], "ma_bull")
    assert r.table.empty and r.errors and "無行情資料" in r.errors[0]


def test_excel_export_has_sheets(demo_hub, tmp_path):
    r = screen(demo_hub, ["2330", "2317"], "combo")
    data = report.to_excel_bytes(r)
    sheets = pd.read_excel(io.BytesIO(data), sheet_name=None)
    assert list(sheets) == ["選股結果", "符合清單", "回測交易明細", "參數與彙總"]
    assert len(sheets["選股結果"]) == 2
    assert "進場日" in sheets["回測交易明細"].columns
    meta = dict(zip(sheets["參數與彙總"]["項目"], sheets["參數與彙總"]["值"]))
    assert meta["策略"] == "綜合：多頭 + 籌碼 + 營收"
    p = report.export(r, tmp_path / "out", "xlsx")
    assert p.is_file() and p.suffix == ".xlsx"


def test_csv_export_is_excel_friendly(demo_hub, tmp_path):
    r = screen(demo_hub, ["2330"], "ma_bull")
    b = report.to_csv_bytes(r)
    assert b.startswith(b"\xef\xbb\xbf")             # BOM：Excel 直接開不會亂碼
    assert "代號" in b.decode("utf-8-sig").splitlines()[0]
    assert report.export(r, tmp_path, "csv").read_bytes() == b
    with pytest.raises(ValueError):
        report.export(r, tmp_path, "pdf")


def test_service_stock_detail(demo_settings):
    svc = AppService(demo_settings)
    d = svc.stock_detail("2330", "ma_bull")
    assert d["ok"] and d["name"] == "台積電"
    assert len(d["ohlc"]) == 250 and len(d["revenue"]) == 24
    assert set(d["checks"]) >= {"ma_bull", "combo"}
    assert d["backtest"]["trades"] >= 0
    import json
    json.dumps(d, allow_nan=False)                    # 不能有 NaN，前端才吃得下


def test_service_export_requires_screen(demo_settings):
    svc = AppService(demo_settings)
    with pytest.raises(RuntimeError):
        svc.export_last()
    svc.run_screen("ma_bull", codes_text="2330 2317，abc")
    data, name = svc.export_last("csv")
    assert name.endswith(".csv") and data
    assert svc.export_last_to_disk("xlsx").is_file()


def test_parse_codes_and_clean():
    assert parse_codes("2330, 2317，2454 2330 ab 00878") == ["2330", "2317", "2454", "00878"]
    assert clean({"a": float("nan"), "b": [pd.Timestamp("2026-01-02")], "c": pd.NA if False else 1}) == \
        {"a": None, "b": ["2026-01-02"], "c": 1}
