"""優分析 CH1 可量化規則（10 年、季報快取 mopsfin ＋ k10y ＋ rev10）：
 V1 ROIC 拐點（連升 2 季、起點是 8 季低點）  V2 ROIC 創 8 季新高  V3 資產年增 ≥ 25%（資本支出代理）
 V4 量價齊揚（單季營收 yoy ≥ 20%、毛利率 +2 點、營益率升）  V5 量增期槓桿（營收 ≥ 20%、毛利率持平、營益率 +1 點）
 V6 超額利潤消失（營收 TTM ≥ 10%、毛利金額增幅落後營收 5 點以上）＝課程的賣訊，預期要輸
訊號日＝法定公布期限後第一個交易日收盤；每個再加「60 日比 0050 多 20 點」（MGK 先漲）。
量：60 天超額（vs 0050）中位／平均／勝率；帳戶模擬 10 槽 × 10%、閒錢 0050 含息、抱 60 天。"""
import json,glob,os,pickle,bisect,random,statistics,collections,sys
exec(open('mgk_test.py').read().split('b = run([])')[0])
from datetime import date
F=collections.defaultdict(dict)   # F[code][q] = row (累計)
for f in glob.glob('mopsfin/mopsfin_*.json'):
    nm=os.path.basename(f)[:-5].split('_'); q="%dQ%s"%(int(nm[2])+1911,nm[3])
    for c,r in json.load(open(f))['rows'].items():
        F[c][q]=r
def qprev(q,k=1):
    y,n=int(q[:4]),int(q[5]); n-=k
    while n<=0: n+=4; y-=1
    return "%dQ%d"%(y,n)
def num(x): return float(x) if isinstance(x,(int,float)) else None
def cum(c,q,k):
    r=F[c].get(q); return num(r.get(k)) if r else None
def ttm(c,q,k):
    """近四季合計（用累計算，不怕缺單季）"""
    a=cum(c,q,k); n=int(q[5])
    if a is None: return None
    if n==4: return a
    y4=cum(c,"%dQ4"%(int(q[:4])-1),k); ly=cum(c,qprev(q,4),k)
    if y4 is None or ly is None: return None
    return a+y4-ly
def single(c,q,k):
    a=cum(c,q,k); n=int(q[5])
    if a is None: return None
    if n==1: return a
    p=cum(c,qprev(q),k); return (a-p) if p is not None else None
def roic(c,q):
    op=ttm(c,q,'op'); a=cum(c,q,'assets'); cl=cum(c,q,'cl')
    if op is None or a is None or cl is None or a-cl<=0: return None
    return op/(a-cl)*100
def due(q):
    y,n=int(q[:4]),int(q[5]); return date(y+1,3,31).isoformat() if n==4 else [None,date(y,5,15),date(y,8,14),date(y,11,14)][n].isoformat()
def first_td_after(ds):
    i=bisect.bisect_right(cal,ds); return cal[i] if i<len(cal) else None
def gm(c,q):
    g,v=single(c,q,'gross'),single(c,q,'rev')
    return g/v*100 if (g is not None and v) else None
def opm(c,q):
    o,v=single(c,q,'op'),single(c,q,'rev')
    return o/v*100 if (o is not None and v) else None
SIG=collections.defaultdict(list)
n_eval=0
for c in F:
    if c not in px or c.startswith('00'): continue
    for q in sorted(F[c]):
        d=first_td_after(due(q))
        if not d or d<'2016-06-01' or d>cal[-61]: continue
        s=px[c]; i=idx[d]; bar=s.get(d)
        if not bar or i<60: continue
        b60=s.get(cal[i-60])
        if not b60 or not c50[i] or not c50[i-60]: continue
        vols=[s[x][4] for x in cal[i-20:i] if x in s]
        if len(vols)<15 or sum(vols)/20<500 or bar[3]<10: continue
        pb=s.get(cal[i-1])
        if pb and bar[3]>=pb[3]*1.094 and bar[3]>=bar[1]*0.999: continue
        r60x=(bar[3]/b60[3]-1)*100-(c50[i]/c50[i-60]-1)*100
        # 事後 60 天
        j=i+60; e=close_near(c,cal[j]); 
        if not e: continue
        fx=(e/bar[3]-1)*100-(c50[j]/c50[i]-1)*100
        base=dict(code=c,d=d,px=bar[3],r60x=r60x,fx=fx,q=q,yoy=0)
        n_eval+=1
        SIG['ALL'].append(base)
        R=[roic(c,qprev(q,k)) for k in range(10)]
        rv=ttm(c,q,'rev'); rvl=ttm(c,qprev(q,4),'rev'); ryoy=(rv/rvl-1)*100 if (rv and rvl) else None
        if None not in R[:3] and R[0]>R[1]>R[2] and R[0]>0 and None not in R[2:10] and R[2]<=min(R[2:10]):
            SIG['V1'].append(base)
        if None not in R[:9] and R[0]>max(R[1:9]) and R[0]>0:
            SIG['V2'].append(base)
            if R[0]<20: SIG['V2b'].append(base)
        if R[0] is not None and R[0]>=40:
            SIG['V7'].append(base)
        if R[0] is not None and 0<R[0]<8:
            SIG['V8'].append(base)
        a,al=cum(c,q,'assets'),cum(c,qprev(q,4),'assets')
        if a and al and a/al-1>=0.25 and ryoy is not None and ryoy>0 and R[0] is not None and R[0]>0:
            SIG['V3'].append(base)
        sv,svl=single(c,q,'rev'),single(c,qprev(q,4),'rev'); g,gl=gm(c,q),gm(c,qprev(q,4)); o,ol=opm(c,q),opm(c,qprev(q,4))
        if sv and svl and g is not None and gl is not None and o is not None and ol is not None:
            syoy=(sv/svl-1)*100
            if syoy>=20 and g-gl>=2 and o>ol: SIG['V4'].append(base)
            if syoy>=20 and abs(g-gl)<1 and o-ol>=1: SIG['V5'].append(base)
        gp,gpl=ttm(c,q,'gross'),ttm(c,qprev(q,4),'gross')
        if ryoy is not None and ryoy>=10 and gp is not None and gpl and gpl>0 and (gp/gpl-1)*100<ryoy-5:
            SIG['V6'].append(base)
NM={'ALL':'全部季報（基準）','V1':'ROIC 拐點（連升 2 季、起點 8 季低）','V2':'ROIC 創 8 季新高','V3':'資產年增 ≥25%＋營收成長（擴產代理）','V4':'量價齊揚（營收+20%、毛利率+2 點、營益率升）','V5':'量增期槓桿（營收+20%、毛利率平、營益率+1 點）','V6':'超額利潤消失（賣訊，預期輸）','V2b':'ROIC 創 8 季新高且還沒過高（<20%）','V7':'ROIC 過高（≥40%，實體課：小心 BOM 表壓力）','V8':'ROIC 偏低（0～8%，對照）'}
print("評估的季報×個股",n_eval)
b=run([]); print("0050 含息：年化 %.1f%% 回撤 %.1f%%"%(b['cagr'],b['mdd']))
def stat(S):
    if not S: return "—"
    f=[s['fx'] for s in S]; h1=[s['fx'] for s in S if s['d']<'2021-07-01']; h2=[s['fx'] for s in S if s['d']>='2021-07-01']
    def m(L): return statistics.median(L) if L else float('nan')
    return "n %5d  60 日超額 中位 %+.2f 平均 %+.2f 勝 0050 %.0f%%  前半中位 %+.2f(%d) 後半 %+.2f(%d)"%(len(S),m(f),statistics.mean(f),100*sum(1 for x in f if x>0)/len(f),m(h1),len(h1),m(h2),len(h2))
print("\n== 事件統計（買進日收盤 → 60 個交易日後，扣 0050 同期）==")
for k in ['ALL','V1','V2','V2b','V7','V8','V3','V4','V5','V6']:
    S=SIG[k]; print("%-40s %s"%(NM[k],stat(S)))
    print("%-40s %s"%("   ＋先漲 >20 點",stat([s for s in S if s['r60x']>20])))
    print("%-40s %s"%("   落後 0050（r60x ≤ 0）",stat([s for s in S if s['r60x']<=0])))
print("\n== 帳戶模擬（10 槽 × 10%、閒錢 0050 含息、抱 60 天、成本 0.47%）==")
for k in ['V1','V2','V2b','V7','V3','V4','V5']:
    for lab,S in ((NM[k],SIG[k]),("   ＋先漲 >20 點",[s for s in SIG[k] if s['r60x']>20])):
        if len(S)<30: print("%s：筆數 %d 太少"%(lab,len(S))); continue
        r=run(S); rs=sorted(run(S,seed=x)['cagr'] for x in range(30)); h1=run(S,end="2021-06-30"); h2=run(S,start="2021-07-01")
        print("%s：年化 %.1f%% 回撤 %.1f%% 筆數 %d 每筆 %+.2f%% 勝率 %.0f%%；隨機 30 次中位 %.1f%%（%.1f～%.1f）；前半 %.1f%% 後半 %.1f%%；贏 0050 年數 %d/%d"%(lab,r['cagr'],r['mdd'],r['n'],r['avg'],r['win'],rs[15],rs[0],rs[-1],h1['cagr'],h2['cagr'],sum(1 for y,v in r['yr'].items() if v>b['yr'].get(y,0)),len(r['yr'])))
        print("     逐年 "+" ".join("%s %+.0f"%(y[2:],v) for y,v in r['yr'].items()))
