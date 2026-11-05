# -*- coding: utf-8 -*-
"""
★ 候選排序：同一天候選比空位多時，改成「當天創新高（收盤＝近一年最高）的先買，同級再照 20 日均量大的先」。
原本是只照 20 日均量大的先。依據：★候選排序_測試.md（2026-11-05，13,708 筆候選、同分打亂 30 次，四種設定都贏隨機中位 5～7 點、26～30/30 次）。
只動 ★ 系列（fundhi／fundall／fund1D／best）；季報意外獲利、財報爆發跳空的順序不變。

用法：雙擊「候選排序改進雷達.bat」（跑一次；再跑會說已經加過）。會先備份 tw_radar.py.bak_rank。
"""
import os, sys, io, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "tw_radar.py")
MARK = "_lt_rank_key"

OLD_OUT = '''            out[c] = {"m": m, "why": why, "tag": tag, "vol": v.get("vol") or 0, "px": px, "xe": xe, "q": v.get("q"), "bg": v.get("bg")}'''
NEW_OUT = '''            out[c] = {"m": m, "why": why, "tag": tag, "vol": v.get("vol") or 0, "px": px, "xe": xe, "q": v.get("q"), "bg": v.get("bg"), "phi": v.get("phi")}'''

OLD_SORT = '''            cands = sorted([(c, s) for c, s in sig.items() if k in s["m"]], key=(lambda z: -(((z[1].get("bg") or {}).get("gap")) or 0)) if k == "bgap" else (lambda z: -(z[1].get("vol") or 0)))   # 候選多時先買 20 日均量大的（財報爆發跳空：跳空大的先買）'''
NEW_SORT = '''            cands = sorted([(c, s) for c, s in sig.items() if k in s["m"]], key=_lt_rank_key(k))   # 候選多時：★ 系列先買當天創新高的、同級再均量大的（2026-11-05 排序測試）；財報爆發跳空：跳空大的先買；其他：均量大的先'''

FUNC_ANCHOR = "def live_signals(sc, ind_map, mkt_ok, rank_src=None, pxmap=None):\n"
FUNC = '''def _lt_rank_key(k):
    """同一天候選比空位多時先買誰。★ 系列：收盤＝近一年最高（phi ≥ 0.9999）的先、同級再 20 日均量大的先。
    依據 ★候選排序_測試.md（2026-11-05）：13,708 筆候選、同分打亂 30 次，四種設定都比隨機中位多 5～7 個百分點、26～30/30 次；
    原本「只照均量」在 95% 門檻時跟隨機差不多。MGK、菲比斯、點位種類當排序都沒用。"""
    if k == "bgap":
        return lambda z: -(((z[1].get("bg") or {}).get("gap")) or 0)
    if k in ("fundhi", "fundall", "fund1D", "best"):
        return lambda z: (0 if (z[1].get("phi") or 0) >= 0.9999 else 1, -(z[1].get("vol") or 0))
    return lambda z: -(z[1].get("vol") or 0)


'''


def main():
    if not os.path.exists(TARGET):
        print("  找不到 %s" % TARGET); return 1
    with io.open(TARGET, "r", encoding="utf-8") as f:
        src = f.read()
    if MARK in src:
        print("  已經加過了（tw_radar.py 裡有 %s）。" % MARK); return 0
    for nm, s in (("候選記錄", OLD_OUT), ("排序那一行", OLD_SORT), ("live_signals", FUNC_ANCHOR)):
        c = src.count(s)
        if c != 1:
            print("  tw_radar.py 版本跟預期不同：%s 找到 %d 處（要剛好 1 處）。沒有改任何東西。" % (nm, c)); return 2
    bak = TARGET + ".bak_rank"
    shutil.copyfile(TARGET, bak)
    out = src.replace(OLD_OUT, NEW_OUT, 1).replace(OLD_SORT, NEW_SORT, 1).replace(FUNC_ANCHOR, FUNC + FUNC_ANCHOR, 1)
    try:
        compile(out, TARGET, "exec")
    except SyntaxError as e:
        print("  改完語法有錯（%s），沒有存檔。" % e); return 3
    with io.open(TARGET + ".tmp", "w", encoding="utf-8", newline="") as f:
        f.write(out)
    os.replace(TARGET + ".tmp", TARGET)
    print("  完成。備份在 %s" % os.path.basename(bak))
    print("  重新啟動台股雷達。從下一次 13:15 掃描起，★ 候選多時先買當天創新高的、同級再均量大的。")
    print("  要改回原本的：把 tw_radar.py.bak_rank 改名回 tw_radar.py。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
