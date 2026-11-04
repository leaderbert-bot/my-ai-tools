# -*- coding: utf-8 -*-
"""
補十年「三大法人買賣超」→ data/inst10/inst10_YYYY.json.gz，給 ★ 加籌碼條件的回測用。

- 資料來源跟雷達每天抓的一樣：證交所 T86（上市）、櫃買 insti/dailyTrade（上櫃），用 tw_radar.fetch_inst_day。
  單位：張。每檔 [外資（含外資自營）, 投信, 自營商]。
- 雷達自己的 inst_hist.json 只留 120 天，這支不會動它，另外存一份完整的。
- 交易日曆用 data/k10y 的日 K（有日 K 的那天才抓）。k10y 沒有的年份用平日逐日試，沒資料的那天會記成空的。
- 證交所會擋太密的請求，每天之間停 1.5 秒；約 2,400 個交易日要 2～3 小時。可以中斷、重跑會接著補（每 20 天存一次）。
- 只在一台電腦跑。

用法：雙擊「十年三大法人.bat」，或
  python inst10_dl.py                    # 2016-01-01 起（跟十年日 K 一樣）
  python inst10_dl.py --since 2012-05-02 # 證交所 T86 最早到這天
"""
import os, sys, json, gzip, time, argparse
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SAVE_EVERY = 20
SRC = "TWSE T86 + TPEx insti/dailyTrade，張；[外資, 投信, 自營]"


def host_tag():
    """每台電腦只寫自己的檔（inst10_YYYY.<電腦>.json.gz），兩台同時跑也不會在 Dropbox 打架。"""
    import socket, re
    return re.sub(r"[^A-Za-z0-9_-]", "_", socket.gethostname())[:24] or "pc"


def out_path(R, y, host=None):
    return os.path.join(R.DATA_DIR, "inst10", "inst10_%s.%s.json.gz" % (y, host or host_tag()))


def load_year(R, y, host=None):
    p = out_path(R, y, host)
    if not os.path.exists(p):
        return {"v": 1, "src": SRC, "host": host or host_tag(), "days": {}, "empty": []}
    try:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            d = json.load(f)
        d.setdefault("days", {}); d.setdefault("empty", [])
        return d
    except Exception:
        return {"v": 1, "src": SRC, "host": host or host_tag(), "days": {}, "empty": []}


def done_everywhere(R, y):
    """這一年所有電腦已經查過的日期（有資料的和空的）。"""
    import glob
    out = set()
    for p in glob.glob(os.path.join(R.DATA_DIR, "inst10", "inst10_%s*.json.gz" % y)):
        try:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                d = json.load(f)
            out.update((d.get("days") or {}).keys()); out.update(d.get("empty") or [])
        except Exception:
            pass
    return out


def save_year(R, y, d):
    os.makedirs(os.path.join(R.DATA_DIR, "inst10"), exist_ok=True)
    p = out_path(R, y); tmp = p + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, p)


def calendar(R, since, until):
    cal = set()
    cur = date(int(since[:4]), int(since[5:7]), 1)
    while cur <= until:
        ym = "%04d-%02d" % (cur.year, cur.month)
        m = R.k10_load_month(ym, cache=False)
        for d in (m.get("px") or {}).keys():
            cal.add(d)
        cur = date(cur.year + (1 if cur.month == 12 else 0), 1 if cur.month == 12 else cur.month + 1, 1)
    have_years = set(d[:4] for d in cal)
    d = date.fromisoformat(since)
    while d <= until:
        if d.weekday() < 5 and str(d.year) not in have_years:
            cal.add(d.isoformat())
        d += timedelta(days=1)
    return sorted(x for x in cal if since <= x <= until.isoformat())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2016-01-01")
    ap.add_argument("--sleep", type=float, default=1.5)
    a = ap.parse_args()
    import tw_radar as R
    until = date.today() - timedelta(days=1)
    cal = calendar(R, a.since, until)
    years = sorted(set(d[:4] for d in cal))
    cache = {y: load_year(R, y) for y in years}
    done_all = {y: done_everywhere(R, y) for y in years}
    todo = [d for d in cal if d not in done_all[d[:4]]]
    print("  %s ～ %s：%d 天要查，已有 %d 天" % (a.since, until, len(todo), len(cal) - len(todo)))
    print("  這台電腦：%s。兩台可以同時跑，各寫自己的檔，順序錯開。" % host_tag())
    if not todo:
        print("  都補好了。"); return 0
    import random
    random.Random(host_tag()).shuffle(todo)
    n_ok = n_empty = 0; dirty = set(); t0 = time.time()
    for i, d in enumerate(todo):
        y = d[:4]
        if d in done_all[y]:
            continue
        got = R.fetch_inst_day(d)
        if got:
            cache[y]["days"][d] = got; n_ok += 1
        else:
            cache[y]["empty"].append(d); n_empty += 1
        dirty.add(y)
        if (i + 1) % SAVE_EVERY == 0:
            for yy in dirty: save_year(R, yy, cache[yy])
            dirty.clear()
            for yy in years:
                done_all[yy] = done_everywhere(R, yy)
            el = time.time() - t0; eta = el / (i + 1) * (len(todo) - i - 1)
            print("  %5d / %d  有資料 %d、空 %d  已 %.0f 分，約再 %.0f 分" % (i + 1, len(todo), n_ok, n_empty, el / 60, eta / 60))
        time.sleep(a.sleep)
    for yy in dirty: save_year(R, yy, cache[yy])
    print("")
    print("  完成：有資料 %d 天、沒資料 %d 天；檔案在 %s" % (n_ok, n_empty, os.path.join(R.DATA_DIR, "inst10")))
    print("  跟 Claude 說「三大法人抓好了」就可以把籌碼條件加進 ★ 回測。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中斷（最近 20 天以前的都存好了；再跑一次接著補）。"); sys.exit(130)
    except Exception as e:
        print("\n失敗：%s" % str(e)[:300]); sys.exit(1)
