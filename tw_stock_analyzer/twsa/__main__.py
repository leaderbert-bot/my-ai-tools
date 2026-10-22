"""命令列入口：``python -m twsa <子指令>``。

    python -m twsa web                 開本地網頁儀表板（預設）
    python -m twsa gui                 開 Tkinter 桌面版
    python -m twsa stock 2330          終端機印出單一個股
    python -m twsa screen --strategy combo --universe 自選股 --export xlsx
    python -m twsa list                列出策略與選股範圍

共用選項：--demo（模擬資料，離線展示）、--radar-dir（台股雷達資料夾）、--offline（不連網）
"""

from __future__ import annotations

import argparse
import sys

from . import strategies
from .config import load_settings
from .service import AppService


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="twsa", description="台股動能、基本面財報與籌碼分佈綜合分析系統")
    ap.add_argument("--demo", action="store_true", help="使用模擬資料（不連網、不讀台股雷達）")
    ap.add_argument("--radar-dir", help="台股雷達資料夾，例如 C:\\Users\\leade\\Desktop\\Dropbox\\00money")
    ap.add_argument("--offline", action="store_true", help="不連網，只用台股雷達本機資料與快取")
    ap.add_argument("--config", help="設定檔路徑（預設 twsa_settings.json）")
    sub = ap.add_subparsers(dest="cmd")

    w = sub.add_parser("web", help="開本地網頁儀表板")
    w.add_argument("--port", type=int)
    w.add_argument("--no-open", action="store_true", help="不要自動打開瀏覽器")
    sub.add_parser("gui", help="開 Tkinter 桌面版")
    sub.add_parser("list", help="列出策略與選股範圍")

    s = sub.add_parser("stock", help="單一個股分析")
    s.add_argument("code")
    s.add_argument("--strategy", default="ma_bull")

    sc = sub.add_parser("screen", help="一鍵選股 + 回測")
    sc.add_argument("--strategy", default="combo", choices=list(strategies.REGISTRY))
    sc.add_argument("--universe", help="選股範圍名稱（見 list）")
    sc.add_argument("--codes", help="自訂代號，逗號分隔")
    sc.add_argument("--lookback", type=int, default=0)
    sc.add_argument("--hold-days", type=int, default=20)
    sc.add_argument("--stop-loss", type=float, default=8.0)
    sc.add_argument("--export", choices=["xlsx", "csv"], help="匯出到 data/exports/")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(args.config, demo=args.demo or None, radar_dir=args.radar_dir,
                             use_network=False if args.offline else None)
    svc = AppService(settings)
    cmd = args.cmd or "web"

    if cmd == "web":
        from .web.server import serve
        serve(svc, port=getattr(args, "port", None), open_browser=not getattr(args, "no_open", False))
    elif cmd == "gui":
        from .gui_tk import run
        run(svc)
    elif cmd == "list":
        print("策略：")
        for k, st in strategies.REGISTRY.items():
            print(f"  {k:<22} [{st.category}] {st.label} —— {st.description}")
        print("\n選股範圍：")
        for k, n in svc.status()["universes"].items():
            print(f"  {k}（{n} 檔）")
    elif cmd == "stock":
        d = svc.stock_detail(args.code, args.strategy)
        if not d.get("ok"):
            print(d.get("message"))
            return 1
        print(f"{d['code']} {d['name']}  收盤 {d['snapshot']['close']}  {d['date']}")
        print("資料來源：", d["sources"])
        for c in d["checks"].values():
            print(f"  {'✔' if c['hit'] else '✗'} {c['label']}")
        b = d["backtest"]
        print(f"回測 {strategies.get(args.strategy).label}：交易 {b['trades']}｜勝率 {b['win_rate']}%｜"
              f"總報酬 {b['total_return']}%｜MDD {b['mdd']}%")
    elif cmd == "screen":
        r = svc.run_screen(args.strategy, args.universe, args.codes,
                           bt={"hold_days": args.hold_days, "stop_loss": args.stop_loss}, lookback=args.lookback)
        s = r["summary"]
        print(f"[{r['strategy_label']}] 掃描 {s['scanned']} 檔，今日符合 {s['matched']} 檔；"
              f"回測勝率 {s['win_rate']}%，等權組合報酬 {s['portfolio_return']}%，MDD {s['portfolio_mdd']}%")
        for row in r["rows"]:
            if row["符合"]:
                print(f"  {row['代號']} {row['名稱']:<8} 收 {row['收盤']:>8}  勝率 {row['回測勝率%']}%  MDD {row['策略MDD%']}%")
        for e in r["errors"]:
            print("  略過", e)
        if args.export:
            print("已匯出：", svc.export_last_to_disk(args.export))
    return 0


if __name__ == "__main__":
    sys.exit(main())
