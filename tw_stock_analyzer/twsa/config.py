"""設定：專案路徑、台股雷達資料夾、API 金鑰與網路參數。

設定來源優先序（後者覆蓋前者）：
    1. 程式內建預設值
    2. 專案根目錄的 ``twsa_settings.json``（可選）
    3. 環境變數 ``TWSA_RADAR_DIR``、``FINMIND_TOKEN``、``TWSA_DATA_DIR``
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 使用者原本「台股雷達」所在位置（Windows 本機）。不存在時自動略過。
DEFAULT_RADAR_DIRS = [
    r"C:\Users\leade\Desktop\Dropbox\00money",
    str(Path.home() / "Desktop" / "Dropbox" / "00money"),
    str(Path.home() / "Dropbox" / "00money"),
]


@dataclass
class Settings:
    radar_dir: str | None = None          # 台股雷達資料夾（內含 data/ 子資料夾）
    data_dir: str = str(PROJECT_ROOT / "data")   # 本系統自己的快取與匯出位置
    finmind_token: str | None = None
    request_timeout: float = 20.0
    request_gap: float = 1.2              # 連續請求間隔秒數，避免被交易所鎖 IP
    use_network: bool = True
    demo: bool = False                    # True = 一律使用模擬資料（離線展示用）
    port: int = 8900                      # 台股雷達用 8899，這裡錯開
    extra: dict = field(default_factory=dict)

    @property
    def cache_dir(self) -> Path:
        return Path(self.data_dir) / "cache"

    @property
    def export_dir(self) -> Path:
        return Path(self.data_dir) / "exports"

    @property
    def radar_data_dir(self) -> Path | None:
        if not self.radar_dir:
            return None
        p = Path(self.radar_dir)
        return p / "data" if (p / "data").is_dir() else p

    def to_dict(self) -> dict:
        d = asdict(self)
        if d.get("finmind_token"):
            d["finmind_token"] = "***"
        return d


def _detect_radar_dir() -> str | None:
    for cand in DEFAULT_RADAR_DIRS:
        if cand and Path(cand).is_dir():
            return cand
    return None


def load_settings(path: str | os.PathLike | None = None, **overrides) -> Settings:
    s = Settings()
    cfg_path = Path(path) if path else PROJECT_ROOT / "twsa_settings.json"
    if cfg_path.is_file():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for k, v in data.items():
            if hasattr(s, k):
                setattr(s, k, v)
            else:
                s.extra[k] = v

    env_radar = os.environ.get("TWSA_RADAR_DIR")
    if env_radar:
        s.radar_dir = env_radar
    env_data = os.environ.get("TWSA_DATA_DIR")
    if env_data:
        s.data_dir = env_data
    env_tok = os.environ.get("FINMIND_TOKEN")
    if env_tok:
        s.finmind_token = env_tok

    for k, v in overrides.items():
        if v is not None and hasattr(s, k):
            setattr(s, k, v)

    if s.radar_dir is None and not s.demo:
        s.radar_dir = _detect_radar_dir()
    return s
