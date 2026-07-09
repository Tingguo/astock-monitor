"""技术指标：MA（收盘 SMA）与 KDJ（通达信 9,3,3）。自 A_stock/indicators.py 精简。"""

import pandas as pd


def add_ma(df: pd.DataFrame, periods=(5, 10, 20)) -> pd.DataFrame:
    for p in periods:
        df[f"MA{p}"] = df["Close"].rolling(p).mean()
    return df


def add_kdj(df: pd.DataFrame, n=9, k_period=3, d_period=3) -> pd.DataFrame:
    low_n = df["Low"].rolling(n).min()
    high_n = df["High"].rolling(n).max()
    rsv = (df["Close"] - low_n) / (high_n - low_n).replace(0, 1e-12) * 100
    df["K"] = rsv.ewm(alpha=1 / k_period, adjust=False).mean()
    df["D"] = df["K"].ewm(alpha=1 / d_period, adjust=False).mean()
    df["J"] = 3 * df["K"] - 2 * df["D"]
    return df
