# -*- coding: utf-8 -*-
"""
把「融資維持率跌破 150% 之後的加碼時點」加進 tw_radar.py（操盤手 → 巨人傑：融資維持率 那一頁，多一張卡片）。

做法：艾立克 2026-11 貼文的定義——上市融資維持率由 150% 以上跌破 150% 算一次事件，回到 158% 以上結束；
六個加碼時點（⑤跌破當天、④第 10 天、⑥第一次 <145、②第一次 <140、③<140 後反彈 5 點、①重新站回 150），
看加權指數之後 20／60／120 個交易日的報酬，跟「平常任意一天」比，另外用隨機抽樣算中位數不輸的機率。
全部用雷達自己的維持率序列（credit_bt.json）和加權指數（data/taiex_hist.json）重算，不用貼文的數字。

用法：雙擊「加碼時點加進雷達.bat」（只要跑一次；跑第二次會說已經加過）。
      會先備份成 tw_radar.py.bak_cr150，再修改。改完重新啟動台股雷達就會看到卡片，不用重抓資料。
"""
import os, sys, io, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "tw_radar.py")
MARK = "_cr_add150"

# ---------------------------------------------------------------- Python 端
PY_FUNC = r'''
CR150_TIM = [("t5", "⑤ 跌破 150% 當天"), ("t4", "④ 跌破 150% 後第 10 天"), ("t6", "⑥ 第一次跌到 145% 以下"),
             ("t2", "② 第一次跌到 140% 以下"), ("t3", "③ 跌到 140% 以下後反彈 5 點"), ("t1", "① 重新站回 150%")]


def _cr_add150(res, since="2016-01-01"):
    """艾立克（2026-11）的加碼時點：上市維持率由 150% 以上跌破 150% 算一次事件，回到 158% 以上結束。
    六個時點之後加權指數 20／60／120 日報酬，跟平常比。用自己的序列重算（他的維持率跟這裡的不是同一條線）。"""
    import random, bisect
    S = res.get("series") or []
    tx = (_jload(os.path.join(DATA_DIR, "taiex_hist.json"), {}) or {}).get("d") or {}
    if not S:
        return {"err": "沒有維持率序列"}
    if not tx:
        return {"err": "需要 data/taiex_hist.json（加權指數日收盤；ETF 申贖那一頁更新時會抓）"}
    m, dates = {}, []
    for r in S:
        if r[1] is not None:
            dates.append(r[0]); m[r[0]] = r[1]
    if len(dates) < 50:
        return {"err": "維持率序列太短"}
    txd = sorted(d for d in tx if d >= dates[0])
    txi = dict((d, i) for i, d in enumerate(txd))

    def fwd(d, n):
        if d is None:
            return None
        if d not in txi:
            j = bisect.bisect_left(txd, d)
            if j >= len(txd):
                return None
            d = txd[j]
        i = txi[d]
        if i + n >= len(txd):
            return None
        return (tx[txd[i + n]] / tx[d] - 1) * 100

    eps, i, n = [], 1, len(dates)
    while i < n:
        d = dates[i]
        if m[d] < 150 and m[dates[i - 1]] >= 150 and d >= since:
            ep = {"start": d, "lo": m[d], "lod": d, "t5": d, "t4": None, "t6": None, "t2": None, "t3": None, "t1": None, "end": None}
            j = i
            while j < n and m[dates[j]] < 158:
                v, dj = m[dates[j]], dates[j]
                if v < ep["lo"]:
                    ep["lo"], ep["lod"] = v, dj
                if ep["t6"] is None and v < 145:
                    ep["t6"] = dj
                if ep["t2"] is None and v < 140:
                    ep["t2"] = dj
                if ep["t2"] is not None and ep["t3"] is None and dj > ep["t2"] and v >= ep["lo"] + 5:
                    ep["t3"] = dj
                if ep["t1"] is None and dj > d and v >= 150:
                    ep["t1"] = dj
                if j == i + 10:
                    ep["t4"] = dj
                j += 1
            if j < n:
                ep["end"] = dates[j]
                if ep["t1"] is None:
                    ep["t1"] = dates[j]
            ep["lo"] = round(ep["lo"], 1)
            ep["r"] = dict((k, [(round(fwd(ep[k], N), 1) if fwd(ep[k], N) is not None else None) for N in (20, 60, 120)]) for k, _ in CR150_TIM)
            eps.append(ep)
            i = j + 1
        else:
            i += 1
    # 底線：同期間任意一天
    base, rng = {}, random.Random(1)
    for N in (20, 60, 120):
        v = [fwd(d, N) for d in txd if d >= since]
        v = [x for x in v if x is not None]
        v.sort()
        base[N] = v
    def med(v):
        v = sorted(v); k = len(v)
        return (v[k // 2] if k % 2 else (v[k // 2 - 1] + v[k // 2]) / 2.0) if k else None
    stat = {}
    for k, lab in CR150_TIM:
        row = {}
        for N in (20, 60, 120):
            xs = [fwd(e[k], N) for e in eps if e.get(k)]
            xs = [x for x in xs if x is not None]
            if not xs:
                row[str(N)] = None
                continue
            md, bs = med(xs), base[N]
            p = None
            if bs and len(bs) > len(xs) * 3:
                cnt, T = 0, 1500
                for _ in range(T):
                    if med(rng.sample(bs, len(xs))) >= md:
                        cnt += 1
                p = round(cnt * 100.0 / T)
            row[str(N)] = {"n": len(xs), "win": round(sum(1 for x in xs if x > 0) * 100.0 / len(xs)), "med": round(md, 1),
                           "avg": round(sum(xs) / len(xs), 1), "worst": round(min(xs), 1), "p": p}
        stat[k] = row
    base_out = dict((str(N), {"n": len(v), "win": (round(sum(1 for x in v if x > 0) * 100.0 / len(v)) if v else None),
                              "med": (round(med(v), 1) if v else None), "avg": (round(sum(v) / len(v), 1) if v else None)}) for N, v in base.items())
    # 今天的狀態
    last_d, last_v = dates[-1], m[dates[-1]]
    st = {"d": last_d, "v": last_v, "state": "none", "txt": ""}
    cur = eps[-1] if (eps and eps[-1]["end"] is None) else None
    if cur is None:
        st["txt"] = "今天 %.1f%%，沒有在事件裡（要先由 150%% 以上跌破 150%% 才開始算；離 150%% 還有 %.1f 點）。" % (last_v, last_v - 150)
    else:
        st["state"] = "in"
        st["ep"] = cur
        days_in = dates.index(last_d) - dates.index(cur["start"])
        hit = [lab for k, lab in CR150_TIM if cur.get(k)]
        nxt = []
        if cur["t2"] is None:
            nxt.append("② 跌到 140%% 以下（還差 %.1f 點）" % (last_v - 140))
        elif cur["t3"] is None:
            nxt.append("③ 由最低 %.1f%% 反彈 5 點（到 %.1f%%）" % (cur["lo"], cur["lo"] + 5))
        if cur["t1"] is None:
            nxt.append("① 站回 150%%（還差 %.1f 點）" % (150 - last_v))
        st["txt"] = "事件進行中：%s 跌破 150%%，到今天第 %d 天，最低 %.1f%%（%s），今天 %.1f%%。已出現：%s。還沒出現：%s。回到 158%% 以上這段才結束。" % (
            cur["start"], days_in, cur["lo"], cur["lod"], last_v, "、".join(hit) if hit else "—", "、".join(nxt) if nxt else "—")
    return {"since": since, "n": len(eps), "eps": eps, "stat": stat, "base": base_out, "today": st, "tx_last": txd[-1] if txd else None}


'''

PY_CALL_OLD = '    res["concl"] = _cr_concl(res)\n    _jsave(os.path.join(DATA_DIR, CR_RES), res)\n'
PY_CALL_NEW = ('    try:\n        res["add150"] = _cr_add150(res)\n    except Exception as e:\n        res["add150"] = {"err": "%s: %s" % (type(e).__name__, str(e)[:160])}\n'
               '    res["concl"] = _cr_concl(res)\n    _jsave(os.path.join(DATA_DIR, CR_RES), res)\n')

PY_CONCL_OLD = '    b2 = res.get("b2") or {}\n    for var, lab in CR_VAR:\n'
PY_CONCL_NEW = ('    a = res.get("add150") or {}\n'
                '    if a.get("stat"):\n'
                '        s2 = (a["stat"].get("t2") or {}).get("120"); s1 = (a["stat"].get("t1") or {}).get("120"); b120 = (a.get("base") or {}).get("120") or {}\n'
                '        if s2 and s1:\n'
                '            out.append("加碼時點（艾立克的六個時點，用自己的序列重算）：%s 起維持率跌破 150%% 有 %d 段；「第一次跌到 140%% 以下」買加權 120 天後中位 %+.1f%%（%d%% 賺，%d 次），「重新站回 150%%」%+.1f%%（%d%% 賺，%d 次），平常任意一天 %+.1f%%（%d%% 賺）。次數很少，只能當參考。"\n'
                '                       % (a.get("since", "")[:4], a.get("n", 0), s2["med"], s2["win"], s2["n"], s1["med"], s1["win"], s1["n"], b120.get("med") or 0, b120.get("win") or 0))\n'
                '        if (a.get("today") or {}).get("state") == "in":\n'
                '            out.append("現在：" + a["today"]["txt"])\n'
                '    b2 = res.get("b2") or {}\n    for var, lab in CR_VAR:\n')

PY_PAYLOAD_OLD = 'def cr10_payload(slim=False):\n    res = _jload(os.path.join(DATA_DIR, CR_RES), {}) or {}\n'
PY_PAYLOAD_NEW = ('def cr10_payload(slim=False):\n    res = _jload(os.path.join(DATA_DIR, CR_RES), {}) or {}\n'
                  '    if res.get("series") and not res.get("add150"):\n'
                  '        try:\n            res["add150"] = _cr_add150(res)\n        except Exception as e:\n            res["add150"] = {"err": str(e)[:160]}\n')

# ---------------------------------------------------------------- 網頁端
JS_FUNC = r'''function crAdd150HTML(res){
  var a = res.add150 || {};
  var sub = '上市維持率由 150% 以上跌破 150% 算一段，回到 158% 以上結束；六個時點之後買加權指數，看 20／60／120 個交易日。全部用這裡自己的維持率序列重算';
  if(a.err) return smCard('加碼時點（艾立克：維持率跌破 150% 的每一段）', sub, '<div class="emptybox">' + esc(a.err) + '</div>');
  if(!a.stat) return '';
  var TIM = [['t5', '⑤ 跌破 150% 當天'], ['t4', '④ 跌破 150% 後第 10 天'], ['t6', '⑥ 第一次跌到 145% 以下'], ['t2', '② 第一次跌到 140% 以下'], ['t3', '③ 跌到 140% 以下後反彈 5 點'], ['t1', '① 重新站回 150%']];
  var t = a.today || {};
  var h = '<div style="padding:4px 0 8px;font-size:13.5px;line-height:1.7"><b style="color:' + (t.state === 'in' ? 'var(--warn)' : 'var(--good)') + '">' + (t.state === 'in' ? '● 事件進行中' : '○ 沒有事件') + '</b>　' + esc(t.txt || '') + '</div>';
  h += '<div style="overflow:auto"><table class="sttbl"><tr><th>加碼時點</th>' + [20, 60, 120].map(function(N){ return '<th>買加權，' + N + ' 天後<br><span class="mut" style="font-weight:400">次數／賺的比例／中位數／平均／最差</span></th>'; }).join('') + '</tr>';
  TIM.forEach(function(z){
    var row = a.stat[z[0]] || {};
    h += '<tr' + (z[0] === 't2' || z[0] === 't3' ? ' style="background:var(--accent-soft)"' : '') + '><td style="white-space:nowrap"><b>' + esc(z[1]) + '</b></td>' + [20, 60, 120].map(function(N){
      var s = row[String(N)];
      if(!s) return '<td class="mut">—</td>';
      var b = (a.base || {})[String(N)] || {};
      var cls = (b.med != null && s.med > b.med) ? 'pos' : 'neg';
      return '<td><span class="mut">' + s.n + ' 次</span>　' + s.win + '%　<b class="' + cls + '">' + (s.med > 0 ? '+' : '') + s.med.toFixed(1) + '%</b>　' + crPc(s.avg, 1) + '　<span class="mut">' + crPc(s.worst, 1) + '</span>' +
        (s.p != null ? '<br><span class="mut" style="font-size:11px">隨機抽 ' + s.n + ' 天，中位數不輸它的機率 ' + s.p + '%</span>' : '') + '</td>';
    }).join('') + '</tr>';
  });
  h += '<tr style="background:var(--panel2)"><td>平常任意一天</td>' + [20, 60, 120].map(function(N){ var b = (a.base || {})[String(N)] || {}; return '<td>' + (b.med != null ? '<span class="mut">' + (b.n || 0).toLocaleString() + ' 天</span>　' + b.win + '%　<b>' + (b.med > 0 ? '+' : '') + b.med.toFixed(1) + '%</b>　' + crPc(b.avg, 1) : '—') + '</td>'; }).join('') + '</tr></table></div>';
  var eps = a.eps || [];
  if(eps.length){
    h += '<h4 class="lnyh">每一段（' + esc(String(a.since || '').slice(0, 4)) + ' 年起，共 ' + eps.length + ' 段）</h4><div style="overflow:auto"><table class="sttbl" style="font-size:12px"><tr><th>跌破 150%</th><th>回到 158%</th><th>最低</th><th>最低那天</th><th>第一次 &lt;145</th><th>第一次 &lt;140</th><th>反彈 5 點</th><th>站回 150</th><th>② 起 60 天</th><th>② 起 120 天</th><th>① 起 60 天</th><th>① 起 120 天</th></tr>' +
      eps.slice().reverse().map(function(e){ var r = e.r || {}; var r2 = r.t2 || [], r1 = r.t1 || [];
        return '<tr><td>' + esc(e.start) + '</td><td>' + esc(e.end || '（還在）') + '</td><td>' + crRatio(e.lo) + '</td><td>' + esc(e.lod || '') + '</td><td>' + esc(e.t6 || '—') + '</td><td>' + esc(e.t2 || '—') + '</td><td>' + esc(e.t3 || '—') + '</td><td>' + esc(e.t1 || '—') + '</td><td>' + crPc(r2[1]) + '</td><td>' + crPc(r2[2]) + '</td><td>' + crPc(r1[1]) + '</td><td>' + crPc(r1[2]) + '</td></tr>'; }).join('') + '</table></div>';
  }
  h += '<div class="mut" style="font-size:11.5px;margin-top:6px;line-height:1.7">報酬＝加權指數收盤到收盤，未扣成本、不含股息。艾立克貼文（2026-11）用的維持率跟這裡不是同一條線（他的 2026-07 低點在 135% 以下、11 月初 142%；這裡同一天是 157%、165%），所以他的 14 次在這裡只有 ' + eps.length + ' 段，門檻數字不能直接搬過來，只能看方向。' +
    '跌到 140% 以下的那幾段（2020-03、2022-07、2022-10、2025-04）就是這十年每次崩盤的底，120 天後都是漲的；但只有 4 次，而且這十年是多頭，「隨機抽同樣天數的中位數不輸它的機率」才是該看的數字。這是歷史統計，不是買賣建議。</div>';
  return smCard('加碼時點（艾立克：維持率跌破 150% 的每一段）', sub, '<div style="padding:8px 14px 10px">' + h + '</div>');
}
'''

JS_ANCHOR_OLD = 'function msCr(){\n'
JS_CALL_OLD = 'crTodayHTML(res) + crCandsHTML(res) + crB1HTML(res)'
JS_CALL_NEW = 'crTodayHTML(res) + crAdd150HTML(res) + crCandsHTML(res) + crB1HTML(res)'


def main():
    if not os.path.exists(TARGET):
        print("  找不到 %s" % TARGET); return 1
    with io.open(TARGET, "r", encoding="utf-8") as f:
        src = f.read()
    if MARK in src:
        print("  已經加過了（tw_radar.py 裡有 %s）。重新啟動台股雷達就會看到卡片。" % MARK); return 0
    need = [("Python 存檔處", PY_CALL_OLD), ("Python 結論", PY_CONCL_OLD), ("Python payload", PY_PAYLOAD_OLD), ("網頁 msCr", JS_ANCHOR_OLD), ("網頁卡片順序", JS_CALL_OLD), ("Python 函式位置", "\ndef _cr_concl(res):\n")]
    for nm, s in need:
        c = src.count(s)
        if c != 1:
            print("  tw_radar.py 版本跟預期不同：%s 找到 %d 處（要剛好 1 處）。沒有改任何東西。" % (nm, c)); return 2
    bak = TARGET + ".bak_cr150"
    shutil.copyfile(TARGET, bak)
    out = src.replace("\ndef _cr_concl(res):\n", PY_FUNC + "def _cr_concl(res):\n", 1)
    out = out.replace(PY_CALL_OLD, PY_CALL_NEW, 1)
    out = out.replace(PY_CONCL_OLD, PY_CONCL_NEW, 1)
    out = out.replace(PY_PAYLOAD_OLD, PY_PAYLOAD_NEW, 1)
    out = out.replace(JS_ANCHOR_OLD, JS_FUNC + JS_ANCHOR_OLD, 1)
    out = out.replace(JS_CALL_OLD, JS_CALL_NEW, 1)
    try:
        compile(out, TARGET, "exec")
    except SyntaxError as e:
        print("  改完語法有錯（%s），沒有存檔。" % e); return 3
    with io.open(TARGET + ".tmp", "w", encoding="utf-8", newline="") as f:
        f.write(out)
    os.replace(TARGET + ".tmp", TARGET)
    print("  完成。備份在 %s" % os.path.basename(bak))
    print("  重新啟動台股雷達 → 操盤手 → 「巨人傑：融資維持率」，大盤維持率卡片下面多一張「加碼時點」。")
    print("  不用重抓資料；下次按「抓十年融資資料＋回測」時結論裡也會多一行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
