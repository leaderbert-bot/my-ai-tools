"""任務 D 補充：new_price／轉 vol 事件的時間集中度，與「同月所有產業」橫斷面基準（去掉市場層與年份集中的效果）。
cd SP && timeout 1800 python3 stagetest/d_audit_extra.py  → 附加寫到 stagetest/d_audit_out.txt 末尾（另存 d_audit_extra_out.txt）"""
import sys, os, pickle, collections, statistics, bisect, time
SP = "/tmp/claude-0/-home-user-my-ai-tools/bb9482f7-4c31-5f24-a06a-81bc958a76a4/scratchpad"
sys.path.insert(0, SP); os.chdir(SP)
OUT = open("stagetest/d_audit_extra_out.txt", "w", encoding="utf-8")
def P(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); OUT.write(s + "\n"); OUT.flush()
def med(xs): return statistics.median(xs) if xs else float("nan")
def f1(x): return "nan" if x is None or x != x else "%.1f" % x
px, cal, mk = pickle.load(open("px.pkl", "rb")); idx = {d: i for i, d in enumerate(cal)}
import stage_lib as S
D = S.D; YMS = D["yms"]; AV = D["avail"]; IND = D["IND"]
c50 = []; last = None
for d in cal:
    v = px.get("0050", {}).get(d); last = v[3] if v else last; c50.append(last)
inds_all = sorted(set(k for k, _ in D["ind"]))
mem = collections.defaultdict(list)
for c, k in IND.items():
    if c in px: mem[k].append(c)
CLIP = 0.35
def build(groups):
    ds = {k: [0.0] * len(cal) for k in groups}; dc = {k: [0] * len(cal) for k in groups}
    for k, ms in groups.items():
        for c in ms:
            s_ = px[c]; prev = None; previ = -99
            for i, d in enumerate(cal):
                v = s_.get(d)
                if v and v[3]:
                    if prev is not None and i - previ <= 10:
                        r = v[3] / prev - 1
                        if abs(r) <= CLIP: ds[k][i] += r; dc[k][i] += 1
                    prev = v[3]; previ = i
    out = {}
    for k in groups:
        lv = 100.0; o = []
        for i in range(len(cal)):
            if dc[k][i] >= 3: lv *= 1 + ds[k][i] / dc[k][i]
            o.append(lv)
        out[k] = o
    return out
DIDX = build({k: mem[k] for k in inds_all})
P("\n==== 4b. 補充：事件的時間集中度與橫斷面基準（d_audit_extra.py）====")
def fwd(k, ym, h):
    i0 = idx[AV[ym]]; i1 = i0 + h
    if i1 >= len(cal): return None
    return (DIDX[k][i1] / DIDX[k][i0] - 1) * 100
# 橫斷面基準：同一個 ym 所有有資料的產業的 forward 中位數
XS = {}
for ym in YMS:
    for h in (63, 126, 252):
        xs = [fwd(k, ym, h) for k in inds_all if (k, ym) in D["ind"]]; xs = [x for x in xs if x is not None]
        XS[(ym, h)] = med(xs) if xs else None
conds = (("new_price", lambda o: o["new_price"]), ("轉 vol/vol?", lambda o: o["stage"] in ("vol", "vol?") and o["prev_stage"] in ("down", "flat")),
         ("price（所有 price 月）", lambda o: o["stage"] == "price"), ("vol（所有 vol 月）", lambda o: o["stage"] == "vol"), ("down（所有 down 月）", lambda o: o["stage"] == "down"))
for lab, cond in conds:
    ev = [(k, ym) for (k, ym), o in D["ind"].items() if cond(o)]
    yrs = collections.Counter(ym[:4] for _, ym in ev); mon = len(set(ym for _, ym in ev))
    P("  %-22s n=%d；分佈年份 %s；落在 %d 個不同月份（同月多產業一起轉＝不獨立）" % (lab, len(ev), dict(sorted(yrs.items())), mon))
    for h, hl in ((63, "3月"), (126, "6月"), (252, "12月")):
        xs = []; xc = []
        for k, ym in ev:
            f = fwd(k, ym, h)
            if f is None or XS[(ym, h)] is None: continue
            i0 = idx[AV[ym]]; i1 = i0 + h
            xs.append(f - (c50[i1] / c50[i0] - 1) * 100); xc.append(f - XS[(ym, h)])
        P("      %s：扣 0050 中位 %s 平均 %s 勝 %s%% | 扣「同月所有產業中位」中位 %s 平均 %s 勝 %s%% (n=%d)" % (hl, f1(med(xs)), f1(statistics.mean(xs)) if xs else "nan", f1(100 * sum(1 for x in xs if x > 0) / len(xs)) if xs else "nan",
            f1(med(xc)), f1(statistics.mean(xc)) if xc else "nan", f1(100 * sum(1 for x in xc if x > 0) / len(xc)) if xc else "nan", len(xc)))
    if lab == "new_price":
        P("      new_price 逐年（12 月、扣同月所有產業中位）：")
        byy = collections.defaultdict(list)
        for k, ym in ev:
            f = fwd(k, ym, 252)
            if f is not None and XS[(ym, 252)] is not None: byy[ym[:4]].append(f - XS[(ym, 252)])
        for y in sorted(byy): P("        %s n=%d 中位 %s 勝 %s%%" % (y, len(byy[y]), f1(med(byy[y])), f1(100 * sum(1 for x in byy[y] if x > 0) / len(byy[y]))))
        P("      new_price 逐年（6 月、扣同月所有產業中位）：")
        byy = collections.defaultdict(list)
        for k, ym in ev:
            f = fwd(k, ym, 126)
            if f is not None and XS[(ym, 126)] is not None: byy[ym[:4]].append(f - XS[(ym, 126)])
        for y in sorted(byy): P("        %s n=%d 中位 %s 勝 %s%%" % (y, len(byy[y]), f1(med(byy[y])), f1(100 * sum(1 for x in byy[y] if x > 0) / len(byy[y]))))
# 等權全市場 vs 0050：市場層的差
xs = []
for ym in YMS:
    i0 = idx[AV[ym]]; i1 = i0 + 252
    if i1 >= len(cal): continue
    m = XS[(ym, 252)]
    if m is not None: xs.append(m - (c50[i1] / c50[i0] - 1) * 100)
P("  參考：「所有產業 12 月報酬中位」− 0050 同期：中位 %s、平均 %s（n=%d 個月）→ 等權產業指數整體輸 0050，所以「扣 0050」會低估 stage 事件、「扣同月產業中位」才是挑產業的能力" % (f1(med(xs)), f1(statistics.mean(xs)), len(xs)))
OUT.close()
open("stagetest/d_audit_out.txt", "a", encoding="utf-8").write(open("stagetest/d_audit_extra_out.txt", encoding="utf-8").read()) if os.path.exists("stagetest/d_audit_out.txt") and "--append" in sys.argv else None
