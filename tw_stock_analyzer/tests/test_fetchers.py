import math

import pandas as pd
import pytest

from twsa.data import fetchers
from conftest import FakeResp, FakeSession


def test_to_number_and_roc_date():
    assert fetchers.to_number("1,234.5") == 1234.5
    assert fetchers.to_number("+3.5") == 3.5
    assert fetchers.to_number("X0.00") == 0.0
    assert math.isnan(fetchers.to_number("--"))
    assert math.isnan(fetchers.to_number(None))
    assert fetchers.roc_to_date("115/10/01") == pd.Timestamp("2026-10-01")
    assert fetchers.roc_to_date("1151001") == pd.Timestamp("2026-10-01")
    assert fetchers.roc_to_date("99/01/05") == pd.Timestamp("2010-01-05")
    with pytest.raises(ValueError):
        fetchers.roc_to_date("hello")


def test_level_lower_bound():
    f = fetchers._level_lower_bound
    assert f("1-999") == 1
    assert f("400,001-600,000") == 400001
    assert f("more than 1,000,001") == 1000001
    assert f("total") == -1 and f("合計") == -1


FM_PRICE = {"status": 200, "data": [
    {"date": "2026-10-01", "stock_id": "2330", "Trading_Volume": 1000, "open": 10, "max": 11, "min": 9, "close": 10.5},
    {"date": "2026-10-02", "stock_id": "2330", "Trading_Volume": 0, "open": 0, "max": 0, "min": 0, "close": 0},
    {"date": "2026-10-03", "stock_id": "2330", "Trading_Volume": 2000, "open": 10.5, "max": 12, "min": 10, "close": 11.5},
]}


def test_finmind_price_drops_halted_days_and_sends_token():
    sess = FakeSession({"finmindtrade#TaiwanStockPrice": FM_PRICE})
    df = fetchers.FinMindClient("TOKEN", session=sess).price("2330", "2026-10-01", "2026-10-03")
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) == 2 and df["high"].iloc[1] == 12
    assert sess.calls[0][2] == {"Authorization": "Bearer TOKEN"}
    assert sess.calls[0][1]["data_id"] == "2330"


def test_finmind_institutional_pivot():
    data = [
        {"date": "2026-10-01", "name": "Foreign_Investor", "buy": 500, "sell": 100},
        {"date": "2026-10-01", "name": "Foreign_Dealer_Self", "buy": 10, "sell": 0},
        {"date": "2026-10-01", "name": "Investment_Trust", "buy": 50, "sell": 70},
        {"date": "2026-10-01", "name": "Dealer_self", "buy": 5, "sell": 0},
        {"date": "2026-10-01", "name": "Dealer_Hedging", "buy": 0, "sell": 15},
        {"date": "2026-10-01", "name": "total", "buy": 999, "sell": 0},
    ]
    sess = FakeSession({"finmindtrade#TaiwanStockInstitutionalInvestorsBuySell": {"status": 200, "data": data}})
    df = fetchers.FinMindClient(session=sess).institutional("2330", "2026-10-01")
    row = df.iloc[0]
    assert (row["foreign"], row["trust"], row["dealer"], row["total"]) == (410, -20, -10, 380)
    assert sess.calls[0][2] is None   # 沒 token 不送 Authorization


def test_finmind_holding_big_holders():
    data = []
    for d in ("2026-10-02", "2026-10-09"):
        data += [
            {"date": d, "HoldingSharesLevel": "1-999", "people": 1000, "percent": 10.0},
            {"date": d, "HoldingSharesLevel": "200,001-400,000", "people": 50, "percent": 20.0},
            {"date": d, "HoldingSharesLevel": "400,001-600,000", "people": 10, "percent": 25.0},
            {"date": d, "HoldingSharesLevel": "more than 1,000,001", "people": 3, "percent": 45.0},
            {"date": d, "HoldingSharesLevel": "total", "people": 1063, "percent": 100.0},
        ]
    sess = FakeSession({"finmindtrade#TaiwanStockHoldingSharesPer": {"status": 200, "data": data}})
    df = fetchers.FinMindClient(session=sess).holding("2330", "2026-10-01")
    assert df["big_holder_pct"].tolist() == [70.0, 70.0]
    assert df["holders"].iloc[0] == 1063


def test_finmind_revenue_uses_revenue_month_not_publish_date():
    data = [
        {"date": "2025-09-01", "revenue_year": 2025, "revenue_month": 8, "revenue": 100_000},
        {"date": "2026-09-01", "revenue_year": 2026, "revenue_month": 8, "revenue": 130_000},
    ]
    sess = FakeSession({"finmindtrade#TaiwanStockMonthRevenue": {"status": 200, "data": data}})
    df = fetchers.FinMindClient(session=sess).revenue("2330", "2025-01-01")
    assert df.index[-1] == pd.Timestamp("2026-08-01")
    assert df["revenue"].iloc[-1] == 130.0          # 元 → 仟元
    assert df["yoy"].iloc[-1] == pytest.approx(30.0)


def test_finmind_financials_margins():
    data = [{"date": "2026-06-30", "type": t, "value": v} for t, v in
            (("EPS", 3.2), ("Revenue", 1000), ("GrossProfit", 450), ("OperatingIncome", 300), ("IncomeAfterTaxes", 250))]
    sess = FakeSession({"finmindtrade#TaiwanStockFinancialStatements": {"status": 200, "data": data}})
    df = fetchers.FinMindClient(session=sess).financials("2330", "2026-01-01")
    r = df.iloc[0]
    assert (r["eps"], r["gross_margin"], r["operating_margin"], r["net_margin"]) == (3.2, 45.0, 30.0, 25.0)


def test_finmind_errors():
    bad = FakeSession({"finmindtrade": {"status": 402, "msg": "upper limit"}})
    with pytest.raises(fetchers.FetchError, match="402"):
        fetchers.FinMindClient(session=bad).price("2330", "2026-10-01")
    http = FakeSession({"finmindtrade": FakeResp({}, 500)})
    with pytest.raises(fetchers.FetchError, match="HTTP 500"):
        fetchers.FinMindClient(session=http).price("2330", "2026-10-01")
    boom = FakeSession({"finmindtrade": ConnectionError("down")})
    with pytest.raises(fetchers.FetchError, match="連線失敗"):
        fetchers.FinMindClient(session=boom).price("2330", "2026-10-01")
    notjson = FakeSession({"finmindtrade": FakeResp(ValueError("x"))})
    with pytest.raises(fetchers.FetchError, match="不是 JSON"):
        fetchers.FinMindClient(session=notjson).price("2330", "2026-10-01")


TWSE_DAY = {"stat": "OK",
            "fields": ["日期", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌價差", "成交筆數"],
            "data": [["115/10/01", "25,000,000", "x", "1,000.00", "1,010.00", "990.00", "1,005.00", "+5", "1"],
                     ["115/10/02", "20,000,000", "x", "--", "--", "--", "--", "0", "0"],
                     ["115/10/05", "30,000,000", "x", "1,005.00", "1,020.00", "1,000.00", "1,015.00", "+10", "1"]]}


def test_twse_stock_day_parsing():
    sess = FakeSession({"twse.com.tw/exchangeReport/STOCK_DAY": TWSE_DAY})
    df = fetchers.OfficialClient(session=sess, gap=0).price_twse("2330", "2026-10-01", "2026-10-31")
    assert len(df) == 2                                  # 無成交那天去掉
    assert df.loc["2026-10-01", "close"] == 1005.0
    assert df.loc["2026-10-05", "volume"] == 30_000_000
    assert sess.calls[0][1]["date"] == "20261001"


def test_tpex_parsing_lots_to_shares():
    js = {"tables": [{"fields": ["日 期", "成交張數", "成交仟元", "開盤", "最高", "最低", "收盤", "漲跌", "筆數"],
                      "data": [["115/10/01", "1,234", "x", "50.0", "52.0", "49.5", "51.0", "1", "9"]]}]}
    sess = FakeSession({"tpex.org.tw": js})
    df = fetchers.OfficialClient(session=sess, gap=0).price_tpex("6488", "2026-10-01", "2026-10-31")
    assert df["volume"].iloc[0] == 1_234_000
    assert df["close"].iloc[0] == 51.0


def test_twse_t86_market_day():
    fields = ["證券代號", "證券名稱", "外陸資買進股數(不含外資自營商)", "外陸資買賣超股數(不含外資自營商)",
              "投信買賣超股數", "自營商買賣超股數", "三大法人買賣超股數"]
    js = {"stat": "OK", "fields": fields, "data": [["2330 ", "台積電", "1", "1,000", "-200", "50", "850"]]}
    df = fetchers.OfficialClient(session=FakeSession({"fund/T86": js}), gap=0).institutional_market_day("2026-10-21")
    assert df.loc["2330"].tolist() == [1000, -200, 50, 850]


def test_month_starts():
    out = fetchers._month_starts(pd.Timestamp("2025-11-15").date(), pd.Timestamp("2026-02-01").date())
    assert [d.isoformat() for d in out] == ["2025-11-01", "2025-12-01", "2026-01-01", "2026-02-01"]
