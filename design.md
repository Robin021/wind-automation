## 设计文档：Wind 夜间委托自动化系统

### 0. 环境与依赖
- WindPy 在 macOS 上可借助官方 **Wind API.app** 提供的 Python 包，将 `/Applications/Wind API.app/Contents/python/WindPy.py` 通过 `install_windpy.py` 脚本软链接到当前虚拟环境（示例脚本已在仓库 `install_windpy.py` 提供）。
- 自动登录配置可参考 `autologin_test.py` 读取 `~/.Wind/WFT/users/Auth/user.config`，确认 `isAutoLogin` 为 `1` 后才能在 CLI 环境中无UI登录。
- `requirements.txt` 仅列出除 WindPy 外的 pip 依赖；在 macOS 环境中运行前需手动执行 `python install_windpy.py` 并保证 `~/Library/Containers/com.wind.mac.api/Data/.Wind` 已映射至 `~/.Wind`。

### 1. 目标与背景
- 满足 `requirements.md` 中定义的三个阶段：收盘批处理、夜间 21:30 之后批量委托、次日 09:30 以后结果核对。
- 自动化读取股票池、下载行情与 Chaikin 指标（`chaikin2`）、生成信号并管理持仓状态。
- 对接 WindPy 的交易接口（`w.tlogon / w.torder / w.tquery / w.tlogout`），实现夜间预委托并在次日确认成交。

### 2. 范围与非目标
**范围**
1. 单账户运行（后续可扩展多账户）。
2. A 股标的（含 SH、SZ、不排除创业/科创/北交所）及 ST 特殊涨跌幅规则。
3. 本地 CSV + SQLite 数据管理，结合 JSON 待下单任务。

**非目标**
- 不涉及实时行情、日内交易、风控扩展、自动资金划拨。
- 不处理多策略组合、回测或云端部署。

### 3. 时间轴与流程
| 阶段 | 时间窗口 | 关键任务 |
| --- | --- | --- |
| 收盘批处理 | T 日收盘后 | 读取股票池 → 批量 `w.wsd` → 更新 CSV → SignalEngine 更新 `positions` → 生成 `pending_orders` JSON (`manage.py run-eod`) |
| 夜间委托 | 当晚 21:30+ | 启动 WindPy → `w.tlogon` → 读取待下单任务 → 计算价位限制 → `w.torder` 批量委托 → 记录 RequestID/日志 |
| 次日核对 | T+1 日 09:30+ | 再次登录 → `w.tquery("Order"/"Trade")` 依据 RequestID/代码对账 → 更新 `positions`/`trades` → 生成核对报告 |

### 4. 架构概览
```
stocks.xlsx ─┐
             ├─▶ DataFetcher ──▶ CSV (data/stocks)
WindPy API ──┤                   │
             │                   ▼
             └─▶ SignalEngine ─▶ PositionStore (SQLite/CSV)
                                    │
                                    ▼
                              PendingOrderBuilder ─▶ pending_orders JSON
                                    │
                                    ▼
                              OrderExecutor (21:30+) ─▶ Wind torder
                                    │
                                    ▼
                              TradeReconciler (T+1) ─▶ trades CSV / status sync
                                    │
                                    ▼
                               Reports / Alerts
```

### 5. 组件设计
#### 5.1 ConfigManager
- 读取 `config.yml`（新建，含 Wind 账号、BrokerID、DepartmentID、指标参数、重试策略、目录路径）。
- 提供数据类访问，供各模块依赖注入。

#### 5.2 StockPoolLoader
- 使用 `openpyxl` 或 `pandas.read_excel` 解析 `stocks.xlsx`。
- 过滤空行/非法代码；输出 `List[str]`。
- 将无效代码记录到日志并写入 `data/invalid_codes.log` 以备核查。

#### 5.3 DataFetcher
- 顺序或并发（ThreadPoolExecutor）逐代码调用 `w.wsd(code, fields, begin, end, options)`。
- 支持增量更新：读取 `data/stocks/{code}.csv`，对比最后日期，补齐缺失部分后写回。
- 统一输出 `pandas.DataFrame`，字段含 `date,open,high,low,close,volume,turn,cho,macho,update_time`。
- 失败时重试（默认 3 次，指数退避 1/2/4 秒），记录错误类别。

#### 5.4 SignalEngine
- 对每支股票运行指标逻辑：
  - 买入：`CHO_t > CHO_{t-1}`。
  - 卖出：如果持仓且 `CHO_t < CHO_{t-1}` 则标记 `pending_sell_since = t`；若 `CHO_{t+1} < CHO_t` 则发出卖出信号。
- 生成 `Signal` 对象：`code`, `side`, `price_hint`, `signal_time`.
- 写回 `positions` 状态，更新 `status`, `pending_sell_since`, `last_signal_time`。

#### 5.5 PositionStore
- SQLite (`data/trading.db`, 表 `positions`) 为主，CSV 仅作备份导出。
- 表结构：
  ```
  CREATE TABLE positions (
    code TEXT PRIMARY KEY,
    status INTEGER NOT NULL,          -- 0未持仓,1已买入,2已卖出
    hold_volume INTEGER DEFAULT 0,
    last_buy_price REAL,
    last_sell_price REAL,
    pending_sell_since TEXT,
    last_signal_time TEXT,
    update_time TEXT NOT NULL
  );
  ```
- 包装 CRUD：`get_position(code)`, `upsert_position(data)`, `list_positions(filter)`。

#### 5.6 PendingOrderBuilder
- 将 `Signal` 列表按交易日分组输出 `data/pending_orders/{trade_date}.json`。
- JSON 格式：`{"code": "...", "side": "Buy|Sell", "volume": 100, "limit_price": 12.34, "signal_time": "...", "request_id": null}`。
- 同步写人类可读汇总（可选 `reports/{trade_date}_orders.md`）。

#### 5.7 OrderExecutor
- 主要流程：
  1. `WindSession`：封装 `w.start() / w.isconnected() / w.tlogon / w.tlogout`。
  2. 计算涨跌停价格：通过前收盘价和涨跌幅限制 `limit_pct` 得到 `limit_up/down`，并按市场 tick size (`0.01` 或 `0.001`) 取整。
  3. 对每条待下单记录调用 `w.torder`，传入 `SecurityCode`, `TradeSide`, `OrderPrice`, `OrderVolume`, `options`（含 `OrderType=LMT`、必要时 `LogonID`）。
  4. 将 Wind 返回的 `RequestID/ErrorCode` 写回待下单 JSON（新增字段 `request_id`、`order_response_ts`）。
  5. 失败记录：写 `logs/app.log`，并输出到 `data/orders_failed/{trade_date}.csv`。

#### 5.8 TradeReconciler
- 次日脚本读取上一夜 `pending_orders`，依据 `RequestID` 调用 `w.tquery("Order")`，若缺字段再用 `WindCode` 或 `w.tquery("Trade")` 兜底。
- 更新 `positions`：若买入成交则 `status=1`, `hold_volume=traded_volume`, `last_buy_price=traded_price`；卖出全部成交则 `status=0`, `hold_volume=0`, `last_sell_price=traded_price`。
- 输出 `data/trades/{YYYYMMDD}.csv`，字段 `[code,side,status,order_price,traded_price,traded_volume,order_number,request_id]`，并生成核对报告（成功/部分成交/失败）。

#### 5.9 Logging & Monitoring
- Python `logging`，轮转文件 `logs/app.log`（保留 30 天）。
- 关键事件：登录、数据下载、信号统计、下单请求与响应、查询返回、异常。
- 可选：发送邮件/IM 报警，当夜间批处理失败或出现重大错误（如无法登录）。

### 6. 数据与文件结构
| 存储 | 路径 | 结构 |
| --- | --- | --- |
| 行情 CSV | `data/stocks/{code}.csv` | `date,open,high,low,close,volume,turn,cho,macho,update_time` |
| 持仓 SQLite | `data/trading.db` | 表 `positions`，字段见 5.5 |
| 待下单 JSON | `data/pending_orders/{YYYYMMDD}.json` | 数组，每项含 `code,side,volume,limit_price,signal_time,request_id` |
| 交易记录 CSV | `data/trades/{YYYYMMDD}.csv` | `code,side,status,order_price,traded_price,traded_volume,order_number,request_id` |
| 日志 | `logs/app.log` | 统一 INFO/ERROR |

### 7. Wind API 交互细节
1. **初始化**
   ```python
   from WindPy import w
   w.start(waitTime=60)
   assert w.isconnected()
   logon = w.tlogon(BrokerID, DepartmentID, LogonAccount, Password, AccountType)
   LOGON_ID = logon.Data[0][0]
   ```
2. **行情**
   ```python
   w.wsd(code, "open,high,low,close,volume,turn,CHO,MACHO", begin, end,
         "PriceAdj=B;Days=Trading;Fill=Previous", usedf=True)
   ```
3. **下单**
   ```python
   w.torder(code, side, price, volume,
            f"OrderType=LMT;LogonID={LOGON_ID}")
   ```
4. **查询**
   ```python
   w.tquery("Order", f"LogonID={LOGON_ID};RequestID={req_id}")
   w.tquery("Trade", f"LogonID={LOGON_ID};WindCode={code}")
   ```
5. **登出**
   ```python
   w.tlogout(LOGON_ID)
   w.stop()
   ```

### 8. 价格限制计算
```python
def calc_limit_price(prev_close, pct, direction, tick):
    raw = prev_close * (1 + pct) if direction == "Buy" else prev_close * (1 - pct)
    scaled = math.floor(raw / tick + 1e-8) * tick if direction == "Sell" else math.ceil(raw / tick - 1e-8) * tick
    return round(scaled, 3 if tick == 0.001 else 2)
```
- `pct` 根据股票类型确定：普通 0.10，ST 0.05，创业/科创/北交所 0.20，上市首日自定义。
- 需要从行情数据或 Wind 额外字段获取 `limit_pct`, `tick_size`。

### 9. 错误处理策略
| 类别 | 策略 |
| --- | --- |
| WindPy 断连/登录失败 | 重试登录 3 次；失败则终止任务并报警。 |
| API 超时/错误码 !=0 | 指数退避重试；记录 `ErrorCode/ErrorMsg`。 |
| 数据缺失 | 标记该股票为 `data_issue`，写入状态库并跳过下单。 |
| 订单失败 | 记录失败原因，不重试；由人工在次日核查。 |
| SQLite/文件 IO | 原子写（临时文件 + rename），定期备份 `data/`。 |

### 10. 配置与密钥
- `config.yml` 示例：
  ```yaml
  wind:
    broker_id: "0000"
    department_id: "0"
    logon_account: "WFTxxxx01"
    password: "env:WIND_PWD"
    account_type: "SHSZ"
  strategy:
    short: 3
    long: 24
    n: 24
    min_history_days: 60
  orders:
    volume_per_trade: 100
    retry: {attempts: 3, backoff: [1, 2, 4]}
  paths:
    data_root: "data"
    log_file: "logs/app.log"
  ```
- 密码存储在环境变量或本地凭证管理，程序启动时注入。

### 11. 测试与验证
- **单元测试**：价格计算、信号逻辑、数据库 CRUD。
- **集成测试**：对 WindPy 使用 Mock 层，验证 `w.wsd` / `w.torder` 调用参数。
- **回放测试**：使用历史 CSV 驱动，模拟多天数据验证 `pending_sell_since` 和委托生成。
- **演练**：在 Wind 模拟账户跑通完整流程，确保夜间委托与次日对账逻辑正确。
- 本地执行 `pytest` 运行自动化测试套件。

### 12. 可扩展性与后续工作
- 多账户支持：在 `pending_orders` 中携带 `account_id`，`OrderExecutor` 按账号分组登录。
- 定时调度：使用 `cron` 或 `APScheduler` 自动触发三个阶段。
- 监控仪表盘：暴露 Prometheus 指标（信号数量、下单成功率）。
- 策略拓展：引入 `MACHO`/量能过滤或其他指标，或连接风控模块（资金占比、同向持仓上限）。
