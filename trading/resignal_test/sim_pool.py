"""整合模擬：事件策略共用一池 0050。
策略：xlev 季報意外獲利（期限後第 2 日收盤買、第 16 日收盤賣，使用者 410 筆）、cr 信用交易恢復（期限後第 1 日收盤買、第 6 日開盤賣，重建）。
池：100% 0050 含息；每筆股票 = 帳戶 10%，進場日收盤賣 0050 換股，出場日換回。成本：股票來回 0.47%、0050 來回 0.3%。"""
import json,pickle,statistics,collections
px,cal,mk=pickle.load(open("px.pkl","rb")); idx={d:i for i,d in enumerate(cal)}
tr50,divs=pickle.load(open("tr50.pkl","rb"))
cj=json.load(open("cyc10_bt.json")); x=cj["trades2"]["xlev"]; ci={c:i for i,c in enumerate(x["cols"])}
XL=[dict(strat="xlev",code=r[ci["code"]],buy=r[ci["sig"]],buy_px=r[ci["in_px"]],sell=r[ci["out_date"]],sell_px=r[ci["out_px"]]) for r in x["rows"]]
CR=[dict(strat="cr",code=e["code"],buy=e["buy"],buy_px=e["buy_px"],sell=e["sell"],sell_px=e["sell_px"]) for e in pickle.load(open("ev_cr.pkl","rb")) if e["liq"] and not e["lu"]]
XL=[t for t in XL if t["buy"] in idx and t["sell"] in idx]; CR=[t for t in CR if t["buy"] in idx and t["sell"] in idx]
START,END="2016-04-06","2026-10-16"
COST_STK=0.0047; COST_50=0.0015  # 單邊
def close(code,d):
    v=px.get(code,{}).get(d); return float(v[3]) if v and v[3] else None
def run(trades, slots=10, frac=0.10, priority=("xlev","cr"), dedup="two", label=""):
    """dedup: 'two' 同一檔兩個策略各買一份；'one' 已持有同一檔就不再買。"""
    byday=collections.defaultdict(list)
    for t in trades: byday[t["buy"]].append(t)
    i0,i1=idx[START],idx[END]
    units50=1.0/tr50[i0]           # 一開始全部 0050（含息單位）
    cash=0.0; pos=[]; eq=[]; done=[]; blocked=collections.Counter(); overlap=0; conflict_days=0
    for i in range(i0,i1+1):
        d=cal[i]
        # 出場：cr 開盤賣、xlev 收盤賣；賣出的錢當天收盤買回 0050
        keep=[]
        for p in pos:
            if p["sell"]==d:
                proceeds=p["sh"]*p["sell_px"]*(1-COST_STK)
                units50+=proceeds*(1-COST_50)/tr50[i]
                done.append(dict(p,ret=(p["sell_px"]/p["buy_px"]-1)*100-COST_STK*200))
            else: keep.append(p)
        pos=keep
        equity=units50*tr50[i]+sum(p["sh"]*(close(p["code"],d) or p["buy_px"]) for p in pos)
        # 進場
        cands=sorted(byday.get(d,[]), key=lambda t: priority.index(t["strat"]) if t["strat"] in priority else 9)
        if len(cands)+len(pos)>slots: conflict_days+=1
        for t in cands:
            if dedup=="one" and any(p["code"]==t["code"] for p in pos): overlap+=1; blocked[t["strat"]+"_dup"]+=1; continue
            if any(p["code"]==t["code"] for p in pos): overlap+=1
            if len(pos)>=slots: blocked[t["strat"]]+=1; continue
            fr=frac if not isinstance(frac,dict) else frac.get(t["strat"],0.10)
            amt=equity*fr
            avail=units50*tr50[i]*(1-COST_50)
            if avail<amt*0.5: blocked[t["strat"]+"_cash"]+=1; continue
            amt=min(amt,avail); need=amt/(1-COST_50)
            units50-=need/tr50[i]
            sh=amt*(1-COST_STK)/t["buy_px"]
            pos.append(dict(t,sh=sh))
        eq.append((d,units50*tr50[i]+sum(p["sh"]*(close(p["code"],d) or p["buy_px"]) for p in pos)))
    yrs=(i1-i0)/245.0; cagr=(eq[-1][1]/eq[0][1])**(1/yrs)-1
    peak=0; mdd=0
    for _,e in eq:
        peak=max(peak,e); mdd=min(mdd,e/peak-1)
    ye={}; 
    for d,e in eq: ye[d[:4]]=e
    ys=sorted(ye); yr={}; base=eq[0][1]
    for y in ys: yr[y]=(ye[y]/base-1)*100; base=ye[y]
    return dict(label=label,cagr=cagr*100,mdd=mdd*100,n=len(done),avg=statistics.mean([t["ret"] for t in done]) if done else 0,
                win=100*sum(1 for t in done if t["ret"]>0)/len(done) if done else 0,blocked=dict(blocked),overlap=overlap,conflict_days=conflict_days,yr=yr,
                by=collections.Counter(t["strat"] for t in done))
def show(r):
    print("== %s"%r["label"]); print("  年化 %.1f%%  回撤 %.1f%%  筆數 %d %s  每筆 %+.2f%%  勝率 %.0f%%  被擠掉 %s  同檔重疊 %d  槽不夠的日子 %d"%(
        r["cagr"],r["mdd"],r["n"],dict(r["by"]),r["avg"],r["win"],r["blocked"],r["overlap"],r["conflict_days"]))
    print("  逐年 "+"  ".join("%s %+.0f"%(y[2:],v) for y,v in r["yr"].items()))
print("xlev %d 筆、cr %d 筆（均量≥500、進場日沒鎖漲停）"%(len(XL),len(CR)))
# 兩個策略同一檔、持有期間重疊的次數
ov=0
for a in XL:
    for b in CR:
        if a["code"]==b["code"] and not (a["sell"]<b["buy"] or b["sell"]<a["buy"]): ov+=1
print("xlev 與 cr 同一檔且持有期間重疊：%d 對"%ov)
same_day=len(set(t["buy"] for t in XL)&set(t["buy"] for t in CR)); print("同一天都有進場的日子：%d"%same_day)
R=[]
R.append(run([],label="只抱 0050 含息"))
R.append(run(XL,label="季報意外獲利 單獨（10 槽）"))
R.append(run(CR,label="信用交易恢復 單獨（10 槽）"))
R.append(run(XL+CR,slots=10,label="兩個合併，共 10 槽，季報優先"))
R.append(run(XL+CR,slots=10,priority=("cr","xlev"),label="兩個合併，共 10 槽，信用恢復優先"))
R.append(run(XL+CR,slots=20,label="兩個合併，共 20 槽（各自 10 槽的上限）"))
R.append(run(XL+CR,slots=20,dedup="one",label="共 20 槽，同一檔只買一份"))
R.append(run(XL+CR,slots=10,frac=0.05,label="共 10 槽，每筆 5%（總曝險上限 50%）"))
R.append(run(XL+CR,slots=20,frac={"xlev":0.10,"cr":0.05},label="共 20 槽，季報 10%、信用恢復 5%"))
R.append(run(XL+CR,slots=20,frac={"xlev":0.10,"cr":0.10},priority=("xlev","cr"),label="共 20 槽，各 10%（同上，確認）"))
for r in R: show(r)
pickle.dump(R,open("sim_pool_rows.pkl","wb"))
