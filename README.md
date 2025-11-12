# Wind 夜间委托自动化系统

本项目基于 WindPy，按照“收盘批处理 → 夜间委托 → 次日核对”的流程自动化完成股票池行情获取、信号筛选、委托下单以及成交对账。

## 功能概览
- **数据处理**：从 `stocks.xlsx` 读取股票池，批量调用 `w.wsd` 下载行情与 Chaikin 指标，维护增量 CSV 与持仓状态（SQLite）。
- **信号与下单**：SignalEngine 判断买/卖信号，PendingOrderBuilder 根据涨跌幅与 tick 规则生成待下单 JSON，OrderExecutor 在夜间 21:30+ 批量调用 `w.torder`。
- **次日对账**：TradeReconciler 在 T+1 查询 `w.tquery("Order"/"Trade")`，更新 `positions`、输出 `data/trades/` CSV 与 Markdown 报告。
- **CLI 管理**：`manage.py` 提供 `run-eod`、`run-orders`、`reconcile` 等命令，覆盖全流程。

## 环境准备
1. **Python**：3.11+，推荐虚拟环境。
2. **依赖安装**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **WindPy（macOS）**
   - 运行仓库中的 `python install_windpy.py`，将 `/Applications/Wind API.app/Contents/python/WindPy.py` 软链接到当前环境。
   - 执行 `python autologin_test.py` 确认 `~/.Wind` 自动登录开启（`isAutoLogin="1"`）。
4. **配置文件**
   - 复制 `config.example.yml` 为 `config.yml`，填写真实账号与路径。
   - 密码建议写成 `env:WIND_PWD` 并在终端中 `export WIND_PWD=xxx`。

## 快速开始
```bash
# 初始化目录 / 数据库
python manage.py init

# 收盘批处理：下载行情 → 信号 → 待下单
python manage.py run-eod --stocks-file stocks.xlsx --trade-date 20250226

# 夜间 21:30+ 执行待下单
python manage.py run-orders --trade-date 20250226

# 次日 09:30+ 对账
python manage.py reconcile --trade-date 20250226
```
> `--trade-date` 可缺省（默认当天）。`--stocks-file` 默认 `stocks.xlsx`。

## 其他常用命令
- `python manage.py validate-config`：检查配置摘录。
- `python manage.py load-stocks`：查看股票池加载结果。
- `python manage.py fetch-history 600000.SH`：单只股票手动下载行情。
- `python manage.py list-positions`：打印持仓状态表。
- `python manage.py build-pending`：在已有行情 CSV 基础上单独生成待下单 JSON。

## 目录结构
```
data/
├── stocks/            # 行情 CSV
├── pending_orders/    # 夜间任务 JSON
├── trades/            # 对账 CSV
├── reports/           # Markdown 报告
└── trading.db         # SQLite 持仓库
logs/
└── app.log            # 轮转日志
```

## 测试
```bash
python -m pytest -q
```
当前提供了 pricing、config、signal、pending-order 等单元测试；后续可接入 WindPy mock 做集成测试。

## 注意事项
- 下单价格按启发式推断（主板 ±10%，ST ±5%，创业/科创/北交 ±20%，tick=0.01/0.001）；若需更精确，可接入 Wind 字段或交易所规则。
- 夜间下单依赖券商接受夜盘预约委托；实际交易需事先确认柜台支持。
- 请妥善保管 `config.yml` 和日志中的敏感信息；部署时可结合 SSH/密钥管理。

欢迎根据 `task.md` 继续扩展多账户、监控、自动调度等特性。***
