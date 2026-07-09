"""
数据源（均已在 quant/trend_select 验证可用，此处自包含）：
- 全市场快照：东财 clist，多镜像主机轮换（扛 502）。
- 日线：东财 push2his kline（klt=101）多镜像轮换。
- 30/60分：新浪 stock_zh_a_minute（东财分钟接口被封）。
- 资金：同花顺 stock_fund_flow_individual（东财资金后端 502）。
"""

from __future__ import annotations
import math
import time
import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd
import requests

import config

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_CLIST_HOSTS = ["push2.eastmoney.com", "1.push2.eastmoney.com", "7.push2.eastmoney.com",
                "push2delay.eastmoney.com", "60.push2.eastmoney.com", "99.push2.eastmoney.com"]
_HIST_HOSTS = ["push2his.eastmoney.com", "1.push2his.eastmoney.com", "7.push2his.eastmoney.com",
               "push2hisdelay.eastmoney.com"]
_good = {}   # host_list id -> 上次成功主机

CACHE_DIR = Path(__file__).resolve().parent / "cache"
(CACHE_DIR / "daily").mkdir(parents=True, exist_ok=True)


def _em_get(hosts: list[str], path: str, params: dict, rounds: int = 3) -> dict:
    """
    多镜像主机轮换 GET，返回 json。优先用上次成功主机。
    东财数据中心 IP（GitHub runner）连接常间歇性被 RemoteDisconnected/502，
    故对全部镜像做 rounds 轮重试、轮间退避，扛住抖动。
    """
    key = id(hosts)
    order = ([_good[key]] if _good.get(key) else []) + [h for h in hosts if h != _good.get(key)]
    sess = requests.Session()
    sess.headers.update({"User-Agent": _UA})
    last = None
    for rnd in range(rounds):
        for h in order:
            try:
                r = sess.get(f"https://{h}{path}", params=params, timeout=20)
                r.raise_for_status()
                j = r.json()
                if j and j.get("data") is not None:
                    _good[key] = h
                    return j
                last = RuntimeError("data 为空")
            except Exception as e:
                last = e
        time.sleep(1.5 * (rnd + 1))     # 轮间退避
    raise last or RuntimeError("所有镜像主机不可用")


# ─────────────── 全市场快照 ───────────────
_SPOT_FIELDS = {"f12": "代码", "f14": "名称", "f2": "最新价", "f3": "涨跌幅",
                "f8": "换手率", "f20": "总市值", "f21": "流通市值"}


def snapshot() -> pd.DataFrame:
    base = {"po": 1, "np": 1, "fltt": 2, "invt": 2, "fid": "f3",
            "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23", "fields": ",".join(_SPOT_FIELDS)}

    def page(pn):
        # 单页失败（多轮重试后仍不行）→ 返回空，不拖垮整表（宁可少几页也别全崩）
        try:
            data = _em_get(_CLIST_HOSTS, "/api/qt/clist/get", {**base, "pn": pn, "pz": 100}).get("data") or {}
        except Exception:
            return 0, []
        diff = data.get("diff") or []
        return data.get("total", 0), (list(diff.values()) if isinstance(diff, dict) else diff)

    total, first = page(1)
    rows = list(first)
    n_pages = math.ceil((total or len(rows)) / 100)
    if n_pages > 1:
        # 低并发，避免突发被东财丢连接（数据中心 IP 尤甚）
        with ThreadPoolExecutor(max_workers=config.SNAPSHOT_WORKERS) as ex:
            for _, diff in ex.map(lambda pn: page(pn), range(2, n_pages + 1)):
                rows.extend(diff)
    df = pd.DataFrame(rows).rename(columns=_SPOT_FIELDS)
    df["代码"] = df["代码"].astype(str).str.zfill(6)
    for c in ["最新价", "涨跌幅", "换手率", "总市值", "流通市值"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ─────────────── 日线 ───────────────
def _secid(code: str) -> str:
    return ("1." if code.startswith("6") else "0.") + code


def load_daily(code: str, use_cache: bool = True) -> pd.DataFrame | None:
    """日线（前复权），列 Open/High/Low/Close/Volume/Turnover，DatetimeIndex。缓存增量。"""
    cache = CACHE_DIR / "daily" / f"{code}.csv"
    cached = None
    if use_cache and cache.exists():
        try:
            cached = pd.read_csv(cache, index_col=0, parse_dates=True)
        except Exception:
            cached = None
    # 首取只要约18个月历史（够 MA20/涨停/回踩判断，远比全量快）
    beg = (dt.date.today() - dt.timedelta(days=550)).strftime("%Y%m%d")
    if cached is not None and len(cached):
        beg = cached.index[-1].strftime("%Y%m%d")     # 从最后一天起补
    params = {"fields1": "f1,f2,f3,f4,f5,f6",
              "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
              "ut": "7eea3edcaed734bea9cbfc24409ed989", "klt": "101", "fqt": "1",
              "secid": _secid(code), "beg": beg, "end": "20500000"}
    for attempt in range(3):
        try:
            data = _em_get(_HIST_HOSTS, "/api/qt/stock/kline/get", params).get("data") or {}
            kl = data.get("klines") or []
            if not kl:
                return cached if cached is not None and len(cached) >= 60 else None
            rows = [x.split(",") for x in kl]
            df = pd.DataFrame(rows, columns=["Date", "Open", "Close", "High", "Low",
                                             "Volume", "Amount", "振幅", "涨跌幅", "涨跌额", "Turnover"])
            df["Date"] = pd.to_datetime(df["Date"])
            for c in ["Open", "High", "Low", "Close", "Volume", "Turnover"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.set_index("Date")[["Open", "High", "Low", "Close", "Volume", "Turnover"]].sort_index()
            if cached is not None and len(cached):
                df = pd.concat([cached[cached.index < df.index[0]], df]).sort_index()
            try:
                df.to_csv(cache, encoding="utf-8-sig")
            except Exception:
                pass
            return df if len(df) >= 60 else None
        except Exception:
            if attempt == 2:
                return cached if cached is not None and len(cached) >= 60 else None
            time.sleep(0.6 * (attempt + 1))
    return None


def load_many_daily(codes: list[str], progress=None):
    """并发拉日线，生成器产出 (code, df)。"""
    total = len(codes)
    done = ok = 0
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as ex:
        futs = {ex.submit(load_daily, c): c for c in codes}
        from concurrent.futures import as_completed
        for fut in as_completed(futs):
            code = futs[fut]
            done += 1
            try:
                df = fut.result()
            except Exception:
                df = None
            if df is not None:
                ok += 1
                yield code, df
            if progress and (done % 50 == 0 or done == total):
                progress(done, total, ok)


# ─────────────── 30/60 分钟（新浪） ───────────────
def _sina_symbol(code: str) -> str:
    return ("sh" if code.startswith("6") else "sz") + code


def load_minute(code: str, period: str = "30", need_bars: int = 20) -> pd.DataFrame | None:
    import akshare as ak
    for attempt in range(3):
        try:
            raw = ak.stock_zh_a_minute(symbol=_sina_symbol(code), period=period, adjust="qfq")
            if raw is None or raw.empty:
                return None
            df = raw.rename(columns={"day": "Date", "open": "Open", "high": "High",
                                     "low": "Low", "close": "Close", "volume": "Volume"})
            for c in ["Open", "High", "Low", "Close", "Volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date")[["Open", "High", "Low", "Close", "Volume"]].dropna().sort_index()
            return df if len(df) >= need_bars else None
        except Exception:
            if attempt == 2:
                return None
            time.sleep(0.7 * (attempt + 1))
    return None


# ─────────────── 资金流（同花顺） ───────────────
_THS_SYM = {"今日": "即时", "3日": "3日排行", "5日": "5日排行", "10日": "10日排行"}


def _parse_amount(s) -> float:
    t = str(s).strip().replace(",", "")
    if t in ("", "-", "--", "nan", "None"):
        return float("nan")
    mult = 1.0
    if t.endswith("亿"):
        mult, t = 1e8, t[:-1]
    elif t.endswith("万"):
        mult, t = 1e4, t[:-1]
    try:
        return float(t) * mult
    except ValueError:
        return float("nan")


def fundflow(indicator: str = "3日") -> dict[str, dict]:
    """返回 {code: {'net': 净额元, 'pct': 0~1分位}}。失败返回空。"""
    import akshare as ak
    try:
        df = ak.stock_fund_flow_individual(symbol=_THS_SYM.get(indicator, "即时")).copy()
    except Exception:
        return {}
    code_col = next((c for c in df.columns if "代码" in c), None)
    net_col = next((c for c in df.columns if "净额" in c), None)
    if not code_col or not net_col:
        return {}
    df["代码"] = df[code_col].astype(str).str.zfill(6)
    df["net"] = df[net_col].map(_parse_amount)
    df = df.dropna(subset=["net"])
    if df.empty:
        return {}
    df["pct"] = df["net"].rank(pct=True)
    return {r["代码"]: {"net": float(r["net"]), "pct": float(r["pct"])} for _, r in df.iterrows()}
