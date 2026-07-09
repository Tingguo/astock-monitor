# A股回踩低吸盯盘（云端 + 邮件报警）

每天收盘后用日线预筛出「强势涨停趋势股」候选池，次日盘中每 5 分钟扫这些票的
**30/60 分钟 KD 低位反弹**信号，命中即发 Gmail 邮件通知。只做买入低吸提醒（做多）。

> ⚠️ 仅供研究学习，不构成投资建议。信号仅是提示，务必结合大盘与个股位置自行判断。

方法论来自「策略四·强势股回踩低吸」：流畅上涨的强势股回踩到 MA5-MA10 支撑带，
用小级别（30/60分）KD 低位反弹 + 资金抬头确认低吸点。

## 工作方式（两段式，GitHub Actions 免费托管）

| 阶段 | 触发 | 做什么 |
|---|---|---|
| 盘后预筛 `screen.yml` | 每天 ~15:15(北京)，`monitor.py --mode screen` | 全市场→策略四日线门槛→`watchlist.json`，提交回仓库 |
| 盘中盯盘 `watch.yml` | 每天 ~09:25(北京) 启动，`monitor.py --mode watch` | 单任务循环每5分钟扫 watchlist 的30/60分低位信号，命中发邮件 |

- 5 分钟节奏由任务内 `sleep` 控制，**不依赖 cron 精度**（cron 只每天点火）。
- 当日去重：同一票命中后当天不再重复报；跨日由新 watchlist 重置。
- 非交易时段/收盘后自动跳过或结束。

## 预筛门槛（策略四日线，`config.py` 可调）
- 趋势仍强：MA5≥MA10≥MA20 且 MA20 上行
- 强势基因：近20日出现过涨停（主板≥9.9%/创业≥19.5%）
- 资金抬头：3日主力净流入 > 0

## 盘中触发（`config.py` 可调）
- 30分 KD 低位（D≤45）反弹 **且** 60分 KD 低位（D≤50）反弹

## 数据源（自带容错）
- 全市场快照：东财 clist，**多镜像主机轮换**（扛 502）
- 日线：东财 push2his kline，镜像轮换，`cache/daily` 增量
- 30/60分：**新浪** `stock_zh_a_minute`（东财分钟接口被封）
- 资金：**同花顺** `stock_fund_flow_individual`（东财资金后端 502）

## 部署（复用 Hermes 那套）
1. 新建 **公开** GitHub 仓库（公开=无限免费 Actions 分钟），推这个目录。
2. 仓库 Settings → Secrets and variables → Actions 加三个 Secret：
   - `GMAIL_USER`（发信 Gmail）
   - `GMAIL_APP_PASSWORD`（Gmail 16 位应用专用密码）
   - `MAIL_TO`（收件邮箱）
3. Settings → Actions → General → Workflow permissions 选 **Read and write**（预筛要提交 watchlist.json）。
4. Actions 页手动 `Run workflow` 各跑一次验证；之后按 cron 每交易日自动跑。

## 本地运行（兜底 / 调试）
若境外数据中心 IP 访问行情接口受阻，可在本机（如 Windows 计划任务）跑：
```bash
pip install -r requirements.txt
python monitor.py --mode screen      # 盘后
RUN_MINUTES=340 INTERVAL_SEC=300 python monitor.py --mode watch   # 盘中
```

## 已知风险
GitHub 数据中心（境外）IP 访问东财/新浪/同花顺可能被地域限流或变慢，需**首次部署实测**。
Hermes 实测 GitHub IP 能过 eastmoney，但行情接口稳定性以实跑为准；受阻则用本机兜底。
