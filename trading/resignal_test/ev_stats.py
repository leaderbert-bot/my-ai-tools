"""再訊號事件（訊號層級）統計：加碼單自己抱 20 天賺多少，跟原本進場比。"""
import pickle, collections, statistics
TR, EV = pickle.load(open("ev.pkl", "rb"))
def S(xs):
    xs = list(xs)
    if not xs: return "—"
    return "n=%d 平均%+.2f%% 中位%+.2f%% 勝率%.0f%%" % (len(xs), statistics.mean(xs), statistics.median(xs), 100 * sum(1 for x in xs if x > 0) / len(xs))
print("原本進場（489 筆）：", S(t["ret"] for t in TR))
print("再訊號加碼單（獨立抱 20 天）：", S(e["ret"] for e in EV))
print("  其中現價 > 第一筆成本：", S(e["ret"] for e in EV if e["above_entry"]))
print("  其中現價 ≤ 第一筆成本：", S(e["ret"] for e in EV if not e["above_entry"]))
print("有再訊號的那些原本交易：", S(TR[n]["ret"] for n in set(e["trade"] for e in EV)))
print("沒有再訊號的原本交易：", S(TR[n]["ret"] for n in range(len(TR)) if n not in set(e["trade"] for e in EV)))
# 同一天的「原本那筆剩下的路」：從再訊號日到原本出場日
print("再訊號日之後原本那筆剩下的報酬（到原出場日）：", S(e["rest"] for e in EV))
print("\n依第幾天再訊號")
for lo, hi in [(1, 3), (4, 7), (8, 12), (13, 19)]:
    print("  第 %2d-%2d 天：" % (lo, hi), S(e["ret"] for e in EV if lo <= e["off"] <= hi))
print("\n依點位")
for tag, xs in sorted(collections.defaultdict(list, {t: [e["ret"] for e in EV if e["tag"] == t] for t in set(e["tag"] for e in EV)}).items()):
    print("  %s：" % tag, S(xs))
print("\n逐年（加碼單 vs 原本）")
for y in sorted(set(e["d"][:4] for e in EV) | set(t["sig"][:4] for t in TR)):
    a = [e["ret"] for e in EV if e["d"][:4] == y]; b = [t["ret"] for t in TR if t["sig"][:4] == y]
    print("  %s  加碼 %-38s  原本 %s" % (y, S(a), S(b)))
print("\n每筆原本交易平均有幾次再訊號：%.2f；有再訊號的交易佔 %.0f%%" % (len(EV) / len(TR), 100 * len(set(e["trade"] for e in EV)) / len(TR)))
# 同一筆交易只取第一次再訊號
first = {}
for e in EV:
    if e["trade"] not in first: first[e["trade"]] = e
print("只取每筆的第一次再訊號：", S(e["ret"] for e in first.values()))
