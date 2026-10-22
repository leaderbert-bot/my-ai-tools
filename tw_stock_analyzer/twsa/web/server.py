"""本地網頁儀表板：只用 Python 標準庫的 http.server，不需要 Flask。

只綁 127.0.0.1（別台電腦連不到），預設埠 8900（台股雷達用 8899，兩個可以同時開）。

API（全部 GET，參數放在網址上）：
    /api/status                      系統狀態、台股雷達連線狀態、可選的選股範圍
    /api/strategies                  策略清單與參數
    /api/stock?code=2330&strategy=   個股查詢（K 線、法人、營收、財報、策略檢查、回測）
    /api/screen?strategy=&universe=&codes=&lookback=   一鍵選股（策略參數用 p_<key>，回測參數用 bt_<key>）
    /api/progress                    選股進度
    /api/export?fmt=xlsx|csv         匯出最近一次選股結果
"""

from __future__ import annotations

import json
import threading
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from ..service import AppService

INDEX_HTML = Path(__file__).with_name("index.html")


def _split_params(q: dict) -> tuple[dict, dict]:
    p = {k[2:]: v for k, v in q.items() if k.startswith("p_")}
    bt = {k[3:]: v for k, v in q.items() if k.startswith("bt_")}
    return p, bt


def make_handler(service: AppService):
    class Handler(BaseHTTPRequestHandler):
        server_version = "TWSA/1.0"

        def log_message(self, fmt, *args):  # 安靜一點，只印錯誤
            pass

        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def do_GET(self):  # noqa: N802
            url = urlparse(self.path)
            q = {k: v[-1] for k, v in parse_qs(url.query).items()}
            try:
                if url.path in ("/", "/index.html"):
                    self._send(200, INDEX_HTML.read_bytes(), "text/html; charset=utf-8")
                elif url.path == "/api/status":
                    self._json(service.status())
                elif url.path == "/api/strategies":
                    self._json(service.strategy_list())
                elif url.path == "/api/progress":
                    self._json(service.progress)
                elif url.path == "/api/stock":
                    if not q.get("code"):
                        return self._json({"ok": False, "message": "請輸入股票代號"}, 400)
                    p, bt = _split_params(q)
                    self._json(service.stock_detail(q["code"], q.get("strategy", "ma_bull"), p, bt))
                elif url.path == "/api/screen":
                    p, bt = _split_params(q)
                    self._json(service.run_screen(q.get("strategy", "ma_bull"), q.get("universe"),
                                                  q.get("codes"), p, bt, int(q.get("lookback", 0) or 0)))
                elif url.path == "/api/export":
                    fmt = q.get("fmt", "xlsx").lower()
                    data, name = service.export_last(fmt)
                    ctype = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                             if fmt == "xlsx" else "text/csv; charset=utf-8")
                    self._send(200, data, ctype, {
                        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})
                else:
                    self._json({"ok": False, "message": "not found"}, 404)
            except KeyError as e:
                self._json({"ok": False, "message": str(e)}, 400)
            except RuntimeError as e:
                self._json({"ok": False, "message": str(e)}, 409)
            except Exception as e:  # 不讓單一請求把伺服器弄掛
                traceback.print_exc()
                self._json({"ok": False, "message": f"{type(e).__name__}: {e}"},
                           HTTPStatus.INTERNAL_SERVER_ERROR)

    return Handler


def create_server(service: AppService, host: str = "127.0.0.1", port: int = 8900) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), make_handler(service))
    httpd.daemon_threads = True
    return httpd


def serve(service: AppService, port: int | None = None, open_browser: bool = True):
    port = port or service.settings.port
    httpd = create_server(service, port=port)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"台股綜合分析儀表板已啟動：{url}（關掉這個視窗就會停止）")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
