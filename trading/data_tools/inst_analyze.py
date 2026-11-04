"""分析 inst_feat.json：法人籌碼條件能不能把 ★（和其他策略）的交易分出好壞。只在進場前看得到的特徵（t-1）。"""
import json,sys,statistics,collections
R=json.load(open(sys.argv[1]))["rows"]
def S(xs): return "n=%d 平均%+.2f%% 中位%+.2f%% 勝率%.0f%%"%(len(xs),statistics.mean(xs),statistics.median(xs),100*sum(1 for x in xs if x>0)/len(xs)) if len(xs)>=5 else "n=%d（太少）"%len(xs)
CONDS=[("投信前一日買超",lambda r:r["t1"]>0),("投信前一日賣超或0",lambda r:r["t1"]<=0),("投信連買≥3天",lambda r:r["tc"]>=3),("投信前5日合計>0",lambda r:r["t5"]>0),("投信前5日合計<0",lambda r:r["t5"]<0),
       ("外資前5日買超",lambda r:r["f5"]>0),("外資前5日賣超",lambda r:r["f5"]<0),("外資連買≥3天",lambda r:r["fc"]>=3),("外資前20日賣超",lambda r:r["f20"]<0),
       ("法人5日合計/均量 ≥ 0.5",lambda r:(r["r5"] or 0)>=0.5),("法人5日合計/均量 0～0.5",lambda r:0<=(r["r5"] or 0)<0.5),("法人5日合計/均量 < 0",lambda r:(r["r5"] or 0)<0),
       ("外資+投信前5日都買",lambda r:r["f5"]>0 and r["t5"]>0),("外資+投信前5日都賣",lambda r:r["f5"]<0 and r["t5"]<0)]
for strat in ["fundhi","fundall","fund1D","best","xlev"]:
    T=[r for r in R if r["strat"]==strat]
    if not T: continue
    print("\n==== %s  %s～%s  全部 %s"%(strat,min(r["sig"] for r in T),max(r["sig"] for r in T),S([r["ret"] for r in T])))
    years=sorted(set(r["sig"][:4] for r in T))
    for nm,c in CONDS:
        a=[r["ret"] for r in T if c(r)]; b=[r["ret"] for r in T if not c(r)]
        if len(a)<5: continue
        # 逐年：條件組比非條件組好的年數
        win=0;tot=0
        for y in years:
            ya=[r["ret"] for r in T if c(r) and r["sig"][:4]==y]; yb=[r["ret"] for r in T if not c(r) and r["sig"][:4]==y]
            if len(ya)>=3 and len(yb)>=3:
                tot+=1; win+= statistics.mean(ya)>statistics.mean(yb)
        print("  %-22s 符合 %s ｜ 不符 %s ｜ 符合較好的年數 %d/%d"%(nm,S(a),S(b),win,tot))
# 持有期間法人（事後對照）
fh=[r for r in R if r["strat"]=="fundhi"]
if fh:
    print("\n==== fundhi 持有期間（事後）外資合計>0：",S([r["ret"] for r in fh if r["hf"]>0])," 外資合計<0：",S([r["ret"] for r in fh if r["hf"]<0]))
    print("==== fundhi 訊號日當天（盤後才知道）投信買超：",S([r["ret"] for r in fh if r["t0"]>0])," 投信賣超：",S([r["ret"] for r in fh if r["t0"]<0]))
