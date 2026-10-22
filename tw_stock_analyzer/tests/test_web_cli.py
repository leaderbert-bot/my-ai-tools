import json
import threading
import urllib.error
import urllib.request
from urllib.parse import quote

import pytest

from twsa.__main__ import main
from twsa.service import AppService
from twsa.web.server import create_server


@pytest.fixture
def server(demo_settings):
    svc = AppService(demo_settings)
    httpd = create_server(svc, port=0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.status, dict(r.headers), r.read()


def get_json(url):
    s, _, b = get(url)
    return s, json.loads(b)


def test_index_and_status(server):
    s, h, b = get(server + "/")
    assert s == 200 and "台股" in b.decode("utf-8") and h["Content-Type"].startswith("text/html")
    s, st = get_json(server + "/api/status")
    assert st["mode"].startswith("模擬") and st["universes"]["範例清單"] == 15
    s, strs = get_json(server + "/api/strategies")
    assert {x["key"] for x in strs} >= {"ma_bull", "momentum_breakout", "chip_concentration"}


def test_stock_and_screen_and_export(server):
    s, d = get_json(server + "/api/stock?code=2330&strategy=combo&bt_hold_days=10")
    assert d["ok"] and d["code"] == "2330" and d["strategy"] == "combo"

    with pytest.raises(urllib.error.HTTPError) as e:
        get(server + "/api/export?fmt=xlsx")
    assert e.value.code == 409

    s, r = get_json(server + "/api/screen?strategy=chip_concentration&universe=" + quote("範例清單")
                    + "&p_min_conc=1&bt_stop_loss=5&lookback=3")
    assert r["params"]["min_conc"] == 1.0 and r["backtest"]["stop_loss"] == 5.0
    assert r["summary"]["scanned"] == 15 and len(r["rows"]) == 15

    s, h, b = get(server + "/api/export?fmt=xlsx")
    assert s == 200 and b[:2] == b"PK" and "attachment" in h["Content-Disposition"]
    s, h, b = get(server + "/api/export?fmt=csv")
    assert b.startswith(b"\xef\xbb\xbf")
    s, p = get_json(server + "/api/progress")
    assert p["running"] is False and p["total"] == 15


def test_errors_are_json(server):
    for path, code in (("/api/stock", 400), ("/api/screen?strategy=nope", 400), ("/nope", 404)):
        with pytest.raises(urllib.error.HTTPError) as e:
            get(server + path)
        assert e.value.code == code
        assert "message" in json.loads(e.value.read())


def test_cli_list_and_screen(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TWSA_DATA_DIR", str(tmp_path))
    assert main(["--demo", "list"]) == 0
    assert "均線多頭排列" in capsys.readouterr().out
    assert main(["--demo", "stock", "2330"]) == 0
    assert "台積電" in capsys.readouterr().out
    assert main(["--demo", "screen", "--strategy", "ma_bull", "--codes", "2330,2317", "--export", "csv"]) == 0
    out = capsys.readouterr().out
    assert "掃描 2 檔" in out and "已匯出" in out
    assert list((tmp_path / "exports").glob("*.csv"))


def test_cli_with_radar_dir(radar_dir, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TWSA_DATA_DIR", str(tmp_path))
    assert main(["--offline", "--radar-dir", str(radar_dir), "screen", "--strategy", "ma_bull",
                 "--universe", "自選股"]) == 0
    out = capsys.readouterr().out
    assert "掃描 2 檔" in out
