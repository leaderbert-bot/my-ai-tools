"""讀取原本「台股雷達」(tw_radar.py) 存在本機 ``data/`` 的資料。

台股雷達已經每天收盤後把全市場行情、三大法人、月營收累積在 Dropbox 的
``00money/data/`` 裡。本系統直接讀那份資料，不用再向交易所重抓一次。

對應的檔案（皆為台股雷達自動產生）：

======================  ===================================  ===================
檔案                     內容                                  本系統用途
======================  ===================================  ===================
px_history.json         全市場每日開高低收量                    price
kline/<代號>-<年月>.json  單檔補抓的日K [[日期,開,高,低,收,量]]     price（補洞）
inst_hist.json          三大法人買賣超歷史                       institutional
history.json            月營收歷史                              revenue
groups.csv              你的族群分類（產業,公司代號,公司名稱）     選股範圍「我的族群」
watchlist.json          自選股 ["2330", ...]                    選股範圍「自選股」
stock_names.json        代號 → 名稱                             顯示名稱
markets.json            代號 → 上市/上櫃                         決定官方端點
======================  ===================================  ===================

台股雷達的 JSON 有兩種常見排法，這裡都會自動辨識：

* **以代號為主**：``{"2330": [["2026-10-01", 開, 高, 低, 收, 量], ...]}``
  （``kline/*.json``、``lend_hist.json`` 都是這種）
* **以日期為主**：``{"2026-10-01": {"2330": [開, 高, 低, 收, 量], ...}}``

每一列可以是 list（依欄位順序）或 dict（依欄名，中英文都認）。如果你的檔案欄位順序
跟預設不同，在 ``twsa_settings.json`` 的 ``radar_columns`` 指定即可，例如：

    {"radar_columns": {"inst": ["foreign", "trust", "dealer", "total"]}}
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pandas as pd

from . import schema

_DATE_RE = re.compile(r"^(\d{4})[-/]?(\d{2})[-/]?(\d{2})$")
_YM_RE = re.compile(r"^(\d{4})[-/]?(\d{2})$")
_ROC_YM_RE = re.compile(r"^(\d{2,3})[-/]?(\d{2})$")

DEFAULT_COLUMNS = {
    "price": ["open", "high", "low", "close", "volume"],
    "inst": ["foreign", "trust", "dealer", "total"],
    "revenue": ["revenue"],
}

_ALIASES = {
    "open": ("open", "o", "開盤", "開盤價", "開"),
    "high": ("high", "h", "max", "最高", "最高價", "高"),
    "low": ("low", "l", "min", "最低", "最低價", "低"),
    "close": ("close", "c", "z", "收盤", "收盤價", "收"),
    "volume": ("volume", "v", "vol", "成交股數", "成交量", "量"),
    "foreign": ("foreign", "f", "fi", "外資", "外陸資", "外資買賣超"),
    "trust": ("trust", "it", "t_", "投信", "投信買賣超"),
    "dealer": ("dealer", "d", "dl", "自營", "自營商", "自營商買賣超"),
    "total": ("total", "sum", "all", "合計", "三大法人", "三大法人買賣超"),
    "revenue": ("revenue", "rev", "r", "營收", "當月營收", "營業收入"),
}

_WRAPPER_KEYS = ("data", "px", "rows", "hist", "history", "by_code", "codes", "items")


def parse_date_key(k) -> pd.Timestamp | None:
    m = _DATE_RE.match(str(k).strip())
    if not m:
        return None
    try:
        return pd.Timestamp(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None


def parse_month_key(k) -> pd.Timestamp | None:
    """'2026-08' / '202608' / 民國 '11508' / '115/08' → 2026-08-01。"""
    s = str(k).strip()
    m = _YM_RE.match(s)
    if m and 1900 < int(m[1]) < 2200 and 1 <= int(m[2]) <= 12:
        return pd.Timestamp(int(m[1]), int(m[2]), 1)
    m = _ROC_YM_RE.match(s)
    if m and 1 <= int(m[2]) <= 12 and 50 <= int(m[1]) <= 300:
        return pd.Timestamp(int(m[1]) + 1911, int(m[2]), 1)
    return None


def _unwrap(raw):
    """台股雷達有時會把資料包在 {"data": {...}, "meta": ...} 這種外殼裡。"""
    for _ in range(3):
        if not isinstance(raw, dict) or not raw:
            return raw
        keys = list(raw.keys())
        if any(parse_date_key(k) or _looks_like_code(k) for k in keys[:20]):
            return raw
        for wk in _WRAPPER_KEYS:
            if wk in raw and isinstance(raw[wk], dict):
                raw = raw[wk]
                break
        else:
            dicts = [v for v in raw.values() if isinstance(v, dict)]
            if not dicts:
                return raw
            raw = max(dicts, key=len)
    return raw


def _looks_like_code(k) -> bool:
    return bool(re.match(r"^[0-9A-Z]{4,6}[A-Z]?$", str(k)))


def _row_values(row, cols: list[str]) -> dict:
    if isinstance(row, dict):
        lower = {str(k).lower(): v for k, v in row.items()}
        out = {}
        for c in cols:
            for a in _ALIASES.get(c, (c,)):
                if a.lower() in lower:
                    out[c] = lower[a.lower()]
                    break
        return out
    if isinstance(row, (list, tuple)):
        return {c: row[i] for i, c in enumerate(cols) if i < len(row)}
    if isinstance(row, (int, float)) and cols:
        return {cols[0]: row}
    return {}


def _num(x) -> float:
    if x is None:
        return float("nan")
    try:
        return float(str(x).replace(",", "")) if not isinstance(x, (int, float)) else float(x)
    except ValueError:
        return float("nan")


def extract_series(raw, code: str, cols: list[str], key_parser=parse_date_key) -> pd.DataFrame:
    """從任一種排法的 JSON 抽出單一代號的時間序列。"""
    raw = _unwrap(raw)
    records: list[tuple[pd.Timestamp, dict]] = []
    if isinstance(raw, dict) and raw:
        sample = list(raw.keys())[:30]
        date_major = sum(1 for k in sample if key_parser(k) is not None) > len(sample) / 2
        if date_major:
            for k, by_code in raw.items():
                ts = key_parser(k)
                if ts is None or not isinstance(by_code, dict) or code not in by_code:
                    continue
                records.append((ts, _row_values(by_code[code], cols)))
        else:
            node = raw.get(code)
            if isinstance(node, list):
                for row in node:
                    if isinstance(row, (list, tuple)) and row:
                        ts = key_parser(row[0])
                        if ts is not None:
                            records.append((ts, _row_values(list(row[1:]), cols)))
                    elif isinstance(row, dict):
                        dk = next((row[k] for k in ("date", "d", "日期", "ym", "month") if k in row), None)
                        ts = key_parser(dk) if dk is not None else None
                        if ts is not None:
                            records.append((ts, _row_values(row, cols)))
            elif isinstance(node, dict):
                for k, row in node.items():
                    ts = key_parser(k)
                    if ts is not None:
                        records.append((ts, _row_values(row, cols)))
    if not records:
        return schema.empty(cols)
    df = pd.DataFrame([{c: _num(v.get(c)) for c in cols} for _, v in records],
                      index=pd.DatetimeIndex([t for t, _ in records], name="date"))
    return df


class RadarSource:
    """台股雷達本機資料來源。大檔只讀一次並依檔案修改時間快取在記憶體。"""

    _cache: dict[str, tuple[float, object]] = {}

    def __init__(self, data_dir: str | Path, columns: dict | None = None):
        self.data_dir = Path(data_dir)
        self.columns = {**DEFAULT_COLUMNS, **(columns or {})}

    # ---------- 共用 ----------
    def available(self) -> bool:
        return self.data_dir.is_dir()

    def _load_json(self, name: str):
        p = self.data_dir / name
        if not p.is_file():
            return None
        key = str(p)
        mtime = p.stat().st_mtime
        hit = self._cache.get(key)
        if hit and hit[0] == mtime:
            return hit[1]
        try:
            with p.open(encoding="utf-8") as f:
                obj = json.load(f)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        self._cache[key] = (mtime, obj)
        return obj

    def files(self) -> dict[str, bool]:
        names = ["px_history.json", "inst_hist.json", "history.json", "groups.csv",
                 "watchlist.json", "stock_names.json", "markets.json", "kline"]
        return {n: (self.data_dir / n).exists() for n in names}

    # ---------- 行情 ----------
    def price(self, code: str) -> pd.DataFrame:
        cols = self.columns["price"]
        parts = []
        kdir = self.data_dir / "kline"
        if kdir.is_dir():
            for f in sorted(kdir.glob(f"{code}-*.json")):
                try:
                    rows = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                parts.append(extract_series({code: rows}, code, cols))
        px = self._load_json("px_history.json")
        if px is not None:
            # px_history 放最後：日期重複時 normalize(keep=last) 會留下它
            parts.append(extract_series(px, code, cols))
        parts = [p for p in parts if not p.empty]
        if not parts:
            return schema.empty(schema.PRICE_COLS)
        df = pd.concat(parts)
        df = schema.normalize(df, schema.PRICE_COLS)
        # 與台股雷達「資料檢核」相同的物理檢查：最低 ≤ 開/收 ≤ 最高，價格 > 0
        ok = (df["close"] > 0) & (df["low"] <= df[["open", "close"]].min(axis=1) + 1e-9) & \
             (df["high"] >= df[["open", "close"]].max(axis=1) - 1e-9)
        return df[ok.fillna(False)]

    # ---------- 三大法人 ----------
    def institutional(self, code: str) -> pd.DataFrame:
        raw = self._load_json("inst_hist.json")
        if raw is None:
            return schema.empty(schema.INST_COLS)
        df = extract_series(raw, code, self.columns["inst"])
        if df.empty:
            return schema.empty(schema.INST_COLS)
        for c in ("foreign", "trust", "dealer"):
            if c not in df.columns:
                df[c] = 0.0
        if "total" not in df.columns or df["total"].isna().all():
            df["total"] = df[["foreign", "trust", "dealer"]].fillna(0).sum(axis=1)
        else:
            df["total"] = df["total"].fillna(df[["foreign", "trust", "dealer"]].fillna(0).sum(axis=1))
        return schema.normalize(df, schema.INST_COLS)

    # ---------- 月營收 ----------
    def revenue(self, code: str) -> pd.DataFrame:
        raw = self._load_json("history.json")
        if raw is None:
            return schema.empty(schema.REVENUE_COLS)
        df = extract_series(raw, code, self.columns["revenue"], key_parser=parse_month_key)
        if df.empty:
            return schema.empty(schema.REVENUE_COLS)
        return schema.add_revenue_growth(df[["revenue"]])

    # ---------- 名單 ----------
    def groups(self) -> dict[str, list[str]]:
        p = self.data_dir / "groups.csv"
        out: dict[str, list[str]] = {}
        if not p.is_file():
            return out
        for enc in ("utf-8-sig", "cp950", "big5"):
            try:
                text = p.read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            return out
        for row in csv.DictReader(text.splitlines()):
            g = (row.get("產業") or row.get("族群") or "").strip()
            c = (row.get("公司代號") or row.get("代號") or "").strip()
            if g and c and c not in out.setdefault(g, []):
                out[g].append(c)
        return out

    def group_names(self) -> dict[str, str]:
        """groups.csv 裡的名稱欄（去掉使用者自己加的 * 記號）。"""
        p = self.data_dir / "groups.csv"
        names: dict[str, str] = {}
        if not p.is_file():
            return names
        try:
            text = p.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            text = p.read_text(encoding="cp950", errors="ignore")
        for row in csv.DictReader(text.splitlines()):
            c = (row.get("公司代號") or "").strip()
            n = (row.get("公司名稱") or "").strip().rstrip("*")
            if c and n:
                names[c] = n
        return names

    def watchlist(self) -> list[str]:
        raw = self._load_json("watchlist.json")
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
        if isinstance(raw, dict):
            for k in ("codes", "watchlist", "list"):
                if isinstance(raw.get(k), list):
                    return [str(x) for x in raw[k]]
        return []

    def names(self) -> dict[str, str]:
        out = dict(self.group_names())
        raw = self._load_json("stock_names.json")
        raw = _unwrap(raw) if isinstance(raw, dict) else raw
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, str):
                    out[str(k)] = v
                elif isinstance(v, dict):
                    n = v.get("name") or v.get("名稱") or v.get("n")
                    if n:
                        out[str(k)] = str(n)
                elif isinstance(v, (list, tuple)) and v and isinstance(v[0], str):
                    out[str(k)] = v[0]
        return out

    def markets(self) -> dict[str, str]:
        raw = self._load_json("markets.json")
        out = {}
        if isinstance(raw, dict):
            for k, v in _unwrap(raw).items() if isinstance(_unwrap(raw), dict) else []:
                s = str(v).lower()
                out[str(k)] = "otc" if ("otc" in s or "櫃" in s or s == "o") else "sii"
        return out
