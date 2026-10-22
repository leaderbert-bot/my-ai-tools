"""Tkinter 桌面介面（選用）。功能與網頁儀表板相同，共用 ``AppService``。

Windows 的 Python 內建 Tkinter，雙擊 ``啟動桌面版.bat`` 即可。
選股在背景執行緒跑，視窗不會卡住。
"""

from __future__ import annotations

import threading

from .service import AppService


def run(service: AppService):  # pragma: no cover - 需要圖形環境，雲端測試環境沒有 Tk
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    from . import strategies

    root = tk.Tk()
    root.title("台股動能‧財報‧籌碼綜合分析")
    root.geometry("1280x760")

    st = service.status()
    top = ttk.Frame(root, padding=8)
    top.pack(fill="x")
    ttk.Label(top, text=st["mode"] + ("｜已連結台股雷達" if st["radar_connected"] else "")).pack(side="left")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8, pady=8)

    # ───────── 個股查詢 ─────────
    f1 = ttk.Frame(nb, padding=8)
    nb.add(f1, text="個股查詢")
    bar = ttk.Frame(f1)
    bar.pack(fill="x")
    ttk.Label(bar, text="股票代號").pack(side="left")
    code_var = tk.StringVar(value="2330")
    ttk.Entry(bar, textvariable=code_var, width=10).pack(side="left", padx=4)
    strat_keys = list(strategies.REGISTRY)
    strat_labels = [strategies.REGISTRY[k].label for k in strat_keys]
    s1 = ttk.Combobox(bar, values=strat_labels, state="readonly", width=24)
    s1.current(0)
    s1.pack(side="left", padx=4)
    out = tk.Text(f1, wrap="none", font=("Consolas", 10))
    out.pack(fill="both", expand=True, pady=6)

    def do_query(*_):
        code = code_var.get().strip()
        key = strat_keys[s1.current()]

        def work():
            try:
                d = service.stock_detail(code, key)
            except Exception as e:
                root.after(0, lambda: messagebox.showerror("錯誤", str(e)))
                return
            root.after(0, lambda: show_stock(d))

        threading.Thread(target=work, daemon=True).start()

    def show_stock(d):
        out.delete("1.0", "end")
        if not d.get("ok"):
            out.insert("end", d.get("message", "查無資料"))
            return
        s = d["snapshot"]
        lines = [f"{d['code']} {d['name']}  收盤 {s['close']}  ({d['date']})",
                 "資料來源：" + "｜".join(f"{k}:{v}" for k, v in d["sources"].items()), "",
                 "今日策略檢查：" + "  ".join(("✔" if c["hit"] else "✗") + c["label"] for c in d["checks"].values()), ""]
        for k, v in s.items():
            lines.append(f"  {strategies.COLUMN_LABELS.get(k, k):<12} {v if v is None else round(v, 2)}")
        b = d["backtest"]
        lines += ["", f"回測（{strategies.get(d['strategy']).label}）：交易 {b['trades']} 次｜勝率 {b['win_rate']}%｜"
                      f"總報酬 {b['total_return']}%｜MDD {b['mdd']}%｜買進持有 {b['buy_hold_return']}%", "",
                  "近 10 筆交易："]
        for t in d["trades"][-10:]:
            lines.append(f"  {t['date']} {t['entry_price']} → {t['exit_date']} {t['exit_price']}  "
                         f"{t['exit_reason']}  {t['return_pct']}%")
        out.insert("end", "\n".join(lines))

    ttk.Button(bar, text="查詢", command=do_query).pack(side="left", padx=4)
    root.bind("<Return>", do_query)

    # ───────── 策略選股 ─────────
    f2 = ttk.Frame(nb, padding=8)
    nb.add(f2, text="策略選股")
    bar2 = ttk.Frame(f2)
    bar2.pack(fill="x")
    s2 = ttk.Combobox(bar2, values=strat_labels, state="readonly", width=24)
    s2.current(0)
    s2.pack(side="left", padx=4)
    unis = list(st["universes"])
    u2 = ttk.Combobox(bar2, values=[f"{u}（{st['universes'][u]}）" for u in unis], state="readonly", width=28)
    u2.current(0)
    u2.pack(side="left", padx=4)
    ttk.Label(bar2, text="自訂代號").pack(side="left")
    codes_var = tk.StringVar()
    ttk.Entry(bar2, textvariable=codes_var, width=30).pack(side="left", padx=4)
    status = tk.StringVar(value="")
    tree = ttk.Treeview(f2, show="headings")
    tree.pack(fill="both", expand=True, pady=6)
    ttk.Label(f2, textvariable=status).pack(anchor="w")

    def do_screen():
        key = strat_keys[s2.current()]
        uni = unis[u2.current()]
        status.set("選股中…")

        def work():
            try:
                r = service.run_screen(key, uni, codes_var.get())
            except Exception as e:
                root.after(0, lambda: status.set(f"錯誤：{e}"))
                return
            root.after(0, lambda: show_screen(r))

        threading.Thread(target=work, daemon=True).start()

    def show_screen(r):
        cols = r["columns"]
        tree["columns"] = cols
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=90, anchor="e")
        tree.delete(*tree.get_children())
        for row in r["rows"]:
            tree.insert("", "end", values=[("" if row[c] is None else row[c]) for c in cols])
        s = r["summary"]
        status.set(f"掃描 {s['scanned']} 檔，今日符合 {s['matched']} 檔｜回測勝率 {s['win_rate']}%｜"
                   f"等權組合報酬 {s['portfolio_return']}%｜MDD {s['portfolio_mdd']}%")

    def do_export(fmt):
        if service.last_result is None:
            messagebox.showinfo("提示", "請先執行選股")
            return
        data, name = service.export_last(fmt)
        path = filedialog.asksaveasfilename(initialfile=name, defaultextension="." + fmt)
        if path:
            with open(path, "wb") as fh:
                fh.write(data)
            status.set(f"已匯出：{path}")

    ttk.Button(bar2, text="▶ 一鍵選股", command=do_screen).pack(side="left", padx=4)
    ttk.Button(bar2, text="匯出 Excel", command=lambda: do_export("xlsx")).pack(side="left", padx=2)
    ttk.Button(bar2, text="匯出 CSV", command=lambda: do_export("csv")).pack(side="left", padx=2)

    root.mainloop()
