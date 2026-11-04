# -*- coding: utf-8 -*-
"""
下載「事件日」的個股 1 分 K → data/stk1m/stk1m_YYYY-MM.json.gz，給當沖類策略的盤中驗證用：
  鎖漲停隔天開高空、恐慌急殺隔天、處置股盤中轉折、搶漲停隔日沖。

- 不是抓全市場（那要幾十 GB），只抓回測需要的 (代號, 日期)：
    lock  ：收盤鎖漲停那天 D，和隔天 D+1（鎖漲停隔天開高空、搶漲停隔日沖要用）
    panic ：飆股那天 D（近 4 天 ≥3 天漲 ≥5%、沒有一天 |漲跌| <2%、5 日累積 ≥18%）和隔天 D+1
    punish：處置期間每一天，加處置前一天（data/punish_hist.json）
    touch ：盤中碰到漲停但沒鎖住的那天 D 和 D+1（預設不抓，加 --touch 才抓）
  條件跟 tw_radar._xl_setups 一樣：20 日均量 ≥ 500 張、股價 ≥ 10。
- 事件來源是 data/k10y 的全市場日 K（新春行情回測抓的那份）。
- 用台股雷達同一套永豐 Shioaji 登入（只用行情權限，金鑰在家目錄 .tw_radar_sinopac.json）。不下單。
- 可以中斷、可以重跑：抓到的每 50 筆存一次，下次接著抓。永豐有每日流量上限，用完就明天再跑。
- 兩台電腦可以同時跑：每台只寫自己名字的檔，抓的順序用電腦名錯開，Dropbox 不會打架。

用法：雙擊「下載個股分K.bat」，或
  python stk1m_dl.py                      # 預設從 2020-01-01 起（永豐大約從 2020 年起有分 K）
  python stk1m_dl.py --since 2022-01-01   # 改起點
  python stk1m_dl.py --touch              # 也抓「盤中碰到漲停」
  python stk1m_dl.py --kinds lock,punish  # 只抓某幾類
  python stk1m_dl.py --list               # 只列出要抓幾筆，不登入
"""
import os, sys, json, gzip, time, argparse
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SAVE_EVERY = 50
MIN_REMAIN_BYTES = 8 * 1024 * 1024      # 永豐剩餘流量低於這個就停，明天再跑
SRC = "SinoPac Shioaji kbars 1 分 K；t＝HH:MM 台灣時間"


def wall(ts):
    try:
        return (datetime(1970, 1, 1) + timedelta(seconds=int(ts) / 1e9)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"


def month_iter(d0, d1):
    cur = date(d0.year, d0.month, 1)
    while cur <= d1:
        yield "%04d-%02d" % (cur.year, cur.month)
        cur = date(cur.year + (1 if cur.month == 12 else 0), 1 if cur.month == 12 else cur.month + 1, 1)


def load_daily(R, since, until):
    """把 k10y 月檔接成 {代號: {日期: [o,h,l,c,v]}} 與交易日曆。從 since 往前 45 天起載。"""
    px = {}; cal = set()
    d0 = date.fromisoformat(since) - timedelta(days=45)
    for ym in month_iter(d0, until):
        m = R.k10_load_month(ym, cache=False)
        for d, row in (m.get("px") or {}).items():
            cal.add(d)
            for c, v in row.items():
                if len(c) == 4 and c.isdigit() and isinstance(v, list) and len(v) >= 5:
                    px.setdefault(c, {})[d] = v
    return px, sorted(cal)


def find_events(px, cal, since, kinds, touch, punish):
    """回傳 {(代號, 日期): set(類別)}"""
    ev = {}
    idx = {d: i for i, d in enumerate(cal)}

    def add(c, d, k):
        if d >= since:
            ev.setdefault((c, d), set()).add(k)

    for c, slot in px.items():
        ds = sorted(slot)
        if len(ds) < 27:
            continue
        for i in range(26, len(ds)):
            d = ds[i]
            if d < since:
                continue
            rows = [slot[x] for x in ds[i - 26:i + 1]]
            try:
                h = [float(r[1]) for r in rows]
                cl = [float(r[3]) for r in rows]; vol = [float(r[4] or 0) for r in rows]
            except Exception:
                continue
            if any(x <= 0 for x in cl) or cl[-1] < 10:
                continue
            if sum(vol[-20:]) / 20.0 < 500:
                continue
            pc = cl[-2]
            nxt = cal[idx[d] + 1] if d in idx and idx[d] + 1 < len(cal) else None
            lu = cl[-1] >= pc * 1.094 and cl[-1] >= h[-1] * 0.999
            if "lock" in kinds and lu:
                add(c, d, "lock")
                if nxt: add(c, nxt, "lock+1")
            if touch and "touch" in kinds and (not lu) and h[-1] >= pc * 1.094:
                add(c, d, "touch")
                if nxt: add(c, nxt, "touch+1")
            if "panic" in kinds:
                rets = [(cl[k] / cl[k - 1] - 1) * 100 for k in range(-4, 0)]
                panic = sum(1 for r in rets if r >= 5) >= 3 and all(abs(r) >= 2 for r in rets) and (cl[-1] / cl[-6] - 1) * 100 >= 18
                if panic:
                    add(c, d, "panic")
                    if nxt: add(c, nxt, "panic+1")
    if "punish" in kinds and punish:
        for c, lst in punish.items():
            if not (isinstance(c, str) and len(c) == 4 and c.isdigit()):
                continue
            for item in lst or []:
                try:
                    a, b = str(item[0]), str(item[1])
                except Exception:
                    continue
                if b < since:
                    continue
                days = [d for d in cal if a <= d <= b]
                if days and days[0] in idx and idx[days[0]] > 0:
                    add(c, cal[idx[days[0]] - 1], "punish-1")
                for d in days:
                    add(c, d, "punish")
    return ev


def host_tag():
    """這台電腦的名字：每台電腦只寫自己的檔（stk1m_YYYY-MM.<電腦>.json.gz），兩台同時跑也不會在 Dropbox 打架。"""
    import socket, re
    return re.sub(r"[^A-Za-z0-9_-]", "_", socket.gethostname())[:24] or "pc"


def out_path(R, ym, host=None):
    return os.path.join(R.DATA_DIR, "stk1m", "stk1m_%s.%s.json.gz" % (ym, host or host_tag()))


def load_month(R, ym, host=None):
    p = out_path(R, ym, host)
    if not os.path.exists(p):
        return {"v": 1, "src": SRC, "host": host or host_tag(), "done": {}, "bars": {}}
    try:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            d = json.load(f)
        d.setdefault("done", {}); d.setdefault("bars", {})
        return d
    except Exception:
        return {"v": 1, "src": SRC, "host": host or host_tag(), "done": {}, "bars": {}}


def done_everywhere(R, ym):
    """這個月所有電腦已經抓過的 (代號|日期)，含舊版沒有電腦名的檔。"""
    import glob
    out = set()
    for p in glob.glob(os.path.join(R.DATA_DIR, "stk1m", "stk1m_%s*.json.gz" % ym)):
        try:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                out.update((json.load(f).get("done") or {}).keys())
        except Exception:
            pass
    return out


def save_month(R, ym, d):
    os.makedirs(os.path.join(R.DATA_DIR, "stk1m"), exist_ok=True)
    p = out_path(R, ym); tmp = p + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, p)


def remaining_bytes(api):
    try:
        u = api.usage()
        v = getattr(u, "remaining_bytes", None) if not isinstance(u, dict) else u.get("remaining_bytes")
        if v is not None:
            return int(v)
    except Exception:
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2020-01-01")
    ap.add_argument("--kinds", default="lock,panic,punish,touch")
    ap.add_argument("--touch", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--next-only", action="store_true", help="lock/panic/touch 只抓隔天 D+1（做交易的那天），量減半")
    ap.add_argument("--sleep", type=float, default=0.4)
    a = ap.parse_args()
    import tw_radar as R
    kinds = set(a.kinds.split(","))
    print("  讀 data/k10y 日 K、找事件日…")
    px, cal = load_daily(R, a.since, date.today())
    if not cal:
        print("  data/k10y 沒有資料。先跑「新春行情回測」把十年日 K 抓回來。"); return 1
    punish = {}
    try:
        with open(os.path.join(R.DATA_DIR, "punish_hist.json"), "r", encoding="utf-8") as f:
            punish = json.load(f)
    except Exception:
        print("  （沒有 punish_hist.json，略過處置股）")
    ev = find_events(px, cal, a.since, kinds, a.touch, punish)
    if a.next_only:
        ev = {k: v for k, v in ev.items() if any(x.endswith("+1") or x.startswith("punish") for x in v)}
    by_kind = {}
    for ks in ev.values():
        for k in ks:
            by_kind[k] = by_kind.get(k, 0) + 1
    print("  事件 (代號,日期) 共 %d 筆：%s" % (len(ev), "、".join("%s %d" % (k, n) for k, n in sorted(by_kind.items()))))
    months = sorted(set(d[:7] for _, d in ev))
    cache = {ym: load_month(R, ym) for ym in months}
    done_all = {ym: done_everywhere(R, ym) for ym in months}
    todo = sorted((c, d) for (c, d) in ev if (c + "|" + d) not in done_all[d[:7]])
    done = len(ev) - len(todo)
    print("  已抓 %d、還要抓 %d（每筆約 270 根、約 25 KB；永豐每天有流量上限，用完明天再跑會接著抓）" % (done, len(todo)))
    print("  這台電腦：%s。兩台可以同時跑，各寫自己的檔，順序錯開，不會重複太多。" % host_tag())
    if a.list or not todo:
        return 0
    import random
    random.Random(host_tag()).shuffle(todo)      # 每台電腦用不同順序抓，兩台同時跑才不會抓同一批
    print("  登入永豐（只看行情）…")
    api = R._sj_login()
    rb = remaining_bytes(api)
    if rb is not None:
        print("  永豐今日剩餘流量約 %.0f MB" % (rb / 1e6))
    n_ok = n_fail = n_none = 0; dirty = set(); t0 = time.time(); stop = False
    for i, (c, d) in enumerate(todo):
        ym = d[:7]
        if (c + "|" + d) in done_all[ym]:
            continue                                   # 另一台剛抓過了
        ct = R._sj_contract(api, c)
        if ct is None:
            cache[ym]["done"][c + "|" + d] = "no-contract"; dirty.add(ym); n_none += 1
            continue
        kb = None
        for k in range(3):
            try:
                kb = api.kbars(contract=ct, start=d, end=d)
                break
            except Exception as e:
                msg = str(e)
                if "limit" in msg.lower() or "quota" in msg.lower():
                    print("  流量到上限了：%s" % msg[:100]); stop = True; break
                time.sleep(2.0 * (k + 1))
        if stop:
            break
        if kb is None:
            n_fail += 1
            continue
        g = lambda key: list(getattr(kb, key, None) or (kb.get(key) if isinstance(kb, dict) else []) or [])
        ts, O, H, L, C, V = g("ts"), g("Open"), g("High"), g("Low"), g("Close"), g("Volume")
        rows = []
        for j in range(min(len(ts), len(O), len(H), len(L), len(C))):
            w = wall(ts[j])
            if w[:10] != d:
                continue
            rows.append((w[11:], float(O[j]), float(H[j]), float(L[j]), float(C[j]), float(V[j] or 0) if j < len(V) else 0.0))
        if rows:
            cache[ym]["bars"].setdefault(c, {})[d] = {
                "t": [r[0] for r in rows], "o": [r[1] for r in rows], "h": [r[2] for r in rows],
                "l": [r[3] for r in rows], "c": [r[4] for r in rows], "v": [r[5] for r in rows],
                "k": sorted(ev[(c, d)])}
            cache[ym]["done"][c + "|" + d] = len(rows); n_ok += 1
        else:
            cache[ym]["done"][c + "|" + d] = 0; n_none += 1
        dirty.add(ym)
        if (i + 1) % SAVE_EVERY == 0:
            for m in dirty: save_month(R, m, cache[m])
            dirty.clear()
            for m in set(x[1][:7] for x in todo[i + 1:i + 1 + SAVE_EVERY * 4]):
                done_all[m] = done_everywhere(R, m)    # 看一下另一台抓到哪了
            rb = remaining_bytes(api)
            el = time.time() - t0
            print("  %5d / %d  成功 %d、空 %d、失敗 %d  %.0f 秒%s" % (
                i + 1, len(todo), n_ok, n_none, n_fail, el, ("  剩餘流量 %.0f MB" % (rb / 1e6)) if rb is not None else ""))
            if rb is not None and rb < MIN_REMAIN_BYTES:
                print("  永豐今日流量快用完，先停。明天再雙擊一次會接著抓。"); break
        time.sleep(a.sleep)
    for m in dirty: save_month(R, m, cache[m])
    print("")
    print("  這次：成功 %d、沒資料 %d、失敗 %d；檔案在 %s" % (n_ok, n_none, n_fail, os.path.join(R.DATA_DIR, "stk1m")))
    left = len(todo) - n_ok - n_none
    if left > 0:
        print("  還有約 %d 筆沒抓，再跑一次會接著抓。" % left)
    else:
        print("  全部抓完。跟 Claude 說「個股分K抓好了」就可以驗當沖策略。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中斷（最近 50 筆以前的都存好了；再跑一次接著抓）。"); sys.exit(130)
    except Exception as e:
        print("\n失敗：%s" % str(e)[:300]); sys.exit(1)
