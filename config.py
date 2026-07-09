"""A股回踩低吸盯盘 —— 全部可调参数。策略四（强势股回踩低吸）门槛与盯盘节奏。"""

import os

# ── 股票池基础过滤 ──
KEEP_PREFIX = ("60", "000", "001", "002", "003", "300")   # 沪深主板+中小+创业；跳过科创688/北交所
FLOAT_MKTCAP_MIN = 50e8       # 流通市值下限（元）
MIN_PRICE = 2.0
MIN_LISTED_DAYS = 120

# ── 策略四·日线门槛（预筛用）──
S4_STRONG_LB = 20             # 近 N 日内有涨停（强势基因）
S4_LIMIT_MIN = 1
S4_PULLBACK_HIGH_LB = 8       # 从近 N 日高点回撤
S4_PULLBACK_MIN = 0.02        # 回撤 ≥ 2% 才算回踩（预筛放宽：≥0 也可入池观察，用 PRESCREEN_PULLBACK_MIN）
PRESCREEN_PULLBACK_MIN = 0.0  # 预筛阶段只要求趋势/强势/资金，回踩深度盘中再判
S4_BAND_TOL = 0.02            # 回踩到位：MA10×(1-tol) ≤ 收盘 ≤ MA5×(1+tol)
S4_FUND_INDICATOR = "3日"     # 资金抬头口径
S4_FUND_NET_MIN = 0.0         # 主力净流入 > 此值

# ── 策略四·分钟信号（盘中用）──
S4_KD_LOW_30 = 45            # 30分 KD 低位：D ≤ 此值
S4_KD_LOW_60 = 50            # 60分 KD 低位：D ≤ 此值
S4_M30_NEED = 30
S4_M60_NEED = 20

# ── 盘中盯盘节奏 ──
INTERVAL_SEC = int(os.environ.get("INTERVAL_SEC", "300"))    # 每轮间隔（秒）
RUN_MINUTES = int(os.environ.get("RUN_MINUTES", "340"))      # 单任务连跑分钟数（覆盖交易时段）
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "12"))

# ── 数据起点 ──
DATA_START = "20180101"
