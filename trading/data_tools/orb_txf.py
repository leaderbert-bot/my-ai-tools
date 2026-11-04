# -*- coding: utf-8 -*-
"""
台指期 1 分 K 盤中策略回測（馬克楊課程裡講的兩個，照 馬克楊重點與策略.md 第四節的規則）。
資料：data/txf_1m.json.gz（「下載台指期分K.bat」抓的，TXFR1 近月連續，ts＝台灣時間當 UTC 的奈秒）。

策略 1  ORB 崩盤空單（日盤）
  08:45～09:30 的區間寬度 > 100 點，而且 09:30 前累計成交量 > 昨天日盤總量 × 0.3
  → 在區間低點 −1 掛觸價空（之後盤中跌破就成交）。停損 0.4%（以進場價算），13:44 收盤平倉，不設停利。
策略 2  400 口爆大量突破（夜盤 15:00～05:00）
  1 分 K 成交量 ≥ 400 口。紅 K（收 > 開）：之後跌破這根低點 −1 就空；綠 K（收 < 開）：漲過高點 +1 就多。
  停損＝K 棒另一端外 1 點，停利 2R；賺到 1R 就把停損移到保本。訊號在 20 根內沒觸發就作廢。夜盤收盤前平倉。
  （課程還有「出現反向訊號就 2 倍口數反手」，這版沒做，先看單純版有沒有優勢。）
成本：每筆來回 COST 點（預設 4 點：手續費加期交稅，大台小台微台都差不多是這個數量級的「點」）。
報酬以「點」報告；大台 1 點 200 元、小台 50 元、微台 10 元。

用法：python orb_txf.py            （在 00money 資料夾）
      python orb_txf.py --cost 3 --orb-width 80 --vol 300   調參數看穩不穩
結果寫到 台指期盤中回測.md。
"""
import os, sys, json, gzip, argparse, statistics, collections
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        d = json.load(f)
    bars = []
    for ts, o, h, l, c, v in zip(d["ts"], d["o"], d["h"], d["l"], d["c"], d["v"]):
        t = datetime(1970, 1, 1) + timedelta(seconds=int(ts) / 1e9)      # 台灣時間
        bars.append((t, float(o), float(h), float(l), float(c), float(v or 0)))
    bars.sort()
    return bars


def sessions(bars):
    """切成日盤（08:45～13:45）和夜盤（15:00～隔天 05:00）。回傳 [(kind, date_key, [bars])]"""
    out = []; cur = None
    for b in bars:
        t = b[0]; hm = t.hour * 60 + t.minute
        if 8 * 60 + 45 <= hm < 13 * 60 + 46:
            key = ("day", t.date().isoformat())
        elif hm >= 15 * 60 or hm < 5 * 60 + 1:
            d = t.date() if hm >= 15 * 60 else (t - timedelta(days=1)).date()
            key = ("night", d.isoformat())
        else:
            continue
        if cur is None or cur[0] != key:
            cur = (key, []); out.append(cur)
        cur[1].append(b)
    return [(k[0], k[1], bs) for k, bs in out]


def orb_short(day_sessions, width_min=100.0, vol_ratio=0.3, stop_pct=0.004, cost=4.0):
    trades = []; prev_vol = None
    for kind, d, bs in day_sessions:
        tot = sum(b[5] for b in bs)
        if prev_vol is None or len(bs) < 60:
            prev_vol = tot; continue
        rng = [b for b in bs if (b[0].hour * 60 + b[0].minute) < 9 * 60 + 30]
        rest = [b for b in bs if (b[0].hour * 60 + b[0].minute) >= 9 * 60 + 30]
        if len(rng) < 20 or not rest:
            prev_vol = tot; continue
        hi = max(b[2] for b in rng); lo = min(b[3] for b in rng); cum = sum(b[5] for b in rng)
        if hi - lo > width_min and cum > prev_vol * vol_ratio:
            trig = lo - 1.0; entry = None
            for b in rest:
                if entry is None:
                    if b[3] <= trig:
                        entry = trig if b[1] > trig else b[1]      # 觸價：開盤已經低於觸價就用開盤
                        stop = entry * (1 + stop_pct); e_t = b[0]
                    continue
                if b[2] >= stop:
                    trades.append(dict(d=d, k="orb", entry=entry, exit=stop, pts=entry - stop - cost, how="停損", t=e_t)); entry = None; break
            else:
                if entry is not None:
                    ex = rest[-1][4]
                    trades.append(dict(d=d, k="orb", entry=entry, exit=ex, pts=entry - ex - cost, how="收盤", t=e_t))
        prev_vol = tot
    return trades


def vol_break(night_sessions, vol_min=400.0, rr=2.0, expire=20, cost=4.0):
    trades = []
    for kind, d, bs in night_sessions:
        i = 0; n = len(bs)
        while i < n - 2:
            b = bs[i]
            if b[5] >= vol_min and b[4] != b[1]:
                up = b[4] > b[1]
                trig = (b[3] - 1.0) if up else (b[2] + 1.0)       # 紅K跌破低點空；綠K漲過高點多
                stop0 = (b[2] + 1.0) if up else (b[3] - 1.0)
                side = -1 if up else 1
                entry = None; j = i + 1
                while j < n and j <= i + expire and entry is None:
                    bb = bs[j]
                    if (side < 0 and bb[3] <= trig) or (side > 0 and bb[2] >= trig):
                        entry = trig
                        if (side < 0 and bb[1] < trig) or (side > 0 and bb[1] > trig): entry = bb[1]
                        R = abs(entry - stop0); tp = entry + side * rr * R; stop = stop0; be = False; e_j = j
                    j += 1
                if entry is None:
                    i += 1; continue
                closed = False
                for k in range(e_j + 1, n):
                    bb = bs[k]
                    if side < 0:
                        if bb[2] >= stop: trades.append(dict(d=d, k="vb", side="空", entry=entry, exit=stop, pts=(entry - stop) - cost, how="停損" if not be else "保本", t=bs[e_j][0])); closed = True; i = k; break
                        if bb[3] <= tp: trades.append(dict(d=d, k="vb", side="空", entry=entry, exit=tp, pts=(entry - tp) - cost, how="停利", t=bs[e_j][0])); closed = True; i = k; break
                        if not be and bb[3] <= entry - R: stop = entry; be = True
                    else:
                        if bb[3] <= stop: trades.append(dict(d=d, k="vb", side="多", entry=entry, exit=stop, pts=(stop - entry) - cost, how="停損" if not be else "保本", t=bs[e_j][0])); closed = True; i = k; break
                        if bb[2] >= tp: trades.append(dict(d=d, k="vb", side="多", entry=entry, exit=tp, pts=(tp - entry) - cost, how="停利", t=bs[e_j][0])); closed = True; i = k; break
                        if not be and bb[2] >= entry + R: stop = entry; be = True
                if not closed:
                    ex = bs[-1][4]
                    trades.append(dict(d=d, k="vb", side="空" if side < 0 else "多", entry=entry, exit=ex, pts=side * (ex - entry) - cost, how="收盤", t=bs[e_j][0])); i = n
            i += 1
    return trades


def report(name, T, lines):
    def P(s): print(s); lines.append(s)
    if not T:
        P("## %s\n- 沒有交易。" % name); return
    pts = [t["pts"] for t in T]
    P("## %s" % name)
    P("- %d 筆，每筆平均 %+.1f 點、中位 %+.1f 點、勝率 %.0f%%、合計 %+.0f 點；平均賺 %+.1f、平均賠 %+.1f" % (
        len(T), statistics.mean(pts), statistics.median(pts), 100 * sum(1 for p in pts if p > 0) / len(pts), sum(pts),
        statistics.mean([p for p in pts if p > 0]) if any(p > 0 for p in pts) else 0, statistics.mean([p for p in pts if p <= 0]) if any(p <= 0 for p in pts) else 0))
    how = collections.Counter(t["how"] for t in T); P("- 出場方式：%s" % dict(how))
    ym = collections.defaultdict(list)
    for t in T: ym[t["d"][:7]].append(t["pts"])
    P("- 逐月（筆數／合計點）：" + "、".join("%s %d/%+.0f" % (m, len(v), sum(v)) for m, v in sorted(ym.items())))
    pos_m = sum(1 for v in ym.values() if sum(v) > 0); P("- 正的月份 %d/%d" % (pos_m, len(ym)))
    # 隨機對照：同樣天數、同方向、隨機時間進場、同樣持有到收盤（只給 ORB 用）
    P("")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=os.path.join(HERE, "data", "txf_1m.json.gz"))
    ap.add_argument("--cost", type=float, default=4.0)
    ap.add_argument("--orb-width", type=float, default=100.0)
    ap.add_argument("--orb-volratio", type=float, default=0.3)
    ap.add_argument("--orb-stop", type=float, default=0.004)
    ap.add_argument("--vol", type=float, default=400.0)
    ap.add_argument("--rr", type=float, default=2.0)
    ap.add_argument("--out", default=os.path.join(HERE, "台指期盤中回測.md"))
    a = ap.parse_args()
    if not os.path.exists(a.file):
        print("  找不到 %s，先雙擊「下載台指期分K.bat」" % a.file); return 1
    bars = load(a.file)
    S = sessions(bars)
    days = [s for s in S if s[0] == "day"]; nights = [s for s in S if s[0] == "night"]
    lines = ["# 台指期盤中策略回測（%s ～ %s；%d 個日盤、%d 個夜盤；成本每筆 %.0f 點）" % (bars[0][0].date(), bars[-1][0].date(), len(days), len(nights), a.cost), ""]
    print(lines[0])
    report("ORB 崩盤空單（區間 > %.0f 點、量 > 昨日 %.0f%%、停損 %.1f%%、收盤平倉）" % (a.orb_width, a.orb_volratio * 100, a.orb_stop * 100),
           orb_short(days, a.orb_width, a.orb_volratio, a.orb_stop, a.cost), lines)
    # 敏感度：區間寬度、量比
    for w in (60, 80, 100, 150):
        for vr in (0.2, 0.3, 0.5):
            T = orb_short(days, w, vr, a.orb_stop, a.cost)
            if T: lines.append("- ORB 區間>%d、量>%.0f%%：%d 筆、每筆 %+.1f 點、合計 %+.0f" % (w, vr * 100, len(T), statistics.mean(t["pts"] for t in T), sum(t["pts"] for t in T)))
    lines.append("")
    report("400 口爆量突破（夜盤；量 ≥ %.0f 口、停利 %.0fR、1R 保本）" % (a.vol, a.rr), vol_break(nights, a.vol, a.rr, 20, a.cost), lines)
    for vm in (200, 300, 400, 600):
        for rr in (1.5, 2.0, 3.0):
            T = vol_break(nights, vm, rr, 20, a.cost)
            if T: lines.append("- 量≥%d、停利 %.1fR：%d 筆、每筆 %+.1f 點、勝率 %.0f%%、合計 %+.0f" % (vm, rr, len(T), statistics.mean(t["pts"] for t in T), 100 * sum(1 for t in T if t["pts"] > 0) / len(T), sum(t["pts"] for t in T)))
    lines += ["", "註：1 分 K 看不到同一根裡停損和停利誰先碰到，這裡一律算先停損（偏保守）；觸價單用觸價成交、不算滑價。",
              "這是歷史回測，不是投資建議。"]
    with open(a.out, "w", encoding="utf-8") as f: f.write("\n".join(lines) + "\n")
    print("  已寫到 %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
