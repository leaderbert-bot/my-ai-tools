"""★ 再訊號加碼測試：持有中的 ★ 股票再出現 ★ 訊號 → 再開一槽（獨立抱 20 天）。
用使用者 cyc10_bt.json 的 fundhi 489 筆實際交易當底，用 k10y 全市場日 K 重算每一天的循環點／離一年高／0050 季線。
基本面旗標（營收創高、TTM EPS 成長、營收年增≥0）假設在 20 天持有期間不變（近似）。"""
import pickle,json,kc,collections,math,sys,time
from datetime import date
COST=0.0047; HOLD=20; SLOTS=6; DAYMAX=3
px,cal,mk=pickle.load(open("px.pkl","rb")); idx={d:i for i,d in enumerate(cal)}
# ---- 0050 季線
c50=[]; last=None
for d in cal:
    v=px["0050"].get(d); last=v[3] if v else last; c50.append(last)
b50=[False]*len(cal)
for i in range(59,len(cal)):
    w=c50[i-59:i+1]
    if None not in w: b50[i]=c50[i]>sum(w)/60
# ---- trades
cj=json.load(open("cyc10_bt.json")); t2=cj["trades2"]["fundhi"]; ci={c:i for i,c in enumerate(t2["cols"])}
TR=[]
for r in t2["rows"]:
    TR.append(dict(sig=r[ci["sig"]],code=r[ci["code"]],name=r[ci["name"]],in_px=r[ci["in_px"]],out=r[ci["out_date"]],out_px=r[ci["out_px"]],ret=r[ci["ret_pct"]],phi=r[ci["phi_pct"]]))
TR=[t for t in TR if t["sig"] in idx and t["out"] in idx]
print("trades usable",len(TR),"of",len(t2["rows"]))
# ---- bars per stock
_bars_cache={}
def bars_of(code):
    if code in _bars_cache: return _bars_cache[code]
    s=px.get(code,{}); out=[]; vols=[]
    for d in sorted(s):
        v=s[d]
        if not (isinstance(v,list) and len(v)>=4): continue
        o,h,l,c=v[0],v[1],v[2],v[3]
        if not (o and h and l and c): continue
        if not (l<=min(o,c) and h>=max(o,c)): continue
        out.append((date.fromisoformat(d),float(o),float(h),float(l),float(c))); vols.append(float(v[4] or 0))
    di={b[0].isoformat():i for i,b in enumerate(out)}
    _bars_cache[code]=(out,vols,di); return _bars_cache[code]
def tag_at(bars,k,win=800):
    sub=bars[max(0,k-win+1):k+1]
    if len(sub)<kc.KC_MIN_BARS: return None
    ctx=kc.KCtx(sub); sc=kc.KScan(ctx,max_segments=40).run()
    return (sc.mc[0] or sc.me[0] or "").strip("$")
def cond_at(code,k):
    bars,vols,di=bars_of(code)
    c=[b[4] for b in bars]
    tag=tag_at(bars,k)
    if tag is None: return None
    hi=max(c[max(0,k-249):k+1]); phi=c[k]/hi
    v20=sum(vols[max(0,k-19):k+1])/len(vols[max(0,k-19):k+1])
    d=bars[k][0].isoformat()
    return dict(tag=tag,phi=phi,v20=v20,px=c[k],b50=b50[idx[d]] if d in idx else False,d=d)
def is_star(cd):
    return cd and cd["tag"] in "123567ABCD" and cd["tag"]!="" and cd["phi"]>=0.95 and cd["v20"]>=500 and cd["px"]>=10 and cd["b50"]
# ---- 1) 檢查我重算的訊號跟他們的進場日對不對得上
t0=time.time(); match=0; miss=0; nomatch=[]
EV=[]   # 再訊號事件
for n,t in enumerate(TR):
    bars,vols,di=bars_of(t["code"]); k0=di.get(t["sig"])
    if k0 is None: miss+=1; continue
    cd0=cond_at(t["code"],k0)
    if is_star(cd0): match+=1
    else: nomatch.append((t["sig"],t["code"],cd0 and cd0["tag"],cd0 and round(cd0["phi"],3),cd0 and cd0["b50"]))
    kout=di.get(t["out"])
    if kout is None: continue
    for k in range(k0+1,kout):            # 持有期間（不含出場日）
        cd=cond_at(t["code"],k)
        if not is_star(cd): continue
        if k+HOLD>=len(bars): continue
        c=[b[4] for b in bars]
        EV.append(dict(trade=n,code=t["code"],name=t["name"],sig=t["sig"],d=cd["d"],off=k-k0,tag=cd["tag"],phi=cd["phi"],
                       px=c[k],out_d=bars[k+HOLD][0].isoformat(),out_px=c[k+HOLD],ret=(c[k+HOLD]/c[k]-1)*100-COST*100,
                       above_entry=c[k]>t["in_px"], rest=(t["out_px"]/c[k]-1)*100, orig_ret=t["ret"]))
    if n%50==0: print("  ..",n,"%.0fs"%(time.time()-t0),flush=True)
print("進場日重算為 ★ 訊號：match %d / %d（不符 %d，缺 %d）"%(match,match+len(nomatch),len(nomatch),miss)); print("不符例子",nomatch[:8])
print("再訊號事件",len(EV),"涉及交易",len(set(e["trade"] for e in EV)))
pickle.dump((TR,EV),open("ev.pkl","wb"))
