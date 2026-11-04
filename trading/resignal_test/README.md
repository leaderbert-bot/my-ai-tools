# ★ 再訊號加碼測試

在 00money 資料夾（有 data/k10y 與 data/cyc10_bt.json）旁執行：

```bash
# 1. 把 data/k10y/k10_YYYY-MM.json.gz 解壓成 k10/k10_YYYY-MM.json（或改 load_data.py 直接讀 gz）
python3 load_data.py        # 產生 px.pkl
python3 resignal.py         # 重算持有期間的 ★ 訊號 → ev.pkl（約 5 分鐘）
python3 ev_stats.py         # 訊號層級統計
python3 sim.py              # 6 槽帳戶模擬：基準 vs 再訊號加碼各版本
```

kc.py 是從 tw_radar.py 抽出的循環點演算法（KC_CFG 到 KScan），未修改。
cyc10_bt.json 需放在同一層（含 trades2.fundhi）。
