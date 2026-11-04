import json,glob,os,pickle
from datetime import date
def build():
    px={}; cal=set(); mk={}
    for f in sorted(glob.glob("k10/k10_*.json")):
        j=json.load(open(f))
        for d,row in j["px"].items():
            cal.add(d)
            for c,v in row.items():
                if len(c)!=4 or not c.isdigit(): continue   # 只留 4 碼個股（含 0050 另存）
                px.setdefault(c,{})[d]=v
        for c,m in j.get("mk",{}).items(): mk[c]=m
        # 0050
        for d,row in j["px"].items():
            if "0050" in row: px.setdefault("0050",{})[d]=row["0050"]
    cal=sorted(cal)
    return px,cal,mk
if __name__=="__main__":
    px,cal,mk=build()
    pickle.dump((px,cal,mk),open("px.pkl","wb"))
    print("stocks",len(px),"days",len(cal),cal[0],cal[-1])
    print("0050 days",len(px["0050"]))
