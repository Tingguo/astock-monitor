"""
盘后日线预筛：从全市场主板筛出「强势涨停趋势股」watchlist（策略四日线门槛，去掉分钟部分）。
次日盘中对这些票盯 30/60 分低位信号。
"""

from __future__ import annotations
import datetime as dt
import numpy as np
import pandas as pd

import config
import datafeeds
import indicators


def _limit_ret(code: str) -> float:
    return 0.195 if code.startswith("300") else 0.099


def _daily_ok(code: str, df: pd.DataFrame, flows: dict) -> dict | None:
    """通过策略四日线门槛返回要点 dict，否则 None。"""
    if len(df) < config.MIN_LISTED_DAYS:
        return None
    df = indicators.add_ma(df, periods=(5, 10, 20))
    last = df.iloc[-1]
    ma5, ma10, ma20, close = last["MA5"], last["MA10"], last["MA20"], last["Close"]
    if any(pd.isna(v) for v in (ma5, ma10, ma20)):
        return None
    # 趋势仍强
    if not (ma5 >= ma10 >= ma20):
        return None
    if not (ma20 > df["MA20"].iloc[-6]):
        return None
    # 强势基因：近 N 日涨停
    ret = df["Close"].pct_change()
    lim = ret.iloc[-config.S4_STRONG_LB:] >= _limit_ret(code) - 0.005
    n_lim = int(lim.sum())
    if n_lim < config.S4_LIMIT_MIN:
        return None
    days_since = int(len(lim) - 1 - np.where(lim.values)[0][-1]) if lim.any() else 99
    # 资金抬头
    fnet = flows.get(code, {}).get("net")
    if flows and (fnet is None or fnet <= config.S4_FUND_NET_MIN):
        return None
    return {
        "code": code,
        "ma5": round(float(ma5), 2), "ma10": round(float(ma10), 2), "ma20": round(float(ma20), 2),
        "close": round(float(close), 2),
        "n_limit": n_lim, "days_since_limit": days_since,
        "fund_net_yi": round((fnet or 0) / 1e8, 2) if fnet is not None else None,
    }


def build_watchlist(log=print) -> list[dict]:
    log("[预筛] 拉全市场快照 ...")
    spot = datafeeds.snapshot()

    def base_ok(r):
        code, name = r["代码"], str(r["名称"])
        if not code.startswith(config.KEEP_PREFIX):
            return False
        if "ST" in name or "退" in name:
            return False
        if pd.isna(r.get("最新价")) or r["最新价"] < config.MIN_PRICE:
            return False
        if pd.isna(r.get("流通市值")) or r["流通市值"] < config.FLOAT_MKTCAP_MIN:
            return False
        return True

    uni = spot[spot.apply(base_ok, axis=1)]
    # 用快照的「60日涨幅」预筛出强势股，把逐只下载日线的数量从数千砍到几百（云端提速关键）
    if "60日涨幅" in uni.columns:
        strong = uni[pd.to_numeric(uni["60日涨幅"], errors="coerce") >= config.PRESCREEN_GAIN60_MIN * 100]
        strong = strong.sort_values("60日涨幅", ascending=False).head(config.PRESCREEN_MAX)
        log(f"[预筛] 基础过滤 {len(uni)} 只 → 60日涨幅≥{config.PRESCREEN_GAIN60_MIN*100:.0f}% 强势 {len(strong)} 只")
        uni = strong
    name_by = dict(zip(uni["代码"], uni["名称"]))
    codes = list(uni["代码"])
    log(f"[预筛] 待下载日线 {len(codes)} 只，取资金流 + 逐只日线 ...")
    flows = datafeeds.fundflow(config.S4_FUND_INDICATOR)

    watch = []

    def prog(done, total, ok):
        log(f"  日线 {done}/{total} 有效 {ok}，已入池 {len(watch)}")

    for code, df in datafeeds.load_many_daily(codes, progress=prog):
        info = _daily_ok(code, df, flows)
        if info:
            info["name"] = name_by.get(code, "")
            watch.append(info)

    watch.sort(key=lambda x: (x["days_since_limit"], -(x["fund_net_yi"] or 0)))
    log(f"[预筛] 入池 {len(watch)} 只强势涨停趋势股")
    return watch
