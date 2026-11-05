"""循環課「剛進入價漲期」當獨立策略（＋MGK 的股價先動）：2016～2026，k10y＋rev10＋季報快取（毛利率）。
價漲期＝近 3 月營收年增 ≥ 10% 且 最新一季累計毛利率比去年同期高 ≥ 1.5 點；剛進入＝3 個月前不是價漲期。
每月 11 日後第一個交易日收盤買、抱 60 天；10 槽 × 10%、閒錢放 0050 含息。"""
import json,glob,os,pickle,bisect,random,statistics,collections
exec(open('mgk_test.py').read().split('b = run([])')[0])   # 借資料載入、run()、close_near()
# 季報毛利率（累計）：{code:{q:margin}}
GM=collections.defaultdict(dict)
for f in glob.glob('mopsfin/mopsfin_*.json'):
    nm=os.path.basename(f)[:-5].split('_'); q="%dQ%s"%(int(nm[2])+1911,nm[3])
    for c,r in json.load(open(f))['rows'].items():
        g,v=r.get('gross'),r.get('rev')
        if isinstance(g,(int,float)) and isinstance(v,(int,float)) and v>0: GM[c][q]=g/v*100
from datetime import date
def due(q):
    y,n=int(q[:4]),int(q[5]); return date(y+1,3,31).isoformat() if n==4 else [None,date(y,5,15),date(y,8,14),date(y,11,14)][n].isoformat()
def latest_q(c,d):
    best=None
    for q in sorted(GM.get(c,{})):
        if due(q)<d: best=q
    return best
def stage(c,ym,d):
    """回傳 'up'（價漲期）或其他"""
    R=rev.get(c,{}); l3=[R.get(ym_prev(ym,j)) for j in range(3)]; y3=[R.get(ym_prev(ym,12+j)) for j in range(3)]
    if None in l3 or None in y3 or sum(y3)<=0: return None
    yoy=(sum(l3)/sum(y3)-1)*100
    q=latest_q(c,d)
    if not q: return None
    ly="%dQ%s"%(int(q[:4])-1,q[5]); g,gl=GM[c].get(q),GM[c].get(ly)
    if g is None or gl is None: return None
    return 'up' if (yoy>=10 and g-gl>=1.5) else ('vol' if yoy>=10 else ('down' if yoy<0 else 'flat'))
sig=[]; n_stage=collections.Counter()
for c in rev:
    if c not in px or c.startswith('00'): continue
    for ym in sorted(rev[c]):
        d=avail(ym)
        if not d or d<'2016-06-01': continue
        st=stage(c,ym,d)
        if st!='up': continue
        d3=avail(ym_prev(ym,3)); st3=stage(c,ym_prev(ym,3),d3) if d3 else None
        if st3=='up' or st3 is None: continue
        s=px[c]; i=idx[d]; bar=s.get(d)
        if not bar or i<60: continue
        b60=s.get(cal[i-60])
        if not b60 or not c50[i] or not c50[i-60]: continue
        vols=[s[x][4] for x in cal[i-20:i] if x in s]
        if len(vols)<15 or sum(vols)/20<500 or bar[3]<10: continue
        pb=s.get(cal[i-1])
        if pb and bar[3]>=pb[3]*1.094 and bar[3]>=bar[1]*0.999: continue
        r60x=(bar[3]/b60[3]-1)*100-(c50[i]/c50[i-60]-1)*100
        sig.append(dict(code=c,d=d,px=bar[3],r60x=r60x,yoy=0))
print("剛進入價漲期訊號", len(sig), "其中股價先漲 >20 點", sum(1 for s in sig if s['r60x']>20))
b=run([]); print("0050 含息：年化 %.1f%% 回撤 %.1f%%"%(b['cagr'],b['mdd']))
for nm,S in (("剛進入價漲期（全部）",sig),("剛進入價漲期＋60 日比 0050 多 20 點",[s for s in sig if s['r60x']>20]),("剛進入價漲期＋60 日比 0050 多 0 點以上",[s for s in sig if s['r60x']>0]),("剛進入價漲期＋60 日落後 0050（沒先漲）",[s for s in sig if s['r60x']<=0])):
    r=run(S); rs=sorted(run(S,seed=k)['cagr'] for k in range(30)); h1=run(S,end="2021-06-30"); h2=run(S,start="2021-07-01")
    print("%s：年化 %.1f%% 回撤 %.1f%% 筆數 %d 每筆 %+.2f%% 勝率 %.0f%%；隨機中位 %.1f%%（%.1f～%.1f）；前半 %.1f%% 後半 %.1f%%；贏 0050 年數 %d/%d"%(nm,r['cagr'],r['mdd'],r['n'],r['avg'],r['win'],rs[15],rs[0],rs[-1],h1['cagr'],h2['cagr'],sum(1 for y,v in r['yr'].items() if v>b['yr'].get(y,0)),len(r['yr'])))
