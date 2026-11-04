"""信用交易恢復事件（陳信宏）：上一季每股淨值 5～10、這一季 ≥ 10 → 申報期限後第 1 個交易日收盤買、第 6 個交易日開盤賣。
資料：mopsfin_{sii,otc}_{ROC年}_{季}.json 的 bvps；價格 k10y。流動性：20 日均量 ≥ 500 張、股價 ≥ 10（跟 0050 比那版一樣）。"""
import json,glob,pickle,os,re
px,cal,mk=pickle.load(open("px.pkl","rb")); idx={d:i for i,d in enumerate(cal)}
Q={}
for f in glob.glob("mopsfin/*.json"):
    m=re.search(r"mopsfin_(sii|otc)_(\d+)_(\d)\.json",f); y=int(m.group(2))+1911; q=int(m.group(3))
    rows=json.load(open(f))["rows"]
    for c,v in rows.items():
        if v.get("bvps") is not None: Q.setdefault((y,q),{})[c]=float(v["bvps"])
def deadline(y,q): return {1:"%d-05-15"%y,2:"%d-08-14"%y,3:"%d-11-14"%y,4:"%d-03-31"%(y+1)}[q]
def prev_q(y,q): return (y,q-1) if q>1 else (y-1,4)
def td_after(d,n):
    """期限 d 之後第 n 個交易日"""
    i=0
    while i<len(cal) and cal[i]<=d: i+=1
    j=i+n-1
    return cal[j] if j<len(cal) else None
EV=[]
for (y,q),cur in sorted(Q.items()):
    pq=prev_q(y,q)
    if pq not in Q: continue
    prv=Q[pq]
    for c,b in cur.items():
        b0=prv.get(c)
        if b0 is None or not (5<=b0<10) or b<10: continue
        if not (len(c)==4 and c.isdigit()): continue
        d=deadline(y,q); t1=td_after(d,1); t6=td_after(d,6)
        if not t1 or not t6: continue
        s=px.get(c,{})
        if t1 not in s or t6 not in s: continue
        ds=[x for x in sorted(s) if x<=t1][-20:]
        if len(ds)<20: continue
        v20=sum(float(s[x][4] or 0) for x in ds)/20
        c_in=float(s[t1][3]); o_out=float(s[t6][0])
        if not (c_in and o_out) or c_in<10: continue
        lu = c_in>=float(s[ds[-2]][3])*1.094 and c_in>=float(s[t1][1])*0.999 if len(ds)>=2 else False
        EV.append(dict(code=c,q="%dQ%d"%(y,q),dl=d,buy=t1,buy_px=c_in,sell=t6,sell_px=o_out,v20=v20,liq=v20>=500,lu=lu,
                       ret=(o_out/c_in-1)*100-0.47, b0=b0,b=b))
import statistics,collections
def S(xs): return "n=%d 平均%+.2f%% 中位%+.2f%% 勝率%.0f%%"%(len(xs),statistics.mean(xs),statistics.median(xs),100*sum(1 for x in xs if x>0)/len(xs)) if xs else "—"
print("季別涵蓋",sorted(Q)[0],"→",sorted(Q)[-1],"共",len(Q))
print("全部事件：",S([e["ret"] for e in EV]))
print("均量≥500：",S([e["ret"] for e in EV if e["liq"]]))
print("均量≥500 且進場日沒鎖漲停：",S([e["ret"] for e in EV if e["liq"] and not e["lu"]]))
print("逐年（均量≥500）：")
for y in sorted(set(e["buy"][:4] for e in EV)):
    print("  ",y,S([e["ret"] for e in EV if e["liq"] and e["buy"][:4]==y]))
print("使用者報告：均量≥500 共 151 筆、每筆比大盤 +3.6%（扣成本前）；全部約 34 筆/年、+2.7%")
pickle.dump(EV,open("ev_cr.pkl","wb"))
