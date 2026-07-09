"""
A股回踩低吸盯盘 —— 入口。

  python monitor.py --mode screen    # 盘后：日线预筛 → watchlist.json
  python monitor.py --mode watch     # 盘中：每5分钟扫 watchlist 的 30/60分低位信号，命中发邮件

时区：交易时段按北京时间(UTC+8)判定；GitHub runner 为 UTC。
"""

from __future__ import annotations
import sys
import json
import time
import argparse
import datetime as dt
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import config
import screen
import signals as sig
import notify

ROOT = Path(__file__).resolve().parent
WATCHLIST = ROOT / "watchlist.json"


def _cst_now() -> dt.datetime:
    return dt.datetime.utcnow() + dt.timedelta(hours=8)


def _in_trading(now_cst: dt.datetime) -> bool:
    t = now_cst.time()
    if now_cst.weekday() >= 5:
        return False
    return (dt.time(9, 30) <= t <= dt.time(11, 30)) or (dt.time(13, 0) <= t <= dt.time(15, 1))


# ─────────────── 盘后预筛 ───────────────
def run_screen():
    watch = screen.build_watchlist()
    payload = {
        "date": _cst_now().strftime("%Y-%m-%d"),
        "generated_at": _cst_now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "count": len(watch),
        "stocks": watch,
    }
    WATCHLIST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[预筛] 写出 {WATCHLIST}（{len(watch)} 只）")
    # 预筛概要邮件（可选，便于确认当天池子）
    if watch:
        top = "\n".join(f"  {w['code']} {w['name']} 涨停{w['n_limit']}次(最近{w['days_since_limit']}日前) "
                        f"资金{w['fund_net_yi']}亿" for w in watch[:20])
        try:
            notify.send_email(f"[A股盯盘] 今日回踩候选池 {len(watch)} 只",
                              f"日期 {payload['generated_at']}\n次日盘中将盯这些票的30/60分低位信号：\n\n{top}")
        except Exception as e:
            print(f"[预筛] 概要邮件发送失败（不影响）：{e}")


# ─────────────── 盘中盯盘 ───────────────
def run_watch():
    if not WATCHLIST.exists():
        print("[盯盘] 无 watchlist.json，先跑 --mode screen。退出。")
        return
    data = json.loads(WATCHLIST.read_text(encoding="utf-8"))
    stocks = data.get("stocks", [])
    name_by = {s["code"]: s["name"] for s in stocks}
    codes = [s["code"] for s in stocks]
    if not codes:
        print("[盯盘] 候选池为空，退出。")
        return
    print(f"[盯盘] 候选 {len(codes)} 只（{data.get('generated_at')}）。每 {config.INTERVAL_SEC}s 扫一轮，"
          f"连跑 {config.RUN_MINUTES} 分钟。")

    alerted: set[str] = set()
    end = time.time() + config.RUN_MINUTES * 60
    rounds = 0
    while time.time() < end:
        cst = _cst_now()
        if _in_trading(cst):
            rounds += 1
            hits = []
            for code in codes:
                if code in alerted:
                    continue
                try:
                    r = sig.check(code)
                except Exception:
                    r = None
                if r:
                    hits.append((code, r))
            if hits and _alert(hits, name_by, cst):     # 发信成功才计入去重
                alerted.update(c for c, _ in hits)
            print(f"[{cst:%H:%M}] 第{rounds}轮扫描完，新命中 {len(hits)}，累计 {len(alerted)}/{len(codes)}")
        elif cst.time() > dt.time(15, 1):
            print(f"[{cst:%H:%M}] 已收盘，结束盯盘。")
            break
        else:
            print(f"[{cst:%H:%M}] 非交易时段，等待 ...")
        time.sleep(config.INTERVAL_SEC)
    print(f"[盯盘] 结束。今日共报警 {len(alerted)} 只。")


def _alert(hits, name_by, cst) -> bool:
    """发命中邮件。成功返回 True（用于计入当日去重），失败返回 False（下轮重试）。"""
    lines = []
    for code, r in hits:
        lines.append(f"● {code} {name_by.get(code,'')}\n    {r['detail']}\n    (30分D={r['d30']:.0f} / 60分D={r['d60']:.0f})")
    body = (f"回踩低吸信号触发  {cst:%Y-%m-%d %H:%M} CST\n"
            f"（强势涨停趋势股回踩到MA5-10，30分&60分KD低位反弹）\n\n"
            + "\n\n".join(lines)
            + "\n\n仅供研究，非投资建议。注意结合大盘与个股具体位置判断。")
    subj = f"[A股低吸] {len(hits)}只命中: " + "、".join(f"{name_by.get(c,c)}" for c, _ in hits[:3])
    try:
        notify.send_email(subj, body)
        return True
    except Exception as e:
        print(f"[盯盘] 邮件发送失败（下轮重试）：{e}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["screen", "watch"], required=True)
    args = ap.parse_args()
    if args.mode == "screen":
        run_screen()
    else:
        run_watch()


if __name__ == "__main__":
    main()
