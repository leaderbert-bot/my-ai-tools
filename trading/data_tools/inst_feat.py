# -*- coding: utf-8 -*-
"""
把三大法人資料（data/inst10/inst10_YYYY.*.json.gz，十年三大法人.bat 抓的）對到 ★ 等策略的每一筆交易，
算出進場前的法人籌碼特徵，存成一個小檔 data/inst_feat.json（約幾百 KB），給 Claude 在雲端分析用。

每筆交易（live_bt.json 的 fundhi／fundall／fund1D／best，加 cyc10_bt.json 的 xlev）算：
  訊號日前一天（t-1，收盤買的時候只看得到前一天的法人資料）：
    f1/t1/d1   外資／投信／自營 當日買賣超（張）
    f5/t5/d5   前 5 日合計；f20/t20/d20 前 20 日合計
    tc/fc      投信／外資 連續買超天數（到 t-1）
    r5         前 5 日三大法人合計 ÷ 20 日均量（張）
    v20        20 日均量（張）
  另外存訊號日當天（t）的 f0/t0/d0（看盤後資料才有，只能當對照，不能當進場條件），和持有期間法人合計 hf/ht/hd。

用法（在 00money 資料夾）：python inst_feat.py
"""
import os, sys, json, gzip, glob
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load_inst(root):
    days = {}
    for f in glob.glob(os.path.join(root, "inst10_*.json.gz")):
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                j = json.load(fh)
        except Exception:
            continue
        for d, m in (j.get("days") or {}).items():
            days.setdefault(d, {}).update(m)
    return days


def main():
    import tw_radar as R
    inst = load_inst(os.path.join(R.DATA_DIR, "inst10"))
    cal = sorted(inst)
    if not cal:
        print("  data/inst10 沒有資料，先跑「十年三大法人.bat」"); return 1
    print("  三大法人 %d 天：%s ～ %s" % (len(cal), cal[0], cal[-1]))
    idx = {d: i for i, d in enumerate(cal)}
    # 20 日均量：從 k10y 月檔抓
    vol = {}
    for f in sorted(glob.glob(os.path.join(R.DATA_DIR, "k10y", "k10_*.json.gz"))):
        ym = os.path.basename(f)[4:11]
        m = R.k10_load_month(ym, cache=False)
        for d, row in (m.get("px") or {}).items():
            for c, v in row.items():
                if len(c) == 4 and c.isdigit() and isinstance(v, list) and len(v) >= 5:
                    vol.setdefault(c, {})[d] = float(v[4] or 0)
    trades = []
    lb = json.load(open(os.path.join(R.DATA_DIR, "live_bt.json"), encoding="utf-8"))
    for k, L in (lb.get("lists") or {}).items():
        ci = {c: i for i, c in enumerate(L["cols"])}
        for r in L["rows"]:
            trades.append(dict(strat=k, code=r[ci["code"]], sig=r[ci["sig"]], out=r[ci["out_date"]], ret=r[ci["ret_pct"]]))
    try:
        cb = json.load(open(os.path.join(R.DATA_DIR, "cyc10_bt.json"), encoding="utf-8"))
        x = cb["trades2"]["xlev"]; ci = {c: i for i, c in enumerate(x["cols"])}
        for r in x["rows"]:
            trades.append(dict(strat="xlev", code=r[ci["code"]], sig=r[ci["sig"]], out=r[ci["out_date"]], ret=r[ci["ret_pct"]]))
    except Exception as e:
        print("  （cyc10_bt.json 讀不到 xlev：%s）" % str(e)[:60])
    out = []; miss = 0
    for t in trades:
        c, s = t["code"], t["sig"]
        if s not in idx:
            miss += 1; continue
        i = idx[s]
        def g(j):
            return inst.get(cal[j], {}).get(c) if 0 <= j < len(cal) else None
        prev = [g(j) for j in range(i - 20, i)]           # t-20 .. t-1
        if sum(1 for p in prev if p) < 10:
            miss += 1; continue
        def ssum(rows, k): return sum(p[k] for p in rows if p)
        p1 = g(i - 1) or [0, 0, 0]; p0 = g(i) or [0, 0, 0]
        def streak(k):
            n = 0
            for j in range(i - 1, i - 61, -1):
                p = g(j)
                if p is None: break
                if p[k] > 0: n += 1
                else: break
            return n
        vs = vol.get(c, {})
        vd = [d for d in sorted(vs) if d <= cal[i - 1]][-20:]
        v20 = sum(vs[d] for d in vd) / len(vd) if vd else None
        f5, t5, d5 = ssum(prev[-5:], 0), ssum(prev[-5:], 1), ssum(prev[-5:], 2)
        hold = [g(j) for j in range(i, idx.get(t["out"], i) + 1)] if t["out"] in idx else []
        out.append(dict(strat=t["strat"], code=c, sig=s, ret=t["ret"],
                        f1=p1[0], t1=p1[1], d1=p1[2], f0=p0[0], t0=p0[1], d0=p0[2],
                        f5=f5, t5=t5, d5=d5, f20=ssum(prev, 0), t20=ssum(prev, 1), d20=ssum(prev, 2),
                        tc=streak(1), fc=streak(0), v20=v20,
                        r5=((f5 + t5 + d5) / v20 if v20 else None),
                        hf=ssum(hold, 0), ht=ssum(hold, 1), hd=ssum(hold, 2)))
    p = os.path.join(R.DATA_DIR, "inst_feat.json")
    json.dump({"v": 1, "from": cal[0], "to": cal[-1], "rows": out}, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("  %d 筆交易有特徵（%d 筆在法人資料範圍外或資料不足），存在 %s" % (len(out), miss, p))
    print("  跟 Claude 說「inst_feat 好了」。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
