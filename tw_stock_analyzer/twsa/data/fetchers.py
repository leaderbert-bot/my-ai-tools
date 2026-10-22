"""網路資料擷取（requests）。

兩組來源：
    * FinMind v4 API（上市櫃通吃、欄位乾淨；有 token 額度較高，沒有也能用）
    * 證交所 / 櫃買中心官方端點（免金鑰，作為 FinMind 失敗時的備援）

所有函式都回傳 ``twsa.data.schema`` 定義的統一格式。網路錯誤一律丟 ``FetchError``，
由上層 ``DataHub`` 決定要不要換下一個來源，不會讓整個程式掛掉。

session 參數可以注入假的物件（單元測試就是這樣做），只要有 ``get(url, params=, headers=, timeout=)``
並回傳具有 ``status_code`` 與 ``json()`` 的物件即可。
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime

import pandas as pd

from . import schema

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
TWSE_STOCK_DAY = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
TWSE_T86 = "https://www.twse.com.tw/fund/T86"
TPEX_STOCK_DAY = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"

HEADERS = {"User-Agent": "Mozilla/5.0 (TWSA stock analyzer; +https://github.com/)"}

# FinMind 三大法人 name 欄位 → 本系統欄位
_INST_NAME_MAP = {
    "Foreign_Investor": "foreign",
    "Foreign_Dealer_Self": "foreign",
    "Investment_Trust": "trust",
    "Dealer_self": "dealer",
    "Dealer_Hedging": "dealer",
    "Dealer": "dealer",
}


class FetchError(RuntimeError):
    pass


def _session(session):
    if session is not None:
        return session
    import requests

    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _get_json(session, url, params=None, headers=None, timeout=20.0):
    try:
        resp = session.get(url, params=params, headers=headers, timeout=timeout)
    except Exception as e:  # requests.RequestException 以及注入物件丟出的任何錯誤
        raise FetchError(f"連線失敗 {url}: {type(e).__name__}: {e}") from e
    if getattr(resp, "status_code", 200) != 200:
        raise FetchError(f"HTTP {resp.status_code} {url}")
    try:
        return resp.json()
    except ValueError as e:
        raise FetchError(f"回應不是 JSON：{url}") from e


def to_number(x) -> float:
    """'1,234.5' / '--' / 'X0.00' / '+3.5' → float；無法解析回 NaN。"""
    if x is None:
        return float("nan")
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", "")
    s = re.sub(r"^[Xx+]", "", s)
    if s in ("", "--", "---", "-", "N/A", "除權息", "除息", "除權"):
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def roc_to_date(s: str) -> pd.Timestamp:
    """民國日期 '115/10/01' 或 '1151001' → Timestamp('2026-10-01')。"""
    s = str(s).strip().replace("＊", "").replace("*", "")
    m = re.match(r"^(\d{2,3})[/\-.]?(\d{1,2})[/\-.]?(\d{1,2})$", s)
    if not m:
        raise ValueError(f"無法解析民國日期：{s!r}")
    y, mo, d = (int(g) for g in m.groups())
    return pd.Timestamp(year=y + 1911, month=mo, day=d)


def _month_starts(start: date, end: date) -> list[date]:
    out, cur = [], date(start.year, start.month, 1)
    while cur <= end:
        out.append(cur)
        cur = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
    return out


def _as_date(x) -> date:
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return pd.Timestamp(x).date()


# ───────────────────────────── FinMind ─────────────────────────────

class FinMindClient:
    def __init__(self, token: str | None = None, session=None, timeout: float = 20.0, gap: float = 0.0):
        self.token = token
        self.session = _session(session)
        self.timeout = timeout
        self.gap = gap

    def fetch(self, dataset: str, stock_id: str, start, end=None) -> pd.DataFrame:
        params = {"dataset": dataset, "data_id": stock_id, "start_date": str(_as_date(start))}
        if end is not None:
            params["end_date"] = str(_as_date(end))
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else None
        js = _get_json(self.session, FINMIND_URL, params=params, headers=headers, timeout=self.timeout)
        if self.gap:
            time.sleep(self.gap)
        status = js.get("status", 200)
        if status not in (200, "200"):
            raise FetchError(f"FinMind {dataset} 回應 {status}: {js.get('msg')}")
        return pd.DataFrame(js.get("data") or [])

    def price(self, stock_id: str, start, end=None) -> pd.DataFrame:
        raw = self.fetch("TaiwanStockPrice", stock_id, start, end)
        if raw.empty:
            return schema.empty(schema.PRICE_COLS)
        df = pd.DataFrame({
            "open": raw["open"], "high": raw["max"], "low": raw["min"],
            "close": raw["close"], "volume": raw["Trading_Volume"],
        })
        df.index = pd.to_datetime(raw["date"])
        df = df[(df["close"] > 0)]  # 停牌日 FinMind 會回 0
        return schema.normalize(df, schema.PRICE_COLS)

    def institutional(self, stock_id: str, start, end=None) -> pd.DataFrame:
        raw = self.fetch("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start, end)
        if raw.empty:
            return schema.empty(schema.INST_COLS)
        raw = raw.copy()
        raw["col"] = raw["name"].map(_INST_NAME_MAP)
        raw = raw.dropna(subset=["col"])
        raw["net"] = pd.to_numeric(raw["buy"], errors="coerce") - pd.to_numeric(raw["sell"], errors="coerce")
        piv = raw.pivot_table(index="date", columns="col", values="net", aggfunc="sum").fillna(0.0)
        piv.index = pd.to_datetime(piv.index)
        for c in ("foreign", "trust", "dealer"):
            if c not in piv.columns:
                piv[c] = 0.0
        piv["total"] = piv["foreign"] + piv["trust"] + piv["dealer"]
        return schema.normalize(piv, schema.INST_COLS)

    def holding(self, stock_id: str, start, end=None, big_lots: int = 400) -> pd.DataFrame:
        """集保股權分散表 → 每週「持股 >= big_lots 張」的大戶比例。"""
        raw = self.fetch("TaiwanStockHoldingSharesPer", stock_id, start, end)
        if raw.empty:
            return schema.empty(schema.HOLDING_COLS)
        raw = raw.copy()
        raw["low"] = raw["HoldingSharesLevel"].map(_level_lower_bound)
        raw["percent"] = pd.to_numeric(raw["percent"], errors="coerce")
        raw["people"] = pd.to_numeric(raw.get("people"), errors="coerce")
        big = raw[raw["low"] >= big_lots * 1000].groupby("date")["percent"].sum()
        # 「合計」那一列（low = -1）的人數就是總股東數；沒有就加總各級距
        tot = raw[raw["low"] == -1].groupby("date")["people"].sum()
        if tot.empty:
            tot = raw[raw["low"] >= 0].groupby("date")["people"].sum()
        df = pd.DataFrame({"big_holder_pct": big, "holders": tot})
        df.index = pd.to_datetime(df.index)
        return schema.normalize(df, schema.HOLDING_COLS)

    def revenue(self, stock_id: str, start, end=None) -> pd.DataFrame:
        raw = self.fetch("TaiwanStockMonthRevenue", stock_id, start, end)
        if raw.empty:
            return schema.empty(schema.REVENUE_COLS)
        # FinMind 的 date 是公告月（次月），revenue_year/revenue_month 才是營收所屬月份
        idx = pd.to_datetime(dict(year=raw["revenue_year"].astype(int),
                                  month=raw["revenue_month"].astype(int), day=1))
        df = pd.DataFrame({"revenue": pd.to_numeric(raw["revenue"], errors="coerce") / 1000.0})
        df.index = idx
        return schema.add_revenue_growth(df)

    def financials(self, stock_id: str, start, end=None) -> pd.DataFrame:
        raw = self.fetch("TaiwanStockFinancialStatements", stock_id, start, end)
        if raw.empty:
            return schema.empty(schema.FIN_COLS)
        piv = raw.pivot_table(index="date", columns="type", values="value", aggfunc="last")
        piv.index = pd.to_datetime(piv.index)
        rev = piv.get("Revenue")
        out = pd.DataFrame(index=piv.index)
        out["eps"] = piv.get("EPS")

        def ratio(col):
            if rev is None or col not in piv.columns:
                return float("nan")
            return piv[col] / rev.where(rev != 0) * 100.0

        out["gross_margin"] = ratio("GrossProfit")
        out["operating_margin"] = ratio("OperatingIncome")
        out["net_margin"] = ratio("IncomeAfterTaxes") if "IncomeAfterTaxes" in piv.columns else ratio("NetIncome")
        return schema.normalize(out, schema.FIN_COLS)


def _level_lower_bound(level: str) -> int:
    """'400,001-600,000' → 400001；'more than 1,000,001' → 1000001；'total' / '合計' → -1。"""
    s = str(level).lower().replace(",", "").strip()
    if "total" in s or "合計" in s:
        return -1
    if s in ("差異數調整", "adjustment"):
        return -2
    nums = re.findall(r"\d+", s)
    if not nums:
        return -2
    return int(nums[0])


# ───────────────────────────── 官方端點 ─────────────────────────────

class OfficialClient:
    """證交所 / 櫃買中心免金鑰端點。上市用 TWSE，上櫃用 TPEx。"""

    def __init__(self, session=None, timeout: float = 20.0, gap: float = 1.2):
        self.session = _session(session)
        self.timeout = timeout
        self.gap = gap

    def _sleep(self):
        if self.gap:
            time.sleep(self.gap)

    def price_twse(self, stock_id: str, start, end) -> pd.DataFrame:
        rows = []
        for m in _month_starts(_as_date(start), _as_date(end)):
            js = _get_json(self.session, TWSE_STOCK_DAY,
                           params={"response": "json", "date": m.strftime("%Y%m%d"), "stockNo": stock_id},
                           timeout=self.timeout)
            self._sleep()
            if js.get("stat") not in ("OK", None) or not js.get("data"):
                continue
            rows.extend(_parse_daily_table(js.get("fields") or [], js["data"], volume_in_lots=False))
        return _rows_to_price(rows, start, end)

    def price_tpex(self, stock_id: str, start, end) -> pd.DataFrame:
        rows = []
        for m in _month_starts(_as_date(start), _as_date(end)):
            js = _get_json(self.session, TPEX_STOCK_DAY,
                           params={"code": stock_id, "date": m.strftime("%Y/%m/%d"), "response": "json"},
                           timeout=self.timeout)
            self._sleep()
            tables = js.get("tables") or []
            for t in tables:
                if t.get("data"):
                    # 櫃買個股日成交的量單位是「張」(仟股)
                    rows.extend(_parse_daily_table(t.get("fields") or [], t["data"], volume_in_lots=True))
        return _rows_to_price(rows, start, end)

    def institutional_market_day(self, day) -> pd.DataFrame:
        """證交所 T86：某一天全體上市股票三大法人買賣超。回傳 index=代號。"""
        d = _as_date(day)
        js = _get_json(self.session, TWSE_T86,
                       params={"response": "json", "date": d.strftime("%Y%m%d"), "selectType": "ALLBUT0999"},
                       timeout=self.timeout)
        self._sleep()
        if js.get("stat") != "OK" or not js.get("data"):
            return pd.DataFrame(columns=schema.INST_COLS)
        fields = js["fields"]
        df = pd.DataFrame(js["data"], columns=fields)

        def pick(*keys):
            for f in fields:
                if all(k in f for k in keys):
                    return df[f].map(to_number)
            return pd.Series(0.0, index=df.index)

        out = pd.DataFrame({
            "foreign": pick("外陸資買賣超", "不含"),
            "trust": pick("投信買賣超"),
            "dealer": pick("自營商買賣超股數") if any(f == "自營商買賣超股數" for f in fields) else pick("自營商買賣超"),
            "total": pick("三大法人買賣超"),
        })
        out.index = df[fields[0]].astype(str).str.strip()
        out.index.name = "code"
        return out


def _parse_daily_table(fields: list[str], data: list[list], volume_in_lots: bool) -> list[tuple]:
    def idx(*cands, default=None):
        for i, f in enumerate(fields):
            f2 = f.replace(" ", "")
            if any(c in f2 for c in cands):
                return i
        return default

    i_date = idx("日期", default=0)
    i_vol = idx("成交股數", "成交張數", "成交仟股", default=1)
    i_open = idx("開盤", default=3)
    i_high = idx("最高", default=4)
    i_low = idx("最低", default=5)
    i_close = idx("收盤", default=6)
    mult = 1000.0 if volume_in_lots else 1.0
    out = []
    for r in data:
        try:
            d = roc_to_date(r[i_date])
        except (ValueError, IndexError):
            continue
        out.append((d, to_number(r[i_open]), to_number(r[i_high]), to_number(r[i_low]),
                    to_number(r[i_close]), to_number(r[i_vol]) * mult))
    return out


def _rows_to_price(rows, start, end) -> pd.DataFrame:
    if not rows:
        return schema.empty(schema.PRICE_COLS)
    df = pd.DataFrame(rows, columns=["date"] + schema.PRICE_COLS).set_index("date")
    df = df.dropna(subset=["close"])
    df = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
    return schema.normalize(df, schema.PRICE_COLS)
