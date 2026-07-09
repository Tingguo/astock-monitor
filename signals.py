"""策略四·分钟信号：30分 & 60分 KD 低位反弹（盘中触发条件）。"""

from __future__ import annotations
import pandas as pd

import config
import datafeeds
import indicators


def _minute_low(code: str, period: str, need: int, kd_low: float):
    """返回 (ok, D值, 说明)。数据不可得 → (None, None, 说明)。"""
    df = datafeeds.load_minute(code, period=period, need_bars=need)
    if df is None:
        return None, None, f"{period}分无数据"
    df = indicators.add_kdj(df)
    last = df.iloc[-1]
    k, d, j = last["K"], last["D"], last["J"]
    if pd.isna(d):
        return None, None, f"{period}分KDJ不足"
    low = d <= kd_low
    turning = (k > d) or (j > k)
    return bool(low and turning), float(d), f"{period}分D={d:.0f}{'低位反弹' if (low and turning) else ('非低位' if not low else '未反弹')}"


def check(code: str) -> dict | None:
    """
    盘中检查一只票是否命中「30分&60分 KD 低位反弹」。命中返回信息 dict，否则 None。
    数据取不到当作未命中（下轮再试）。
    """
    ok30, d30, det30 = _minute_low(code, "30", config.S4_M30_NEED, config.S4_KD_LOW_30)
    if ok30 is not True:
        return None
    ok60, d60, det60 = _minute_low(code, "60", config.S4_M60_NEED, config.S4_KD_LOW_60)
    if ok60 is not True:
        return None
    return {"d30": d30, "d60": d60, "detail": f"{det30}；{det60}"}
