# -*- coding: utf-8 -*-
"""
把「作戰手冊」卡片加進 tw_radar.py 的「📌 今天要做什麼」頁最上面：
  Ⓐ 現在可以用的策略（9 個）和錢放哪    Ⓑ 每天／每月／每季的流程    Ⓒ 資金桶（可以自己改數字，存在瀏覽器）    Ⓓ 待辦清單（打勾會記住）
內容照 00money 的「系統總評_2026-11-05.md」「現在可以用的用法.md」「財報公布日重驗_解讀.md」。

用法：雙擊「作戰手冊加進雷達.bat」（只要跑一次；再跑會說已經加過）。會先備份 tw_radar.py.bak_playbook。
改完重新啟動雷達；兩台電腦只要在一台跑，Dropbox 會同步。
"""
import os, sys, io, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "tw_radar.py")
MARK = "tdPlaybookCard"

JS_FUNC = r'''/* ==================== 作戰手冊（2026-11-05）：可用策略、流程、資金桶、待辦 ==================== */
var PB_STRATS = [
  ['★ 基本面＋近一年高', '任一點位＋近 3 月均營收創 12 月高＋TTM EPS 成長＋收盤 ≥ 一年高 95%＋0050 季線上；13:25 掛收盤價買，抱 20 個交易日收盤賣；6 槽、不停損、不加碼', '★ 帳戶', '實單', '早年 18.3%／近年 44.9%，兩段都驗過'],
  ['景氣燈號調 0050 倍數', '藍／黃藍且分數回升 → 1.5 倍（正2）；綠燈轉弱 → 0.5 倍；其他 1 倍。每月底看第 ④ 張卡', '長期底倉', '上線', '1990 起三段都不輸'],
  ['季報意外獲利', '單季 EPS 轉虧為盈或意外大賺、公布前 20 天沒先漲 10%；期限後第 2 個交易日收盤買（11/05 重驗：改「公告隔天收盤買」更好，先紙上並行一季）、抱 16 天', '事件小帳戶 A（10%／筆）', '上線', '只有十年；每筆 +3.2%（實際日 +4.4%）'],
  ['信用交易恢復', '上季淨值 5～10、本季 ≥ 10；期限後第 1 個交易日收盤買、第 6 個交易日開盤賣。11/05 重驗：優勢就在期限後那 5 天，一個字都不要改', '事件小帳戶 A（5%／筆）', '上線', '只有十年；每筆 +4.3%、67% 賺'],
  ['MSCI 新增股', '公告當天收盤買、生效日收盤賣，一年 4 次', '事件小帳戶 B', '上線', '只有十年；11 年 9 年贏'],
  ['財報爆發跳空', '董事會通過財報、單季 EPS 真的爆發、公布後第一個開盤跳空 3～9.5%：當天收盤買、抱 20 天；最多 10 檔', '事件小帳戶 B（先紙上）', '紙上', '11/04 起紙上，滿 20～30 筆對得上回測再放錢'],
  ['新春行情', '封關日收盤買 0050、紅盤第 5 天收盤賣', '長期底倉的錢', '上線', '12 年 11 年正、平均 +3.1%'],
  ['底倉：0050 定期定值＋VTI／QQQ', '照現在的計畫；美國部位到 100 萬為止', '長期底倉', '進行中', '10 年以上才用的錢'],
  ['融資維持率 <140% 崩盤加碼', '操盤手 → 巨人傑：融資維持率 → 「加碼時點」卡片變「●」而且跌到 140% 以下或反彈 5 點：用崩盤加碼金買 0050、抱半年、不用融資', '崩盤加碼金', '觸發', '十年 4 次，120 天中位 +27%；是觸發不是策略']
];
var PB_FLOW = [
  ['每天 13:15', '看「① 今天要買」。有的話 13:25 掛收盤價（整張掛高一點、零股 13:29 前後）。沒有就不買。'],
  ['每天 13:30 後', '按「✓ 我買了／我賣了」。漏買 → 隔天收盤直接補，不等低價；收漲停買不到 → 跳過買下一個。'],
  ['每天 13:15', '看「② 今天要賣」：第 20 個交易日收盤賣，不早賣、不晚賣。'],
  ['每筆', '在「實際 vs 模擬」記成交價，順手算「成交價 − 收盤價」（滑價）。30 筆後就知道回測要打幾折。'],
  ['本月淨值 −5%', '★ 停開新倉到下個月（年化 +1.6 點、9/10 年）。連輸減半、回落減碼都不要。'],
  ['每月底', '第 ④ 張卡：景氣燈號幾倍，0050 底倉照它調。'],
  ['每季 5/15、8/14、11/14、3/31 前後', '事件小帳戶：季報意外獲利（財報公告隔天／期限後第 2 天）、信用交易恢復（期限後第 1 天買、第 6 天開盤賣）、MSCI（公告日）。'],
  ['崩盤時', '「加碼時點」卡片跌到 140% 以下才動崩盤加碼金；跌破 150 當天、第 10 天、<145 都不要動。'],
  ['任何時候都不做', '個股加碼、母子單、拉回加碼、再訊號加碼、★ 加停損停利、★ 加法人條件、空槽放 0050、事件策略合成一池、當沖（等 1 分 K 驗完）。']
];
var PB_BUCKETS = [
  ['reserve', '預備金（活存定存，不動）', 101.6], ['star', '★ 帳戶（6 槽，全照規則）', 55], ['evA', '事件小帳戶 A（0050 底＋季報意外獲利 10%／信用恢復 5%）', 25],
  ['evB', '事件小帳戶 B（0050 底＋財報爆發跳空，先紙上；MSCI 之後接進來）', 25], ['crash', '崩盤加碼金（現金，只在維持率 <140 或景氣藍燈時買 0050）', 30],
  ['core_tw', '長期底倉：0050（定期定值）', 29], ['core_us', '長期底倉：VTI／QQQ（每月續投到 100 萬）', 50.8], ['other', '規則外持股（泰合、台積電、台塑、00981A…每檔寫理由）', 31], ['fut', '期貨保證金（留最低，其餘回現金）', 20.4]
];
var PB_TODO = [
  ['t_cap', '定 ★ 帳戶大小（44～66 萬），到「實戰紀錄」把本金改成它、「實際下單每檔」改成 本金 ÷ 6；從那天起照股數買'],
  ['t_slip', '「實際 vs 模擬」每筆記成交價；滿 30 筆看滑價'],
  ['t_kill', '每個上線策略寫一句停用條件（例：★ 實單滿 30 筆後滾動 30 筆勝率 <35% → 退回紙上）'],
  ['t_dbx', 'Dropbox 只讓一台寫（另一台用瀏覽器連主機），清掉 data 裡的衝突複本'],
  ['t_1m', '兩台都再雙擊「下載個股分K.bat」直到它說全部抓完（流量上限會分幾天）'],
  ['t_bgap', '財報爆發跳空紙上滿 20～30 筆、對得上回測，再把事件小帳戶 B 的錢放進去'],
  ['t_xlev', '季報意外獲利「公告隔天收盤買」版先紙上並行一季，再決定要不要切'],
  ['t_us', '美股 12 檔個股：每檔寫下留的理由，沒有理由的賣掉併回 VTI'],
  ['t_other', '泰合、台積電、台塑、00981A：寫理由或併回底倉；帳本修華擎 −1 股、泰合成本'],
  ['t_fut', '期貨保證金 20.4 萬只留最低，其餘回活存']
];
function pbNum(k, dflt){ var v = parseFloat(store('pb_' + k)); return isFinite(v) ? v : dflt; }
function pbSet(k, v){ store('pb_' + k, String(v)); if(S.page === 'today') renderToday(); }
function pbTick(k, on){ store('pb_' + k, on ? '1' : '0'); if(S.page === 'today') renderToday(); }
function pbToggle(){ store('pb_open', store('pb_open') === '0' ? '1' : '0'); if(S.page === 'today') renderToday(); }
function pbTab(t){ store('pb_tab', t); if(S.page === 'today') renderToday(); }
function tdPlaybookCard(d){
  var open = store('pb_open') !== '0', tab = store('pb_tab') || 'buckets';
  var done = PB_TODO.filter(function(t){ return store('pb_' + t[0]) === '1'; }).length;
  var h = '<div class="tdcard" id="tdPb"><h3 style="cursor:pointer" onclick="pbToggle()">📘 作戰手冊<span class="sub">9 個可用策略・每天流程・資金桶・待辦 ' + done + '/' + PB_TODO.length + '　' + (open ? '▲ 收合' : '▼ 展開') + '</span></h3>';
  if(!open) return h + '</div>';
  var tabs = [['buckets', 'Ⓒ 資金桶'], ['strats', 'Ⓐ 可用策略'], ['flow', 'Ⓑ 流程'], ['todo', 'Ⓓ 待辦']];
  h += '<div class="ctrl" style="margin-bottom:10px"><span class="kseg">' + tabs.map(function(t){ return '<button' + (t[0] === tab ? ' class="on"' : '') + ' onclick="pbTab(\'' + t[0] + '\')">' + t[1] + '</button>'; }).join('') + '</span></div>';
  if(tab === 'strats'){
    h += '<div style="overflow:auto"><table class="sttbl"><tr><th>策略</th><th>做法</th><th>錢放哪</th><th>狀態</th><th>依據</th></tr>' +
      PB_STRATS.map(function(s){ return '<tr><td style="white-space:nowrap"><b>' + esc(s[0]) + '</b></td><td style="white-space:normal;min-width:320px;line-height:1.6">' + esc(s[1]) + '</td><td style="white-space:nowrap">' + esc(s[2]) + '</td><td>' + esc(s[3]) + '</td><td style="white-space:normal;min-width:160px" class="mut">' + esc(s[4]) + '</td></tr>'; }).join('') + '</table></div>' +
      '<div class="mut" style="font-size:12px;margin-top:6px;line-height:1.7">工具（不是策略）：DR 套利監控、台指期三兄弟價差、持股警示、美股 ETF 買哪邊。有條件可用：可轉債穿雲箭／CBAS、★ 多空版、季報 z 值。否決的不列（加碼、停損停利、法人條件、老白、台指期盤中、配對交易、D 配方…）。</div>';
  }else if(tab === 'flow'){
    h += '<table class="sttbl"><tr><th>什麼時候</th><th>做什麼</th></tr>' + PB_FLOW.map(function(f){ return '<tr><td style="white-space:nowrap"><b>' + esc(f[0]) + '</b></td><td style="white-space:normal;line-height:1.7">' + esc(f[1]) + '</td></tr>'; }).join('') + '</table>' +
      '<div class="mut" style="font-size:12px;margin-top:6px;line-height:1.7">上線節奏：紙上 → 實單 real_cap 3 檔 → 滿 20～30 筆對得上回測 → 6 檔。這才是「試單 → 壓滿」，單位是帳戶不是個股。新錢先進底倉和現金，策略帳戶只靠自己的獲利長大。</div>';
  }else if(tab === 'todo'){
    h += PB_TODO.map(function(t){ var on = store('pb_' + t[0]) === '1'; return '<label style="display:flex;gap:8px;align-items:flex-start;padding:5px 0;border-bottom:1px solid var(--line);line-height:1.6;cursor:pointer' + (on ? ';opacity:.55;text-decoration:line-through' : '') + '"><input type="checkbox"' + (on ? ' checked' : '') + ' onchange="pbTick(\'' + t[0] + '\', this.checked)" style="margin-top:5px">' + esc(t[1]) + '</label>'; }).join('') +
      '<div class="mut" style="font-size:12px;margin-top:6px">打勾只記在這台電腦的瀏覽器。Claude 那邊還在做：★ 候選排序、季報意外獲利「公告隔天買」版的帳戶模擬、基本面 1／D 早年、融資斷頭貨帳戶版、1 分 K 抓完後的當沖三招。</div>';
  }else{
    var tot = 0, eq = 0, vals = {};
    PB_BUCKETS.forEach(function(b){ var v = pbNum(b[0], b[2]); vals[b[0]] = v; tot += v; });
    eq = vals.star + vals.evA + vals.evB + vals.core_tw + vals.core_us + vals.other;
    var starEach = vals.star / 6, radarEach = d && d.each ? d.each / 1e4 : null;
    h += '<div style="overflow:auto"><table class="sttbl"><tr><th>桶</th><th>金額（萬）</th><th>每筆</th></tr>' +
      PB_BUCKETS.map(function(b){
        var v = vals[b[0]], each = '';
        if(b[0] === 'star') each = '每檔 ' + (v / 6).toFixed(1) + ' 萬';
        else if(b[0] === 'evA') each = '季報每筆 ' + (v / 10).toFixed(1) + ' 萬、信用恢復每筆 ' + (v / 20).toFixed(1) + ' 萬';
        else if(b[0] === 'evB') each = '每筆 ' + (v / 10).toFixed(1) + ' 萬';
        else if(b[0] === 'crash') each = '一次買 10～20% 總資產 = ' + (tot * 0.1).toFixed(0) + '～' + (tot * 0.2).toFixed(0) + ' 萬';
        return '<tr><td style="white-space:normal;min-width:260px">' + esc(b[1]) + '</td><td><input type="number" value="' + v + '" step="1" min="0" style="width:80px" onchange="pbSet(\'' + b[0] + '\', this.value)"></td><td class="mut" style="white-space:normal">' + each + '</td></tr>';
      }).join('') +
      '<tr style="background:var(--panel2)"><td><b>合計</b></td><td><b>' + tot.toFixed(1) + '</b></td><td class="mut">股票曝險 ' + eq.toFixed(0) + ' 萬（' + (tot ? Math.round(eq / tot * 100) : 0) + '%）；全部同跌 35% 那年總資產約 −' + (tot ? Math.round(eq * 0.35 / tot * 100) : 0) + '%</td></tr></table></div>';
    var warn = '';
    if(radarEach != null && Math.abs(radarEach - starEach) > 1) warn = '<div class="tdlu" style="margin-top:8px">⚠ 雷達「實戰紀錄」現在每檔算 ' + radarEach.toFixed(1) + ' 萬，跟上面 ★ 帳戶 ÷ 6 = ' + starEach.toFixed(1) + ' 萬不一樣。到「實戰紀錄」把本金改成 ' + vals.star + ' 萬、「實際下單每檔」改成 ' + starEach.toFixed(1) + ' 萬，13:15 的股數才會對。</div>';
    h += warn + '<div class="mut" style="font-size:12px;margin-top:6px;line-height:1.7">數字是 11/05 照「系統總評」的框架填的（總資產 330.6 萬、10/21 快照），改了會記在這台電腦的瀏覽器。原則：每個桶一個規則、一個帳戶、一張紀錄表，不互相借錢；睡不著的線如果是 −10%，★ 和事件帳戶各砍一半。這是整理，不是投資建議。</div>';
  }
  return h + '</div>';
}
'''

JS_ANCHOR = 'function renderToday(){\n'
JS_CALL_OLD = "box.innerHTML = '<div class=\"tdwrap\">' + head + c1 + c2 + c11"
JS_CALL_NEW = "box.innerHTML = '<div class=\"tdwrap\">' + head + tdPlaybookCard(d) + c1 + c2 + c11"


def main():
    if not os.path.exists(TARGET):
        print("  找不到 %s" % TARGET); return 1
    with io.open(TARGET, "r", encoding="utf-8") as f:
        src = f.read()
    if MARK in src:
        print("  已經加過了（tw_radar.py 裡有 %s）。重新啟動台股雷達就會看到卡片。" % MARK); return 0
    for nm, s in (("renderToday", JS_ANCHOR), ("卡片順序", JS_CALL_OLD)):
        c = src.count(s)
        if c != 1:
            print("  tw_radar.py 版本跟預期不同：%s 找到 %d 處（要剛好 1 處）。沒有改任何東西。" % (nm, c)); return 2
    bak = TARGET + ".bak_playbook"
    shutil.copyfile(TARGET, bak)
    out = src.replace(JS_ANCHOR, JS_FUNC + JS_ANCHOR, 1).replace(JS_CALL_OLD, JS_CALL_NEW, 1)
    try:
        compile(out, TARGET, "exec")
    except SyntaxError as e:
        print("  改完語法有錯（%s），沒有存檔。" % e); return 3
    with io.open(TARGET + ".tmp", "w", encoding="utf-8", newline="") as f:
        f.write(out)
    os.replace(TARGET + ".tmp", TARGET)
    print("  完成。備份在 %s" % os.path.basename(bak))
    print("  重新啟動台股雷達 → 「📌 今天要做什麼」最上面多一張「📘 作戰手冊」（資金桶、可用策略、流程、待辦）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
