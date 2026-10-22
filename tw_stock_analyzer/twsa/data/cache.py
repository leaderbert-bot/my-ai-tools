"""簡單的 CSV 檔案快取：data/cache/<種類>/<代號>.csv。

網路抓回來的資料存一份，下次同一天內直接讀檔；收盤後（15:00 以後）才會認定「今天的快取」
包含當日行情 —— 跟台股雷達「快取用絕對時點判斷」同一個原則。
"""

from __future__ import annotations

from datetime import datetime, time as dtime
from pathlib import Path

import pandas as pd

CLOSE_READY = dtime(15, 0)


class CsvCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def path(self, kind: str, code: str) -> Path:
        return self.root / kind / f"{code}.csv"

    def load(self, kind: str, code: str) -> pd.DataFrame | None:
        p = self.path(kind, code)
        if not p.is_file():
            return None
        try:
            df = pd.read_csv(p, index_col=0, parse_dates=True)
        except (OSError, ValueError, pd.errors.ParserError):
            return None
        df.index.name = "date"
        return df

    def save(self, kind: str, code: str, df: pd.DataFrame) -> None:
        p = self.path(kind, code)
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(p, encoding="utf-8")

    def is_fresh(self, kind: str, code: str, now: datetime | None = None, max_age_hours: float = 6.0) -> bool:
        p = self.path(kind, code)
        if not p.is_file():
            return False
        now = now or datetime.now()
        mtime = datetime.fromtimestamp(p.stat().st_mtime)
        if (now - mtime).total_seconds() > max_age_hours * 3600:
            return False
        if kind == "price" and now.time() >= CLOSE_READY:
            # 收盤後只採信 15:00 之後寫的快取，避免中午抓的檔案冒充當日收盤
            return mtime >= datetime.combine(now.date(), CLOSE_READY)
        return True
