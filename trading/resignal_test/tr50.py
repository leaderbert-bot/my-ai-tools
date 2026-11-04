"""0050 含息日線（股息再投入）。2024 起用 exdiv.json，2016～2023 用公開的配息紀錄（手打，見下），
最後跟使用者報告裡的 0050 含息年化對照驗證。"""
import json,pickle
px,cal,mk=pickle.load(open("px.pkl","rb")); idx={d:i for i,d in enumerate(cal)}
DIV_MANUAL={  # 除息日: 每股配息（元）。0050 2016 年一次、2017 起一年兩次。
 "2016-10-26":0.85,
 "2017-02-08":1.70,"2017-07-31":0.70,
 "2018-01-29":2.20,"2018-07-23":0.70,
 "2019-01-22":2.30,"2019-07-19":0.70,
 "2020-01-31":2.90,"2020-07-21":0.70,
 "2021-01-22":3.05,"2021-07-21":0.35,
 "2022-01-21":3.20,"2022-07-18":1.80,
 "2023-01-30":2.60,"2023-07-18":1.90,
}
ex=json.load(open("exdiv.json"))
div=dict(DIV_MANUAL)
for r in ex["by"].get("0050",[]):
    if r["d"]>="2024-01-01": div[r["d"]]=float(r["tot"])
def nearest_td(d):
    i=0
    while i<len(cal) and cal[i]<d: i+=1
    return cal[i] if i<len(cal) else None
divs={}
for d,v in div.items():
    t=nearest_td(d)
    if t: divs[t]=divs.get(t,0)+v
c50=[]; last=None
for d in cal:
    v=px["0050"].get(d); last=float(v[3]) if v and v[3] else last; c50.append(last)
# 拆分還原：相鄰兩天收盤比 < 0.6 視為拆分，之前的價格全部除以比例
raw=list(c50)
for i in range(1,len(c50)):
    if c50[i] and c50[i-1] and c50[i]/c50[i-1]<0.6:
        ratio=round(c50[i-1]/c50[i]); print("偵測到拆分",cal[i],"比例 1:%d"%ratio)
        for j in range(i): 
            if c50[j]: c50[j]/=ratio
        for d in list(divs):          # 拆分前的配息也要除
            if d<cal[i]: divs[d]=divs[d]/ratio
# 含息指數：除息日把股息再投入 → units *= 1 + div/close
units=1.0; tr=[]
for i,d in enumerate(cal):
    if d in divs and c50[i]: units*= (1+divs[d]/c50[i])
    tr.append(units*c50[i] if c50[i] else None)
pickle.dump((tr,divs),open("tr50.pkl","wb"))
def cagr(a,b):
    ia,ib=idx[a],idx[b]; yrs=(ib-ia)/245.0
    return (tr[ib]/tr[ia])**(1/yrs)-1, (c50[ib]/c50[ia])**(1/yrs)-1
for a,b,ref in [("2017-08-24","2026-10-16","報告：含息 23.8%、不含息 20.0%"),("2016-04-06","2026-10-16","報告：含息 24.1%"),("2016-01-04","2026-10-16","報告：含息 23.7%（景氣燈號報告 2016-01～2026-10）")]:
    t,p=cagr(a,b); print("%s~%s 含息 %.1f%%  不含息 %.1f%%   %s"%(a,b,t*100,p*100,ref))
print("配息筆數",len(divs),"合計",round(sum(divs.values()),2))
