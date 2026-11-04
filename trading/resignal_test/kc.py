import math
from datetime import date, timedelta

#   · 延伸點 ABCD 33/43 吻合 —— 原程式的採納條件會讀「上一次執行寫在 CSV 裡的標記」，
#     從零重算沒辦法完全複製，所以延伸點當參考、循環點才是主訊號。

KC_CFG = {
    "ma_s": 8, "ma_m": 21, "ma_l": 55,
    "num_k": 66,
    "ang_pos": 12.0, "ang_neg": -12.0,
    "buf_atr_pct": 0.45,
    "buf_close_units": 2.0,
    "price_unit_ratio": 0.001,
    "buf_ma_units": 2.0,
    "atr_period": 21,
}

# 角度是在 matplotlib 的「像素座標」上量的，等價於把 ΔMA 用 66 根 K 的價格範圍歸一化。
# C = (axes高 / axes寬) * x_range = (0.72*9)/(0.46*15) * (65 + 2*65/66)
KC_ANGLE_C = 62.89328063241106


def _kc_np_round(x, scale):
    """
    複製 numpy 的 round：先乘上 10^n、用「四捨六入五成雙」取整、再除回去。

    不能用 Python 內建的 round() —— 它對「真正的二進位值」四捨五入，
    numpy 則是對「乘完之後的浮點數」四捨五入，兩者在 .005 邊界會差一分。
    MA 是先四捨五入到小數 2 位才拿去跟 buffer 比、才拿去算角度的，
    差一分會讓小角度整個變成兩倍或一半，所以這裡必須跟原程式完全一致。
    """
    v = x * scale
    n = math.floor(v)
    d = v - n
    if d > 0.5:
        n += 1
    elif d == 0.5 and (n % 2 != 0):
        n += 1
    return n / scale


def _kc_r2(x):
    return None if x is None else _kc_np_round(x, 100.0)


def _kc_r1(x):
    return None if x is None else _kc_np_round(x, 10.0)


def _kc_tick(p):
    """台股一跳多少錢。"""
    if p is None:
        return 0.01
    if p < 10:   return 0.01
    if p < 50:   return 0.05
    if p < 100:  return 0.10
    if p < 500:  return 0.50
    if p < 1000: return 1.00
    return 5.00


def _kc_sma(vals, n):
    """
    降冪陣列的移動平均：ma[i] = mean(vals[i .. i+n-1])。資料不足回 None。

    每一格都重新把區間加總一次，不用滾動累加 —— 滾動累加的浮點誤差會漂移，
    在 .005 邊界上跟原程式差一分，而那一分會讓小角度差到兩倍。
    """
    N = len(vals)
    out = [None] * N
    last = N - n
    for i in range(last + 1):
        out[i] = _kc_r2(sum(vals[i:i + n]) / n)
    return out


def _kc_atr(highs, lows, closes, period):
    N = len(closes)
    tr = [None] * N
    for i in range(N - 1):
        pc = closes[i + 1]
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - pc), abs(lows[i] - pc))
    out = [None] * N
    run = 0.0
    cnt = 0
    for i in range(N - 2, -1, -1):
        run += tr[i]
        cnt += 1
        if cnt > period:
            run -= tr[i + period]
            cnt = period
        if cnt == period:
            out[i] = _kc_r2(run / period)
    return out


def _kc_week_key(d):
    """W-FRI 分箱：週六～週五算同一週，標籤是該週五。"""
    return d + timedelta(days=(4 - d.weekday()) % 7)


def _kc_angle(ma_from, ma_to, n_bars, y_range):
    """ma_from = 較舊那根、ma_to = 較新那根。回傳度數（四捨五入到小數 1 位）。"""
    if ma_from is None or ma_to is None or not y_range or n_bars <= 0:
        return None
    dy = (ma_to - ma_from) * KC_ANGLE_C
    dx = n_bars * y_range
    if dx == 0:
        return 90.0 if dy > 0 else -90.0
    return _kc_r1(math.degrees(math.atan2(dy, dx)))


def _kc_win_span(hi_arr, lo_arr, ma_list, i, n):
    """圖上 n 根的 y 軸範圍：價格高低 ±2% 邊距，再跟三條 MA 取聯集。"""
    N = len(hi_arr)
    end = min(i + n, N)
    if end - i < 2:
        return None
    hi = max(hi_arr[i:end])
    lo = min(lo_arr[i:end])
    off = (hi - lo) * 0.02
    y_max, y_min = hi + off, lo - off
    for ma in ma_list:
        for k in range(i, end):
            v = ma[k]
            if v is None:
                continue
            if v > y_max: y_max = v
            if v < y_min: y_min = v
    rng = y_max - y_min
    return rng if rng > 0 else None


class KCtx(object):
    """一檔股票的全部前置計算。bars 由呼叫端給「由舊到新」，內部轉成降冪。"""

    def __init__(self, bars_asc, cfg=None):
        self.cfg = dict(KC_CFG)
        if cfg:
            self.cfg.update(cfg)
        n_k = self.cfg["num_k"]

        rows = list(reversed(bars_asc))           # 轉成降冪：index 0 = 最新
        self.N = N = len(rows)
        self.dates = [r[0] for r in rows]
        self.o = [float(r[1]) for r in rows]
        self.h = [float(r[2]) for r in rows]
        self.l = [float(r[3]) for r in rows]
        self.c = [float(r[4]) for r in rows]

        self.ma_s = _kc_sma(self.c, self.cfg["ma_s"])
        self.ma_m = _kc_sma(self.c, self.cfg["ma_m"])
        self.ma_l = _kc_sma(self.c, self.cfg["ma_l"])
        self.atr = _kc_atr(self.h, self.l, self.c, self.cfg["atr_period"])

        self._build_weekly()
        self._build_angles()

    # ---------- 週線 ----------
    def _build_weekly(self):
        N = self.N
        n_k = self.cfg["num_k"]
        self.wkey = [_kc_week_key(d) for d in self.dates]

        # 完整週（降冪）。同一週的日 K 在降冪陣列裡是連續的一段。
        CW = []
        idx_of_key = {}
        j = 0
        while j < N:
            k = self.wkey[j]
            e = j
            while e + 1 < N and self.wkey[e + 1] == k:
                e += 1
            idx_of_key[k] = len(CW)
            CW.append({
                "c": self.c[j], "o": self.o[e],
                "h": max(self.h[j:e + 1]), "l": min(self.l[j:e + 1]),
                "dmin": self.dates[e], "dmax": self.dates[j],
                "i_new": j, "i_old": e,
            })
            j = e + 1
        self.CW = CW
        self.cw_idx = idx_of_key
        M = len(CW)

        cw_c = [w["c"] for w in CW]
        self.cw_ma_s = _kc_sma(cw_c, self.cfg["ma_s"])
        self.cw_ma_m = _kc_sma(cw_c, self.cfg["ma_m"])
        self.cw_ma_l = _kc_sma(cw_c, self.cfg["ma_l"])

        # 每根日 K 的「當下半週」高低（從該週最舊一根累積到這一根）
        part_hi = [0.0] * N
        part_lo = [0.0] * N
        for w in CW:
            hh, ll = None, None
            for t in range(w["i_old"], w["i_new"] - 1, -1):
                hh = self.h[t] if hh is None else max(hh, self.h[t])
                ll = self.l[t] if ll is None else min(ll, self.l[t])
                part_hi[t] = hh
                part_lo[t] = ll
        self.part_hi, self.part_lo = part_hi, part_lo

        # 錨定在每根日 K 時的週 MA[0]（半週收盤 = 當天收盤）
        def wma0(period, cw_close):
            out = [None] * N
            for i in range(N):
                k = idx_of_key[self.wkey[i]]
                if k + period - 1 >= M:
                    continue
                s = self.c[i]
                for t in range(1, period):
                    s += cw_close[k + t]
                out[i] = _kc_r2(s / period)
            return out
        self.wma0_s = wma0(self.cfg["ma_s"], cw_c)
        self.wma0_m = wma0(self.cfg["ma_m"], cw_c)
        self.wma0_l = wma0(self.cfg["ma_l"], cw_c)

    def weekly_yrange(self, i):
        """錨定在日 K i 時，週線圖 66 根的 y 範圍。"""
        n_k = self.cfg["num_k"]
        k = self.cw_idx[self.wkey[i]]
        M = len(self.CW)
        end = min(k + n_k, M)
        if end - (k + 1) < 1:
            return None
        hi = self.part_hi[i]
        lo = self.part_lo[i]
        for t in range(k + 1, end):
            w = self.CW[t]
            if w["h"] > hi: hi = w["h"]
            if w["l"] < lo: lo = w["l"]
        off = (hi - lo) * 0.02
        y_max, y_min = hi + off, lo - off
        for ma0, cw_ma in ((self.wma0_s, self.cw_ma_s),
                           (self.wma0_m, self.cw_ma_m),
                           (self.wma0_l, self.cw_ma_l)):
            v = ma0[i]
            if v is not None:
                if v > y_max: y_max = v
                if v < y_min: y_min = v
            for t in range(k + 1, end):
                v = cw_ma[t]
                if v is None:
                    continue
                if v > y_max: y_max = v
                if v < y_min: y_min = v
        rng = y_max - y_min
        return rng if rng > 0 else None

    # ---------- 角度 ----------
    def _build_angles(self):
        N = self.N
        n_k = self.cfg["num_k"]
        pos, neg = self.cfg["ang_pos"], self.cfg["ang_neg"]

        self.dy_range = [None] * N
        self.wy_range = [None] * N
        for i in range(N):
            self.dy_range[i] = _kc_win_span(self.h, self.l,
                                         (self.ma_s, self.ma_m, self.ma_l), i, n_k)
            self.wy_range[i] = self.weekly_yrange(i)

        # 1D 日線角度
        self.d1_s = [None] * N
        self.d1_m = [None] * N
        self.d1_l = [None] * N
        for i in range(N - 1):
            yr = self.dy_range[i]
            self.d1_s[i] = _kc_angle(self.ma_s[i + 1], self.ma_s[i], 1, yr)
            self.d1_m[i] = _kc_angle(self.ma_m[i + 1], self.ma_m[i], 1, yr)
            self.d1_l[i] = _kc_angle(self.ma_l[i + 1], self.ma_l[i], 1, yr)

        # 1W 週線角度（寫在日 K 那一列上）
        self.w1_s = [None] * N
        self.w1_m = [None] * N
        self.w1_l = [None] * N
        M = len(self.CW)
        for i in range(N):
            k = self.cw_idx[self.wkey[i]]
            if k + 1 >= M:
                continue
            yr = self.wy_range[i]
            self.w1_s[i] = _kc_angle(self.cw_ma_s[k + 1], self.wma0_s[i], 1, yr)
            self.w1_m[i] = _kc_angle(self.cw_ma_m[k + 1], self.wma0_m[i], 1, yr)
            self.w1_l[i] = _kc_angle(self.cw_ma_l[k + 1], self.wma0_l[i], 1, yr)

        # 聚合日線角度：把連續走平（-12~12）的那一段合併起來量一條較長的斜率。
        # 必須由舊往新算，因為它會讀自己這一欄前面（較舊）bar 的值。
        def agg_daily(ma, one_d):
            out = [None] * N
            for i in range(N - 1, -1, -1):
                n = 0
                while i + n + 1 < N:
                    n += 1
                    pa = out[i + n]
                    if pa is None or pa > pos or pa < neg:
                        break
                if n == 1 and one_d[i] is not None:
                    out[i] = one_d[i]
                else:
                    out[i] = _kc_angle(ma[i + n] if i + n < N else None, ma[i], n, self.dy_range[i])
            return out
        self.da_s = agg_daily(self.ma_s, self.d1_s)
        self.da_m = agg_daily(self.ma_m, self.d1_m)
        self.da_l = agg_daily(self.ma_l, self.d1_l)

        # 聚合週線角度：走訪的是「週」，讀的是該週最後一個交易日那一列的同欄位值。
        i_of_date = {}
        for idx, d in enumerate(self.dates):
            i_of_date[d] = idx

        def agg_weekly(cw_ma, wma0, one_w):
            out = [None] * N
            for i in range(N - 1, -1, -1):
                k = self.cw_idx[self.wkey[i]]
                n = 0
                while k + n + 1 < M:
                    n += 1
                    w = self.CW[k + n]
                    pi = i_of_date.get(w["dmax"])
                    pa = out[pi] if pi is not None else None
                    if pa is None or pa > pos or pa < neg:
                        break
                if n == 0:
                    continue
                if n == 1 and one_w[i] is not None:
                    out[i] = one_w[i]
                else:
                    src = cw_ma[k + n] if k + n < M else None
                    out[i] = _kc_angle(src, wma0[i], n, self.wy_range[i])
            return out
        self.wa_s = agg_weekly(self.cw_ma_s, self.wma0_s, self.w1_s)
        self.wa_m = agg_weekly(self.cw_ma_m, self.wma0_m, self.w1_m)
        self.wa_l = agg_weekly(self.cw_ma_l, self.wma0_l, self.w1_l)

    # ---------- buffer ----------
    def buf_close(self, i):
        return _kc_tick(self.c[i]) * self.cfg["buf_close_units"]

    def buf_ma(self, i):
        return self.c[i] * self.cfg["price_unit_ratio"] * self.cfg["buf_ma_units"]

    def buf_zone(self, i):
        a = self.atr[i]
        return None if a is None else a * self.cfg["buf_atr_pct"]




class KScan(object):

    def __init__(self, ctx, max_segments=4):
        self.x = ctx
        self.N = ctx.N
        self.n_k = ctx.cfg["num_k"]
        self.pos = ctx.cfg["ang_pos"]
        self.neg = ctx.cfg["ang_neg"]
        self.max_segments = max_segments

        N = self.N
        self.mc = [''] * N               # marker_cycle
        self.dc = [None] * N             # definition_cycle
        self.me = [''] * N               # marker_extension
        self.de = [None] * N             # definition_extension
        self.rh = [False] * N            # is_record_high
        self.st = dict((k, [0] * N) for k in (1, 2, 3, 5, 6, 7))
        self.segments = []

    # ---------- 小工具 ----------
    def _dc(self, i):
        return self.dc[i] or ()

    def _de(self, i):
        return self.de[i] or ()

    def _add_dc(self, i, v):
        if self.dc[i] is None:
            self.dc[i] = []
        self.dc[i].append(v)

    def _add_de(self, i, v):
        if self.de[i] is None:
            self.de[i] = []
        self.de[i].append(v)

    def _closest(self, arr, wanted, i_right, i_left):
        """對應 pandas 的 iloc[i_right:i_left] + first_valid_index()（降冪＝取最新的）。"""
        N = self.N
        if i_left is None:
            i_left = N
        i_right = max(0, i_right)
        i_left = min(N, i_left)
        for k in range(i_right, i_left):
            if arr[k] in wanted:
                return k
        return None

    def _ang_turn(self, col, i, max_range):
        """最近一次角度由 <=12 翻上 >12 的位置。碰到 None 立刻整個中止。"""
        N = self.N
        for n in range(i, i + max_range):
            if n + 1 >= N:
                return None
            cur, pre = col[n], col[n + 1]
            if cur is None or pre is None:
                return None
            if pre <= self.pos and cur > self.pos:
                return n
        return None

    def _turn_close(self, i):
        """收盤價在 1 或 2 根之前形成局部低點。回傳 1/2 或 None。"""
        c, N = self.x.c, self.N
        for n in (1, 2):
            if i + n + 1 >= N:
                return None
            cur, pre, nxt = c[i + n], c[i + n + 1], c[i + n - 1]
            if cur < nxt and pre >= cur:
                return n
        return None

    def _red(self, i):
        return self.x.c[i] > self.x.o[i]

    def _above_yday_body(self, i):
        if i + 1 >= self.N:
            return False
        return self.x.c[i] > max(self.x.c[i + 1], self.x.o[i + 1])

    def _within_yday_body(self, i):
        if i + 1 >= self.N:
            return False
        lo = min(self.x.c[i + 1], self.x.o[i + 1])
        hi = max(self.x.c[i + 1], self.x.o[i + 1])
        return lo <= self.x.c[i] <= hi

    def _red_k_over_ma_s(self, i, pct):
        """紅 K 實體有 pct 比例在 MA8 之上。"""
        ma = self.x.ma_s[i]
        if ma is None:
            return False
        o, c = self.x.o[i], self.x.c[i]
        return ma <= o + (c - o) * (1.0 - pct)

    def _record_high(self, i):
        h, N = self.x.h, self.N
        end = min(i + 330 - 1, N)
        if i + 1 >= end:
            return False
        return h[i] > max(h[i + 1:end])

    # ---------- 區段切分 ----------
    def run(self):
        x, N, n_k = self.x, self.N, self.n_k
        if N < n_k + 5:
            return self
        M = len(x.CW)
        if M >= n_k:
            wlimit_date = x.CW[n_k - 1]["dmin"]
            W = N - 1
            for j in range(N):
                if x.dates[j] <= wlimit_date:
                    W = j
                    break
        else:
            W = N - 1

        i_end = 0
        i_start = 0
        guard = 0
        while i_start < n_k - 1 and guard < self.max_segments:
            guard += 1
            hi_i, hi_v = None, None
            for j in range(min(W, N - 1), i_end - 1, -1):   # 由舊往新掃，同高取最舊
                v = x.c[j]
                if hi_v is None or v > hi_v:
                    hi_v, hi_i = v, j
            if hi_i is None:
                break
            i_start = hi_i
            self.segments.append((i_start, i_end))
            self._segment(i_start, i_end)
            if i_end == 0 and self.max_segments == 1:
                break
            i_end = i_start + 1
            if i_end >= N:
                break
        return self

    def _segment(self, start_i, end_i):
        for i in range(start_i, end_i - 1, -1):
            if self._record_high(i):
                self.rh[i] = True
            self._judge_7(i, start_i)
            self._judge_6(i, start_i)
            self._judge_5(i, start_i)
            self._judge_0(i)
            self._judge_1(i, start_i)
            self._judge_2(i, start_i)
            self._judge_3(i, start_i)
            self._judge_abcd(i, start_i)

    # ---------- 循環點 0（元氣丸） ----------
    def _judge_0(self, i):
        if self.mc[i] != '':
            return
        if self._is_0(i):
            self._add_dc(i, '0')
            self.mc[i] = '$0$'

    def _is_0(self, i):
        x, N = self.x, self.N
        if i + 1 >= N:
            return False
        if self._ang_turn(x.da_s, i, 2) is None:
            return False
        if not self._red(i):
            return False
        ms, mm = x.ma_s[i], x.ma_m[i]
        if ms is None or mm is None or not (ms > mm):
            return False
        if self.mc[i + 1] == '$0$':
            return False
        # 原程式這裡綁錯 bar（永遠拿最新一根判斷），此處改成判斷「這一根」——
        # 對最新一根結果完全相同，對歷史 bar 才是正確的。
        if not self._red_k_over_ma_s(i, 0.75):
            return False
        ps, pm = x.ma_s[i + 1], x.ma_m[i + 1]
        if ps is not None and pm is not None and ps < pm and ms > mm:
            return True
        return (ms - mm) < x.buf_ma(i)

    # ---------- 循環點 1/2/3（日 MA8 / MA21 / MA55） ----------
    def _judge_ma(self, i, start_i, key, ma, ang, use_list):
        x, N = self.x, self.N
        st = self.st[key]
        st[i] = st[i + 1] if (i != start_i and i + 1 < N) else 0
        if st[i] == 0:
            if self._is_ma_point(i, ma, ang):
                self._add_dc(i, str(key))
                if self._use_ma_point(i, start_i, key, ma, use_list):
                    self.mc[i] = '$%d$' % key
                    st[i] = 1
                    return
            a = ang[i]
            cv, mv = x.c[i], ma[i]
            if (a is not None and a <= self.pos) or (mv is not None and cv < mv):
                st[i] = 1
                return
        if st[i] == 1:
            mv = ma[i]
            if mv is not None and x.c[i] >= mv:
                st[i] = 0

    def _is_ma_point(self, i, ma, ang):
        x = self.x
        mv, a = ma[i], ang[i]
        if mv is None or a is None:
            return False
        b = x.buf_close(i)
        if not (mv - b <= x.c[i] <= mv + b):
            return False
        return a > self.pos

    def _use_ma_point(self, i, start_i, key, ma, use_list):
        x = self.x
        if self.mc[i] != '':
            return False
        k = self._closest(self.mc, use_list, i + 1, start_i + 1)
        me = '$%d$' % key
        if k is None:
            for t in range(i + 1, min(start_i + 1, self.N)):
                mv = ma[t]
                if mv is None or x.c[t] < mv:
                    return False
            return True
        if self.mc[k] == me:
            return x.c[i] >= x.c[k]
        return x.c[i] > x.c[k]

    def _judge_1(self, i, s):
        self._judge_ma(i, s, 1, self.x.ma_s, self.x.da_s,
                       ('$1$', '$2$', '$3$', '$5$', '$6$', '$7$'))

    def _judge_2(self, i, s):
        self._judge_ma(i, s, 2, self.x.ma_m, self.x.da_m, ('$2$', '$3$', '$6$', '$7$'))

    def _judge_3(self, i, s):
        self._judge_ma(i, s, 3, self.x.ma_l, self.x.da_l, ('$3$', '$6$', '$7$'))

    # ---------- 循環點 5 / 6 / 7（週 MA8 / MA21 / MA55） ----------
    def _judge_w(self, i, start_i, key, wma0, ang, use_map, has_zone, prev_marker_block):
        """
        5/6/7 共用的狀態機。has_zone 的那兩個（5、6）多一段「盤整區」判斷：
        週 MA8 跌破週 MA21 就進 step 2 停住，要重新站上 MA21 + ATR*0.45 才解除。
        """
        x, N = self.x, self.N
        st = self.st[key]
        st[i] = st[i + 1] if (i != start_i and i + 1 < N) else 0
        w0 = wma0[i]
        if w0 is None:
            return
        a = ang[i]
        # 盤整判斷一律看「週 MA8 vs 週 MA21」，跟這個點自己踩哪一條均線無關
        za, zb = x.wma0_s[i], x.wma0_m[i]
        in_zone = has_zone and za is not None and zb is not None and za < zb

        if st[i] == 0:
            if in_zone:
                st[i] = 2
            elif x.l[i] <= w0:
                st[i] = 1

        if st[i] == 1:
            if in_zone:
                st[i] = 2
            elif self._is_w_point(i, key, wma0, ang, prev_marker_block):
                self._add_dc(i, str(key))
                # 「前一天也符合定義」就不採納（原程式看的是 definition 不是 marker）
                prev_def = (i + 1 < N) and (str(key) in self._dc(i + 1))
                if prev_def:
                    st[i] = 1 if x.l[i] <= w0 else 0
                    return
                st[i] = 0
                if self._use_w_point(i, start_i, key, use_map):
                    self.mc[i] = '$%d$' % key
                    if key == 7:
                        st[i] = 2
                return
            elif a is not None and a < self.neg:
                st[i] = 3 if has_zone else 2

        if has_zone and st[i] == 2:
            z = x.buf_zone(i)
            if za is not None and zb is not None and z is not None and za > zb + z:
                st[i] = 3

        end_state = 3 if has_zone else 2
        if st[i] == end_state and x.c[i] >= w0:
            st[i] = 0

    def _is_w_point(self, i, key, wma0, ang, prev_marker_block):
        x, N = self.x, self.N
        if i + 1 >= N:
            return False
        if prev_marker_block and self.mc[i + 1] == '$%d$' % key:
            return False
        a = ang[i]
        if a is None or a < self.neg:
            return False
        w0 = wma0[i]
        if w0 is None or x.c[i] < w0:
            return False
        if not self._red(i):
            return False
        if not self._above_yday_body(i):
            return False
        return self._turn_close(i) is not None

    def _use_w_point(self, i, start_i, key, use_map):
        x = self.x
        k = self._closest(self.mc, tuple(use_map.keys()), i + 1, start_i + 1)
        if k is None:
            return True
        op = use_map.get(self.mc[k])
        if op == 'ge':
            return x.c[i] >= x.c[k]
        if op == 'gt':
            return x.c[i] > x.c[k]
        if op == 'lt':
            return x.c[i] < x.c[k]
        return False

    def _judge_5(self, i, s):
        self._judge_w(i, s, 5, self.x.wma0_s, self.x.wa_s,
                      {'$5$': 'ge', '$6$': 'gt', '$7$': 'gt'}, True, False)

    def _judge_6(self, i, s):
        self._judge_w(i, s, 6, self.x.wma0_m, self.x.w1_m,
                      {'$5$': 'lt', '$6$': 'ge', '$7$': 'gt'}, True, True)

    def _judge_7(self, i, s):
        self._judge_w(i, s, 7, self.x.wma0_l, self.x.w1_l,
                      {'$5$': 'lt', '$6$': 'lt', '$7$': 'ge'}, False, True)

    # ---------- 延伸點 A / B / C / D ----------
    CYCLE_ALL = ('$0$', '$1$', '$2$', '$3$', '$4$', '$5$', '$6$', '$7$')

    def _judge_abcd(self, i, start_i):
        x = self.x
        a = x.da_s[i]
        if a is not None and a <= self.pos:
            return
        if self._ang_turn(x.da_s, i, 1) is not None:
            self._add_de(i, 'A')
            if self._use_A(i, start_i):
                self.me[i] = '$A$'
        else:
            if self._is_D(i):
                self._add_de(i, 'D')
                if self._use_bcd(i, start_i, 'D'):
                    self.me[i] = '$D$'
            if self._is_C(i):
                self._add_de(i, 'C')
                if self._use_bcd(i, start_i, 'C'):
                    self.me[i] = '$C$'
            if self._is_B(i):
                self._add_de(i, 'B')
                if self._use_bcd(i, start_i, 'B'):
                    self.me[i] = '$B$'

    def _use_A(self, i, start_i):
        x = self.x
        if self.me[i] != '':
            return False
        ka = self._closest(self.me, ('$A$',), i + 1, i + self.n_k - 1)
        kc = self._closest(self.mc, self.CYCLE_ALL, i + 1, start_i)
        if kc is not None and (ka is None or kc <= ka):
            if x.c[i] > x.c[kc]:
                return True
        if ka is not None and (kc is None or ka <= kc):
            if x.c[i] > x.c[ka]:
                return True
        return False

    def _is_B(self, i):
        if i + 1 >= self.N:
            return False
        return self.x.c[i] > self.x.c[i + 1]

    def _is_C(self, i):
        x, N = self.x, self.N
        for n in range(1, self.n_k):
            if i + n + 1 >= N:
                return False
            if x.c[i + n] > x.c[i + n + 1]:
                return False
            if x.c[i + n] == x.c[i + n + 1]:
                continue
            break
        if not self._within_yday_body(i):
            return False
        if 'A' in self._de(i + 1):
            return False
        return True

    def _is_D(self, i):
        x, N = self.x, self.N
        if i + 1 >= N:
            return False
        if not self._red(i):
            return False
        if not self._above_yday_body(i):
            return False
        sh = self._turn_close(i)
        if sh is None:
            return False
        tp = self._ang_turn(x.da_s, i, self.n_k - 1)
        if tp is not None and (i + sh) >= tp:
            return False
        if 'A' in self._de(i + 1) or 'D' in self._de(i + 1):
            return False
        return True

    def _use_bcd(self, i, start_i, kind):
        x = self.x
        if self.me[i] != '':
            return False
        tp = self._ang_turn(x.da_s, i, self.n_k - 1)
        if kind == 'B':
            ke = self._closest(self.me, ('$A$', '$B$', '$C$', '$D$'), i + 1, tp)
            kc = self._closest(self.mc, self.CYCLE_ALL, i + 1, start_i)
            if (ke is not None and self.me[ke] == '$C$'
                    and (kc is None or ke <= kc) and x.c[i] > x.c[ke]):
                return True
            if self.rh[i]:
                return True
        else:
            if tp is not None:
                for t in range(i, min(tp, self.N)):
                    if self.rh[t]:
                        return True
        same = self._closest(self.me, ('$%s$' % kind,), i + 1, tp)
        if same is None:
            kc = self._closest(self.mc, self.CYCLE_ALL, i + 1, start_i)
            if kc is not None and x.c[i] > x.c[kc]:
                return True
            if tp is not None:
                ka2 = self._closest(self.me, ('$A$',), tp + 1, self.n_k)
                if ka2 is not None and x.c[tp] > x.c[ka2]:
                    return True
        else:
            if x.c[i] > x.c[same]:
                return True
        return False


# --------------------------------------------------------------------------------------
# 掃描驅動：吃 px_history，算出每一檔「最新一根」的循環點／延伸點
# --------------------------------------------------------------------------------------

SCAN_NAME = "scan_cycle.json"
INTRA_NAME = "scan_intraday.json"    # 盤中那份，不蓋掉收盤的結果
KC_MIN_BARS = 200          # 少於這麼多根就不掃，算出來也不能信
# 回傳給網頁畫在 K 線上的標記。個股頁的 K 線圖最長可以拉到 5 年，所以這裡
# 也留到 5 年份（1300 根）—— 等於「有多少歷史就標多少」。
# 一檔平均多出約 35 個標記，整份 scan_cycle.json 大概 0.9 MB → 3 MB，還在可以接受的範圍。
KC_MARK_BARS = 1300
# 「最近一次出現的循環點」往回找幾根就好 —— 找太遠沒有參考價值，
# 而且「幾根前」這個篩選條件本來就只在小數字時有意義。
KC_LAST_BARS = 260


