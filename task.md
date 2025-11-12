## Task Breakdown (Wind 夜间委托自动化系统)

### Phase 0 · 基础设施
1. **环境/依赖清单**
   - 明确 Python 版本、`WindPy`, `pandas`, `openpyxl`, `SQLAlchemy`/`sqlite3`、日志库等。
   - macOS：执行 `python install_windpy.py` 将 `/Applications/Wind API.app/Contents/python/WindPy.py` 链接到当前环境，并用 `autologin_test.py` 校验 `~/.Wind` 自动登录配置。
   - 补充 `requirements.txt` / `poetry` 配置，并验证 WindPy 可在目标环境安装。
2. **配置管理**
   - 定义 `config.yml` 模板与示例，支持账号、指标、重试、路径等字段（见 design.md §10）。
   - 实现 `ConfigManager`：加载 YAML、解析环境变量占位、校验必填项。
3. **目录初始化脚本**
   - 创建 `data/`, `logs/`, `reports/`, `data/pending_orders/`, `data/trades/`, `data/stocks/` 等目录。
   - 可提供 CLI（如 `python manage.py init`）一次性创建。

### Phase 1 · 数据与状态
4. **StockPoolLoader 模块**
   - 解析 `stocks.xlsx`，过滤无效行，输出代码列表。
   - 无效代码写入 `data/invalid_codes.log` 并在日志中提示。
5. **行情 DataFetcher**
   - 封装 `w.wsd` 调用，逐代码获取多字段并落地 CSV（增量更新）。
   - 支持重试、异常捕获、统计下载耗时。
6. **PositionStore（SQLite）**
   - 建库脚本 & 迁移（`positions` 表结构见 design.md §5.5）。
   - 提供 CRUD 接口、事务封装、CSV 备份导出。
7. **SignalEngine**
   - 读取最新行情+持仓状态，执行买入/卖出/观察逻辑，更新 `pending_sell_since`。
   - 产出标准化的 `Signal` 列表供后续任务使用。
8. **PendingOrderBuilder**
   - 将信号转为 `data/pending_orders/{YYYYMMDD}.json`，含 `limit_price`,`volume`,`signal_time`。
   - 可选生成 `reports/{date}_orders.md` 供人工审核。

### Phase 2 · 夜间下单
9. **WindSession 封装**
   - 包括 `w.start`, `w.isconnected`, `w.tlogon`, 自动重试与 `w.tlogout`.
   - 统一管理 `LogonID`, 失败时写日志并返回错误。
10. **价格限制计算模块**
    - 根据股票属性（ST/科创/北交）确定涨跌幅和 tick size。
    - 提供 `calc_limit_price(prev_close, direction)` API，供下单前调用。
11. **OrderExecutor**
    - 读取 pending JSON，按顺序或批量提交 `w.torder`。
    - 将 `RequestID/ErrorCode` 写回 JSON，追加 `order_response_ts`，并输出失败 CSV。
12. **夜间日志/监控**
    - 标准化日志格式（信息级别、RequestID、耗时）。
    - 可选：提供 CLI 命令 `python main.py night-order --date YYYYMMDD`.

### Phase 3 · 次日对账
13. **TradeReconciler**
    - 登录后根据 `RequestID`/`WindCode` 查询 `w.tquery("Order"/"Trade")`。
    - 更新 `positions` 状态、`last_buy_price` 等，并输出 `data/trades/{YYYYMMDD}.csv`。
14. **对账报告**
    - 汇总成功/部分成交/失败列表，写入 `reports/{date}_reconcile.md`。
    - 若存在失败/异常，触发报警（邮件/IM 占位）。

### Phase 4 · 运行与保障
15. **错误处理与重试**
    - 按 design.md §9 实现统一重试装饰器、异常分类。
16. **日志轮转与备份**
    - `logging.handlers.RotatingFileHandler` 或 `TimedRotatingFileHandler`。
    - 定期将 `data/` 目录打包（可脚本化）。
17. **测试体系**
    - 单元：价格计算、信号逻辑、PositionStore。
    - 集成：Mock WindPy，验证 `w.wsd`、`w.torder`、`w.tquery` 参数。
    - 回放：使用历史样本驱动 end-to-end 流程。
18. **运维脚本**
    - 定时调度（cron/APScheduler）样例，用于自动触发三阶段任务。
    - 运行手册：记录启动命令、常见故障排查、Wind 登录要求。

### Nice-to-have / 后续扩展
19. **多账户支持设计**
    - 扩展 `pending_orders` schema，支持 `account_id`、多 `LogonID` 并发处理。
20. **监控指标**
    - 暴露信号数量、下单成功率、错误率，可后续接入 Prometheus/Grafana。
21. **策略拓展 Hooks**
    - 预留 `filters/` 接口，方便增加 `MACHO`、量能、风控模块。
