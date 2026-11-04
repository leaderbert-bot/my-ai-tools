#!/usr/bin/env python3
"""
加碼策略回測：同一套進出場規則下，比較五種部位管理方式。

  A  不加碼        一次進滿倉
  B  SOP金字塔     試單25% → 回檔不破轉強時加 30/25/20%，加碼後停損上移到打平，加碼單有獨立停損
  B2 SOP加碼       同 B 的加碼時機與獨立停損，但整體停損不上移（分離「打平停損」的影響）
  C  追高加碼      連續3根紅K後加碼（多數人的習慣），停損不動
  C2 追高+移停損   同 C，但加碼後停損上移到打平（用來分離「時機」和「停損」兩個因素）
  D  攤平          跌破上一筆進場價 5% 就加

進出場規則（所有變體共用，可改）：
  進場  收盤突破前 20 日最高、站上 20 日線、量 > 20 日均量 1.5 倍（--no-volume 可關掉量的條件）
  停損  前 5 日最低（至少低於進場價 2%）
  出場  整體停損被打到，或收盤跌破 10 日線
  部位  每筆操作風險 = 權益 1%，滿倉金額不超過權益（不開槓桿）
  成交  訊號日隔天開盤成交；停損盤中成交（跳空則以開盤價成交）

用法：
  python3 backtest_pyramid.py                      # 用內建 GOOG 2004-2013 示範資料
  python3 backtest_pyramid.py --csv 2330.csv       # 你自己的 OHLCV CSV（欄位 Date,Open,High,Low,Close,Volume）
  python3 backtest_pyramid.py --symbols 2330.TW,2317.TW,2454.TW   # 本機有網路時用 yfinance 下載
"""
import argparse
import math
import sys

import numpy as np
import pandas as pd

VARIANTS = ["A", "B", "B2", "C", "C2", "D"]
VARIANT_NAME = {
    "A": "A 不加碼（一次滿倉）",
    "B": "B SOP金字塔加碼",
    "B2": "B2 SOP加碼（停損不上移）",
    "C": "C 追高加碼（停損不動）",
    "C2": "C2 追高加碼（停損上移）",
    "D": "D 攤平加碼",
}
ADD_FRACS = [0.30, 0.25, 0.20]  # 試單 25% 之後的三次加碼比例


# ---------------------------------------------------------------- 資料
def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = df.columns[0] if "Date" not in df.columns else "Date"
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    df.columns = [c.strip().title() for c in df.columns]
    need = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        sys.exit(f"CSV 缺少欄位: {missing}")
    return df[need].dropna()


def load_builtin() -> pd.DataFrame:
    import os
    return load_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "GOOG_2004_2013.csv"))


def load_symbol(symbol: str, start: str) -> pd.DataFrame:
    import yfinance as yf
    df = yf.download(symbol, start=start, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.empty:
        sys.exit(f"{symbol} 下載不到資料")
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def add_indicators(df: pd.DataFrame, breakout=20, exit_ma=10) -> pd.DataFrame:
    d = df.copy()
    c, h, l, v = d["Close"], d["High"], d["Low"], d["Volume"]
    d["ma5"] = c.rolling(5).mean()
    d["ma10"] = c.rolling(exit_ma).mean()  # 出場均線（名稱沿用 ma10）
    d["ma20"] = c.rolling(20).mean()
    d["hh20"] = h.rolling(breakout).max().shift(1)  # 突破參考高點
    d["low5"] = l.rolling(5).min().shift(1)
    d["vol20"] = v.rolling(20).mean().shift(1)
    d["dev"] = c / d["ma20"] - 1
    up = (c > c.shift(1)).astype(int)
    d["upcnt"] = up.groupby((up == 0).cumsum()).cumsum()
    d["prev_close"] = c.shift(1)
    return d.dropna()


# ---------------------------------------------------------------- 引擎
class Lot:
    __slots__ = ("price", "shares", "stop", "idx")

    def __init__(self, price, shares, stop, idx):
        self.price, self.shares, self.stop, self.idx = price, shares, stop, idx


def run(d: pd.DataFrame, variant: str, capital=1_000_000, risk=0.01, fee=0.001,
        max_dev=0.15, use_volume=True):
    o, h, l, c = d["Open"].values, d["High"].values, d["Low"].values, d["Close"].values
    ma5, ma10, ma20 = d["ma5"].values, d["ma10"].values, d["ma20"].values
    hh20, low5, vol20, vol = d["hh20"].values, d["low5"].values, d["vol20"].values, d["Volume"].values
    dev, upcnt, pc = d["dev"].values, d["upcnt"].values, d["prev_close"].values
    n = len(d)

    cash = capital
    lots: list[Lot] = []
    equity_curve = np.zeros(n)
    trades = []

    # 進行中的交易狀態
    st = {}
    pending = None  # ("entry"|"add"|"exit", info) 隔天開盤執行

    def pos_shares():
        return sum(x.shares for x in lots)

    def avg_cost():
        s = pos_shares()
        return sum(x.price * x.shares for x in lots) / s if s else 0.0

    def sell(shares, price, i, reason):
        nonlocal cash
        proceeds = shares * price * (1 - fee)
        cash += proceeds
        st["realized"] += proceeds - 0  # 成本在 buy 時已扣
        st["exits"].append((d.index[i].date(), reason, shares, price))

    def buy(shares, price, i, stop, kind):
        nonlocal cash
        cost = shares * price * (1 + fee)
        if shares <= 0 or cost > cash:
            return False
        cash -= cost
        lots.append(Lot(price, shares, stop, i))
        st["adds"].append((d.index[i].date(), kind, shares, price))
        return True

    def close_trade(i):
        pnl = st["realized"] - st["invested"]
        trades.append({
            "entry": st["entry_date"], "exit": d.index[i].date(),
            "pnl": pnl, "R": pnl / st["risk_amt"], "maxR": st["maxR"],
            "n_adds": len(st["adds"]) - 1, "exits": st["exits"], "adds": st["adds"],
        })

    for i in range(1, n):
        # ---------- 1. 執行昨天排好的開盤單
        if pending:
            kind, info = pending
            pending = None
            if kind == "entry":
                fill = o[i]
                stop0 = min(info["stop"], fill * 0.98)
                risk_amt = info["equity"] * risk
                full = math.floor(risk_amt / (fill - stop0))
                full = min(full, math.floor(info["equity"] / (fill * (1 + fee))))  # 不開槓桿
                if full > 0:
                    first = full if variant == "A" else max(1, math.floor(full * 0.25))
                    st = {"entry_date": d.index[i].date(), "risk_amt": risk_amt, "full": full,
                          "whole_stop": stop0, "first_price": fill, "adds": [], "exits": [],
                          "invested": 0.0, "realized": 0.0, "maxR": 0.0,
                          "pullback": False, "pb_low": np.inf, "last_add_idx": i}
                    if buy(first, fill, i, None, "試單"):
                        st["invested"] += first * fill * (1 + fee)
            elif kind == "add" and lots:
                fill = o[i]
                shares = info["shares"]
                if buy(shares, fill, i, info["lot_stop"], f"加碼{len(st['adds'])}"):
                    st["invested"] += shares * fill * (1 + fee)
                    k = len(st["adds"]) - 1
                    if info["raise_stop"]:
                        target = st["first_price"] if k == 1 else avg_cost()
                        st["whole_stop"] = max(st["whole_stop"], target)
                    st["pullback"], st["pb_low"], st["last_add_idx"] = False, np.inf, i
            elif kind == "exit" and lots:
                sell(pos_shares(), o[i], i, "跌破10日線")
                lots.clear()
                close_trade(i)

        # ---------- 2. 盤中停損
        if lots:
            ws = st["whole_stop"]
            if l[i] <= ws:
                px = o[i] if o[i] < ws else ws
                sell(pos_shares(), px, i, "整體停損")
                lots.clear()
                close_trade(i)
            else:
                for lot in list(lots):
                    if lot.stop is not None and l[i] <= lot.stop:
                        px = o[i] if o[i] < lot.stop else lot.stop
                        sell(lot.shares, px, i, "加碼單獨立停損")
                        lots.remove(lot)
                if not lots:
                    close_trade(i)

        # ---------- 3. 收盤後決策
        if lots:
            # 追蹤未實現 R 與回檔
            unreal = (st["realized"] + pos_shares() * c[i]) - st["invested"]
            st["maxR"] = max(st["maxR"], unreal / st["risk_amt"])
            if l[i] <= ma5[i] or c[i] < ma5[i]:
                st["pullback"] = True
            st["pb_low"] = min(st["pb_low"], l[i])

            if c[i] < ma10[i]:
                pending = ("exit", None)
            else:
                k = len(st["adds"])  # 已有幾筆（含試單）
                if variant != "A" and k <= 3 and pos_shares() < st["full"]:
                    last_px = lots[-1].price if lots else st["first_price"]
                    frac = ADD_FRACS[k - 1]
                    shares = min(math.floor(st["full"] * frac), st["full"] - pos_shares())
                    want, lot_stop, raise_stop = False, None, False
                    if variant in ("B", "B2"):
                        new_avg = (avg_cost() * pos_shares() + c[i] * shares) / (pos_shares() + shares)
                        want = (c[i] > last_px and st["pullback"] and c[i] > ma5[i] and c[i] > pc[i]
                                and upcnt[i] < 3 and dev[i] < max_dev and new_avg >= c[i] * 0.95)
                        lot_stop, raise_stop = st["pb_low"] * 0.99, variant == "B"
                    elif variant in ("C", "C2"):
                        want = c[i] > last_px and upcnt[i] >= 3
                        raise_stop = variant == "C2"
                    elif variant == "D":
                        want = c[i] <= last_px * 0.95 and c[i] > st["whole_stop"]
                    if want and shares > 0:
                        pending = ("add", {"shares": shares, "lot_stop": lot_stop, "raise_stop": raise_stop})
        else:
            equity = cash
            sig = c[i] > hh20[i] and c[i] > ma20[i]
            if use_volume:
                sig = sig and vol[i] > 1.5 * vol20[i]
            if sig and i + 1 < n:
                pending = ("entry", {"stop": low5[i], "equity": equity})

        equity_curve[i] = cash + pos_shares() * c[i]

    equity_curve[0] = capital
    # 期末強制平倉以便統計
    if lots:
        sell(pos_shares(), c[-1], n - 1, "期末平倉")
        lots.clear()
        close_trade(n - 1)
        equity_curve[-1] = cash
    return pd.Series(equity_curve, index=d.index), pd.DataFrame(trades)


# ---------------------------------------------------------------- 統計
def stats(eq: pd.Series, tr: pd.DataFrame, capital: float):
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    total = eq.iloc[-1] / capital - 1
    cagr = (eq.iloc[-1] / capital) ** (1 / years) - 1 if years > 0 else np.nan
    dd = eq / eq.cummax() - 1
    out = {"總報酬%": total * 100, "年化%": cagr * 100, "最大回撤%": dd.min() * 100,
           "交易次數": len(tr)}
    if len(tr):
        wins, losses = tr[tr.pnl > 0], tr[tr.pnl <= 0]
        out["勝率%"] = len(wins) / len(tr) * 100
        out["獲利因子"] = wins.pnl.sum() / abs(losses.pnl.sum()) if len(losses) and losses.pnl.sum() != 0 else np.inf
        out["平均R"] = tr.R.mean()
        out["最大單筆虧損R"] = tr.R.min()
        out["平均加碼次數"] = tr.n_adds.mean()
        out["賺變賠筆數"] = int(((tr.maxR >= 0.5) & (tr.pnl < 0)).sum())
        out["賺變賠%"] = out["賺變賠筆數"] / len(tr) * 100
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", help="OHLCV CSV 路徑")
    ap.add_argument("--symbols", help="逗號分隔的 yfinance 代號，例如 2330.TW,2317.TW")
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--capital", type=float, default=1_000_000)
    ap.add_argument("--risk", type=float, default=0.01, help="每筆風險佔權益比例，預設 1%%")
    ap.add_argument("--fee", type=float, default=0.001, help="單邊成本比例。台股約 0.001425+0.0015(稅/2)")
    ap.add_argument("--max-dev", type=float, default=0.15, help="SOP 加碼的乖離上限")
    ap.add_argument("--no-volume", action="store_true", help="進場不要求量能")
    ap.add_argument("--breakout", type=int, default=20, help="突破的回看天數")
    ap.add_argument("--exit-ma", type=int, default=10, help="出場均線天數")
    ap.add_argument("--grid", action="store_true", help="跑參數網格，看哪個變體最穩")
    ap.add_argument("--trades", action="store_true", help="列出每一筆交易")
    args = ap.parse_args()

    datasets = {}
    if args.csv:
        datasets[args.csv] = load_csv(args.csv)
    elif args.symbols:
        for s in args.symbols.split(","):
            datasets[s.strip()] = load_symbol(s.strip(), args.start)
    else:
        datasets["GOOG (內建示範 2004-2013)"] = load_builtin()

    pd.set_option("display.width", 200)
    if args.grid:
        for name, raw in datasets.items():
            print(f"\n===== 參數網格 {name} =====")
            recs = []
            for bo in (20, 40, 55):
                for em in (10, 20):
                    for uv in (True, False):
                        d = add_indicators(raw, bo, em)
                        for v in VARIANTS:
                            eq, tr = run(d, v, args.capital, args.risk, args.fee, args.max_dev, uv)
                            s_ = stats(eq, tr, args.capital)
                            recs.append({"突破": bo, "出場MA": em, "量能": uv, "變體": v,
                                         "總報酬%": s_["總報酬%"], "最大回撤%": s_["最大回撤%"],
                                         "平均R": s_.get("平均R", np.nan), "交易": s_["交易次數"],
                                         "賺變賠%": s_.get("賺變賠%", np.nan)})
            g = pd.DataFrame(recs)
            piv = g.pivot_table(index=["突破", "出場MA", "量能"], columns="變體", values="總報酬%")[VARIANTS]
            print("\n總報酬% （每列一組參數）"); print(piv.round(1).to_string())
            piv_r = g.pivot_table(index=["突破", "出場MA", "量能"], columns="變體", values="平均R")[VARIANTS]
            print("\n平均每筆 R"); print(piv_r.round(2).to_string())
            win = piv.idxmax(axis=1).value_counts()
            print("\n各變體在幾組參數中總報酬最高："); print(win.to_string())
            print("\n各變體平均："); print(g.groupby("變體")[["總報酬%", "最大回撤%", "平均R", "賺變賠%"]].mean().loc[VARIANTS].round(2).to_string())
        return
    for name, raw in datasets.items():
        d = add_indicators(raw, args.breakout, args.exit_ma)
        bh = raw["Close"].iloc[-1] / raw["Close"].iloc[0] - 1
        print(f"\n{'=' * 90}\n{name}  {d.index[0].date()} ~ {d.index[-1].date()}  共 {len(d)} 根  買進持有 {bh * 100:.1f}%\n{'=' * 90}")
        rows = {}
        for v in VARIANTS:
            eq, tr = run(d, v, args.capital, args.risk, args.fee, args.max_dev, not args.no_volume)
            rows[VARIANT_NAME[v]] = stats(eq, tr, args.capital)
            if args.trades:
                print(f"\n--- {VARIANT_NAME[v]} ---")
                for _, t in tr.iterrows():
                    adds = " | ".join(f"{a[1]}{a[2]}股@{a[3]:.2f}" for a in t.adds)
                    print(f"{t.entry} → {t.exit}  R={t.R:+.2f} (最高{t.maxR:+.2f})  {adds}  出:{t.exits[-1][1]}")
        tbl = pd.DataFrame(rows).T
        print(tbl.round(2).to_string())


if __name__ == "__main__":
    main()
