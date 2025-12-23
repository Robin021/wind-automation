# Wind 夜间委托自动化系统

本项目基于 WindPy，按照“收盘批处理 → 夜间委托 → 次日核对”的流程自动化完成股票池行情获取、信号筛选、委托下单以及成交对账。

## 功能概览
- **数据处理**：从 `stocks.xlsx` 读取股票池，批量调用 `w.wsd` 下载行情（OHLCV、TURN 等）。项目在本地按需求计算 Chaikin 指标（CHO/MACHO），无需请求 Wind 端指标字段。
- **信号与下单**：SignalEngine 判断买/卖信号，PendingOrderBuilder 根据涨跌幅与 tick 规则生成待下单 JSON，OrderExecutor 在夜间 21:30+ 批量调用 `w.torder`。
- **次日对账**：TradeReconciler 在 T+1 查询 `w.tquery("Order"/"Trade")`，更新 `positions`、输出 `data/trades/` CSV 与 Markdown 报告。
- **CLI 管理**：`manage.py` 提供 `run-eod`、`run-orders`、`reconcile` 等命令，覆盖全流程。

## 环境准备
1. **Python**：3.9+，推荐虚拟环境。
2. **依赖安装**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
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

## Web API / 前端开发
```bash
# 后端 API（FastAPI）
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 前端（Vite）
cd frontend
npm install
npm run dev
```

## Docker 部署
```bash
# 构建并启动（前端 Nginx + 后端 FastAPI）
docker compose up -d --build
```
- 环境变量：默认读取项目根目录 `.env.local`
- 数据目录：`./data`、`./logs` 会挂载到容器内
- 证书目录：`./backend/certs` 需包含微信支付证书/公钥（若使用微信支付回调验签）

## 生产环境变量（.env.local）
微信支付 V3 需要以下配置（敏感信息请勿提交仓库）：
```bash
WECHAT_PAY_MOCK=false
WECHAT_PAY_MCHID=你的商户号
WECHAT_PAY_MERCHANT_SERIAL_NO=商户证书序列号
WECHAT_PAY_MERCHANT_PRIVATE_KEY_PATH=backend/certs/apiclient_key.pem
WECHAT_PAY_API_V3_KEY=32字节APIv3Key
WECHAT_PAY_NOTIFY_URL=https://你的域名/api/v1/payments/wechat/notify
WECHAT_PAY_APPID_MP=公众号AppID
WECHAT_PAY_APPID_MINI=小程序AppID(可选)
WECHAT_PAY_PLATFORM_CERT_PATH=backend/certs/wechatpay_platform.pem
WECHAT_PAY_PLATFORM_SERIAL_NO=平台证书序列号或公钥ID
```

## 用 Docker 启动 Web API
```bash
# 构建并启动
docker compose up -d --build

# 查看日志
docker compose logs -f backend
```

## 可视化仪表盘（Dashboard）
- 生成仪表盘：
  ```bash
  python manage.py dashboard --trade-date 20250226
  ```
- 控制台将显示持仓/待下单/成交的摘要与前 10 行预览；完整 HTML 报告输出到：
  - `data/reports/dashboard_20250226.html`
- HTML 报告内置：按代码过滤（搜索框）、状态彩色标记（Submitted/Failed 等）。

## 终端 TUI（彩色表格）
```bash
python manage.py tui --trade-date 20250226 --filter 600 --rows 30
```
- 依赖 `rich`（已在 `requirements.txt` 中）；按代码子串筛选，快速查看 Pending/Positions/Trades。

## Web 面板（Streamlit）
```bash
# 方式一：一键启动（推荐）
python manage.py ui-streamlit --trade-date 20250226 --port 8501 --host localhost

# 方式二：手动启动（等价）
streamlit run ui/streamlit_app.py -- --config config.yml --trade-date 20250226
```
- 在浏览器内交互式过滤、排序和查看全量数据；依赖 `streamlit`（已在 `requirements.txt` 中）。
- 数据来源：
  - 持仓：`data/trading.db`（SQLite，表 `positions`）
  - 待下单：`data/pending_orders/{YYYYMMDD}.json`
  - 成交：`data/trades/{YYYYMMDD}.csv`
  - 配置：`config.yml`（通过 `--config` 传入，默认项目根目录）
- 界面语言：中文（标题、指标、提示均为中文）。

## 其他常用命令
- `python manage.py validate-config`：检查配置摘录。
- `python manage.py load-stocks`：查看股票池加载结果。
- `python manage.py fetch-history 600000.SH`：单只股票手动下载行情。
- `python manage.py list-positions`：打印持仓状态表。
- `python manage.py build-pending`：在已有行情 CSV 基础上单独生成待下单 JSON。

## stocks.xlsx 规范
- 支持任意列名；优先寻找包含 `code`（大小写不敏感）的列作为证券代码列，否则取第一列。
- 证券代码格式：`000001.SZ`、`600000.SH`、`430047.BJ`（无效代码会记录到 `data/invalid_codes.log`）。

## 目录结构
```
data/
├── stocks/            # 行情 CSV
├── pending_orders/    # 夜间任务 JSON
├── trades/            # 对账 CSV
├── reports/           # Markdown 报告
│   └── dashboard_YYYYMMDD.html  # 可视化仪表盘
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
- 交易接口（tlogon/torder/tquery）通常仅在 Windows/WFT 客户端环境可用；macOS 的 Wind API.app 多数情况下不包含交易接口，执行 `run-orders` 时会提示不支持。
- 请妥善保管 `config.yml` 和日志中的敏感信息；部署时可结合 SSH/密钥管理。

### 关于 CHO/MACHO 指标
- Wind 端 WSD 不提供 `CHO/MACHO` 字段；直接请求会返回 `-40522007`。本项目改为在本地根据 OHLCV（优先使用 `VWAP`，否则 `CLOSE`）计算：
  - `MID := 累加(VOLUME * (2*P - HIGH - LOW) / (HIGH + LOW))`
  - `CHO := SMA(MID, short) - SMA(MID, long)`；`MACHO := SMA(CHO, n)`
- 相关窗口参数在 `config.yml` 的 `strategy` 段配置。

欢迎根据 `task.md` 继续扩展多账户、监控、自动调度等特性。***
