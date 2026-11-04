# -*- coding: utf-8 -*-
# 獨立重算版（給 scratchpad 用）：python3 cr150_check.py [欄位 1=上市 3=全市場] [起始日]；需要 credit_bt.json、dl/taiex_hist.json、tr50.pkl、px.pkl
"""重做艾立克貼文：融資維持率由150以上跌破150→回到158以上算一次事件；6 種加碍時點，看加權指數 20/60/120 日報酬。"""
import json,statistics,random,sys,pickle
cb=json.load(open('credit_bt.json'))
S=cb['series']                    # [date, sii, otc, all, cover, k, n]
tx=json.load(open('dl/taiex_hist.json'))['d']
tr50=pickle.load(open('tr50.pkl','rb'))[0]
pxd=pickle.load(open('px.pkl','rb'))[1]
TR={d:v for d,v in zip(pxd,tr50) if v==v}
dates=[r[0] for r in S]; mr={r[0]:r[1] for r in S}
txd=sorted(k for k in tx if k>='2016-01-01'); txi={d:i for i,d in enumerate(txd)}
def fwd(d,n,src='tx'):
    """由日期 d 收盤買，n 個交易日後收盤報酬 %"""
    if src=='tx':
        if d not in txi: 
            # 找下一個有指數的日子
            c=[x for x in txd if x>=d]; 
            if not c: return None
            d=c[0]
        i=txi[d]
        if i+n>=len(txd): return None
        return (tx[txd[i+n]]/tx[d]-1)*100
    else:
        ks=sorted(k for k in TR if k>=d)
        if not ks: return None
        i=ks.index(ks[0]); 
        if i+n>=len(ks): return None
        return (TR[ks[i+n]]/TR[ks[0]]-1)*100
COL=int(sys.argv[1]) if len(sys.argv)>1 else 1   # 1=上市 3=全市場
since=sys.argv[2] if len(sys.argv)>2 else '2018-01-01'
m={r[0]:r[COL] for r in S}
eps=[]; i=0
while i<len(dates):
    d=dates[i]
    if m[d]<150 and i>0 and m[dates[i-1]]>=150 and d>=since:
        ep={'start':d,'idx':i}
        j=i; lo=1e9; lod=None; f140=None; f145=None; rb5=None; back150=None; d10=None
        while j<len(dates) and m[dates[j]]<158:
            v=m[dates[j]]
            if v<lo: lo=v; lod=dates[j]
            if f145 is None and v<145: f145=dates[j]
            if f140 is None and v<140: f140=dates[j]
            if f140 is not None and rb5 is None and v>=lo+5 and dates[j]>f140: rb5=dates[j]
            if back150 is None and v>=150 and dates[j]>d: back150=dates[j]
            if j==i+10: d10=dates[j]
            j+=1
        ep.update(end=dates[j] if j<len(dates) else None, lo=lo, lod=lod, f145=f145, f140=f140, rb5=rb5, back150=back150, d10=d10 if d10 else (dates[min(i+10,len(dates)-1)]))
        if back150 is None:
            # 事件結束(≥158)那天本身就是站回150
            ep['back150']=dates[j] if j<len(dates) else None
        eps.append(ep); i=j+1
    else: i+=1
print("序列欄位 %s，%s 起：%d 次事件"%("上市" if COL==1 else "全市場", since, len(eps)))
for e in eps: print("  %s→%s 最低 %.1f(%s)  <145:%s <140:%s 反彈5:%s 站回150:%s"%(e['start'],e['end'],e['lo'],e['lod'],e['f145'],e['f140'],e['rb5'],e['back150']))
TIM=[('⑤跌破150當天','start'),('④跌破150後第10天','d10'),('⑥第一次<145','f145'),('②第一次<140','f140'),('③<140後反彈5點','rb5'),('①重新站回150','back150')]
print("\n各時點 加權指數 報酬（勝率 / 中位 / 平均；n）")
out={}
for nm,k in TIM:
    row=[]
    for h in (20,60,120):
        xs=[fwd(e[k],h) for e in eps if e.get(k)]; xs=[x for x in xs if x is not None]
        row.append(xs)
    out[nm]=row
    print("  %-14s "%nm + " | ".join("%dd 勝%3.0f%% 中%+5.1f%% 均%+5.1f%% n=%d"%(h,100*sum(x>0 for x in xs)/len(xs),statistics.median(xs),statistics.mean(xs),len(xs)) if xs else "%dd n=0"%h for h,xs in zip((20,60,120),row)))
# 無條件底線（同期間）
print("\n同期間任意一天買進（底線）")
base={}
for h in (20,60,120):
    xs=[fwd(d,h) for d in txd if d>=since]; xs=[x for x in xs if x is not None]; base[h]=xs
    print("  %dd 勝%.0f%% 中%+.1f%% 均%+.1f%% n=%d"%(h,100*sum(x>0 for x in xs)/len(xs),statistics.median(xs),statistics.mean(xs),len(xs)))
# 隨機抽同樣筆數：勝率 ≥ 觀察值的機率
random.seed(1)
print("\n隨機抽同樣筆數的日子，勝率不輸該時點的機率（越小越像真訊號）")
for nm,row in out.items():
    s=[]
    for h,xs in zip((20,60,120),row):
        if not xs: s.append('-'); continue
        w=sum(x>0 for x in xs)/len(xs); md=statistics.median(xs)
        cnt=0;cnt2=0;N=4000
        for _ in range(N):
            smp=random.sample(base[h],len(xs))
            if sum(x>0 for x in smp)/len(smp)>=w: cnt+=1
            if statistics.median(smp)>=md: cnt2+=1
        s.append("%dd p勝率=%.2f p中位=%.2f"%(h,cnt/N,cnt2/N))
    print("  %-14s %s"%(nm," | ".join(s)))
# 0050 含息
print("\n各時點 0050 含息 報酬")
for nm,k in TIM:
    s=[]
    for h in (20,60,120):
        xs=[fwd(e[k],h,'tr') for e in eps if e.get(k)]; xs=[x for x in xs if x is not None]
        s.append("%dd 勝%3.0f%% 中%+5.1f%% n=%d"%(h,100*sum(x>0 for x in xs)/len(xs),statistics.median(xs),len(xs)) if xs else '-')
    print("  %-14s %s"%(nm," | ".join(s)))
