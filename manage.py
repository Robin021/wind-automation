#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from wind_trader.config import AppConfig, ConfigManager
from wind_trader.logging_utils import setup_logging
from wind_trader.paths import ensure_directories
from wind_trader.stock_pool import StockPoolLoader
from wind_trader.storage import PositionStore
from wind_trader.wind_client import WindClient, WindClientError
from wind_trader.data_fetcher import DataFetcher
from wind_trader.signals import SignalEngine
from wind_trader.pending_orders import PendingOrderBuilder
from wind_trader.order_executor import OrderExecutor
from wind_trader.reconciler import TradeReconciler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Wind 夜间委托自动化系统管理脚本",
    )
    parser.add_argument(
        "--config",
        default="config.yml",
        help="配置文件路径（默认：config.yml）",
    )
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="创建数据、日志等目录，并初始化数据库")
    init_parser.add_argument(
        "--stocks-file",
        default="stocks.xlsx",
        help="股票池文件路径（仅用于校验存在性）",
    )

    subparsers.add_parser("validate-config", help="校验配置文件并输出摘要")

    load_parser = subparsers.add_parser("load-stocks", help="读取股票池并输出数量")
    load_parser.add_argument(
        "--stocks-file",
        default="stocks.xlsx",
        help="股票池 Excel 文件路径",
    )

    subparsers.add_parser("list-positions", help="查看 positions 数据表中的内容")

    fetch_parser = subparsers.add_parser("fetch-history", help="调用 WindPy 下载单只股票行情")
    fetch_parser.add_argument("code", help="股票代码，例如 600000.SH")
    fetch_parser.add_argument("--days", type=int, default=None, help="向前回溯天数（默认由配置决定）")
    fetch_parser.add_argument("--end-date", help="结束日期 YYYY-MM-DD（默认今天）")

    build_parser = subparsers.add_parser("build-pending", help="根据信号生成待下单任务 JSON")
    build_parser.add_argument(
        "--stocks-file",
        default="stocks.xlsx",
        help="股票池 Excel 文件路径",
    )
    build_parser.add_argument(
        "--trade-date",
        help="交易日期 YYYYMMDD（默认今日）",
    )

    run_parser = subparsers.add_parser("run-orders", help="夜间执行待下单任务")
    run_parser.add_argument(
        "--trade-date",
        help="交易日期 YYYYMMDD，对应 data/pending_orders/{date}.json",
    )
    run_parser.add_argument(
        "--file",
        help="待下单文件路径（若指定则优先生效）",
    )

    reconcile_parser = subparsers.add_parser("reconcile", help="次日核对委托与成交")
    reconcile_parser.add_argument(
        "--pending-file",
        help="夜间生成的待下单文件路径（默认根据 trade-date 自动定位）",
    )
    reconcile_parser.add_argument(
        "--trade-date",
        help="交易日期 YYYYMMDD（默认今天）",
    )

    eod_parser = subparsers.add_parser("run-eod", help="收盘后自动化流程：拉数据→算信号→生成待下单")
    eod_parser.add_argument(
        "--stocks-file",
        default="stocks.xlsx",
        help="股票池 Excel 文件路径",
    )
    eod_parser.add_argument(
        "--trade-date",
        help="交易日期 YYYYMMDD（默认今天）",
    )

    dash_parser = subparsers.add_parser("dashboard", help="汇总查看：持仓/待下单/成交 概览，并导出 HTML")
    dash_parser.add_argument(
        "--trade-date",
        help="交易日期 YYYYMMDD（默认今天）",
    )

    tui_parser = subparsers.add_parser("tui", help="终端 TUI：彩色表格查看持仓/待下单/成交")
    tui_parser.add_argument(
        "--trade-date",
        help="交易日期 YYYYMMDD（默认今天）",
    )
    tui_parser.add_argument(
        "--filter",
        help="按代码过滤（子串匹配）",
        default=None,
    )
    tui_parser.add_argument(
        "--rows",
        type=int,
        default=30,
        help="每张表最多显示的行数（默认 30）",
    )

    ui_parser = subparsers.add_parser("ui-streamlit", help="一键启动 Streamlit Web 面板")
    ui_parser.add_argument(
        "--trade-date",
        help="交易日期 YYYYMMDD（默认今天）",
    )
    ui_parser.add_argument(
        "--port",
        type=int,
        default=8501,
        help="端口（默认 8501）",
    )
    ui_parser.add_argument(
        "--host",
        default="localhost",
        help="监听地址（默认 localhost）",
    )


    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    try:
        config = ConfigManager(args.config).get()
    except Exception as exc:
        print(f"加载配置失败：{exc}", file=sys.stderr)
        return 1

    if args.command == "init":
        return handle_init(config, Path(args.stocks_file))

    ensure_directories(config.paths)
    setup_logging(config)

    if args.command == "validate-config":
        return handle_validate(config)
    if args.command == "load-stocks":
        return handle_load_stocks(config, Path(args.stocks_file))
    if args.command == "list-positions":
        return handle_list_positions(config)
    if args.command == "fetch-history":
        return handle_fetch_history(config, args.code, days=args.days, end_date=args.end_date)
    if args.command == "build-pending":
        return handle_build_pending(config, Path(args.stocks_file), args.trade_date)
    if args.command == "run-orders":
        return handle_run_orders(config, trade_date=args.trade_date, file_path=args.file)
    if args.command == "reconcile":
        return handle_reconcile(config, pending_file=args.pending_file, trade_date=args.trade_date)
    if args.command == "run-eod":
        return handle_run_eod(config, Path(args.stocks_file), args.trade_date)
    if args.command == "dashboard":
        return handle_dashboard(config, args.trade_date)
    if args.command == "tui":
        return handle_tui(config, args.trade_date, args.filter, args.rows)
    if args.command == "ui-streamlit":
        return handle_ui_streamlit(config, args.trade_date, args.port, args.host, args.config)

    parser.print_help()
    return 1


def handle_init(config: AppConfig, stocks_file: Path) -> int:
    ensure_directories(config.paths)
    db_path = config.paths.data_root / "trading.db"
    store = PositionStore(db_path)
    store.close()
    invalid_log = config.paths.data_root / "invalid_codes.log"
    invalid_log.touch(exist_ok=True)
    stocks_msg = (
        "存在" if stocks_file.exists() else "不存在"
    )
    print("初始化完成：")
    print(f" - 数据目录：{config.paths.data_root}")
    print(f" - 日志文件：{config.paths.log_file}")
    print(f" - 持仓数据库：{db_path}")
    print(f" - 股票池文件（{stocks_msg}）：{stocks_file}")
    return 0


def handle_validate(config: AppConfig) -> int:
    print("配置文件校验通过：")
    print(f" - 数据目录：{config.paths.data_root}")
    print(f" - 日志文件：{config.paths.log_file}")
    print(f" - Wind 账户：{config.wind.logon_account}")
    print(f" - 策略窗口：short={config.strategy.short}, long={config.strategy.long}, n={config.strategy.n}")
    return 0


def handle_load_stocks(config: AppConfig, stocks_file: Path) -> int:
    logger = logging.getLogger("StockPoolLoaderCLI")
    loader = StockPoolLoader(
        excel_path=stocks_file,
        invalid_log_path=config.paths.data_root / "invalid_codes.log",
        logger=logger,
    )
    try:
        codes = loader.load()
    except Exception as exc:
        logger.error("加载股票池失败：%s", exc)
        return 1
    logger.info("股票池样本：%s", codes[:5])
    print(f"共加载 {len(codes)} 条股票代码。")
    return 0


def handle_list_positions(config: AppConfig) -> int:
    store = PositionStore(config.paths.data_root / "trading.db")
    positions = store.list_all()
    if not positions:
        print("positions 表为空。")
        return 0
    for pos in positions:
        print(
            f"{pos.code} | status={pos.status} | "
            f"hold={pos.hold_volume} | pending={pos.pending_sell_since} | updated={pos.update_time}"
        )
    print(f"共 {len(positions)} 条记录。")
    return 0


def handle_fetch_history(config: AppConfig, code: str, days: int | None, end_date: str | None) -> int:
    client = WindClient()
    fetcher = DataFetcher(client=client, strategy=config.strategy)
    try:
        with client.session():
            df = fetcher.fetch_history(code, days=days, end_date=end_date)
    except WindClientError as exc:
        print(f"WindPy 访问失败：{exc}")
        return 1
    output_path = config.paths.stocks_dir / f"{code}.csv"
    fetcher.save_history(df, output_path)
    print(f"成功保存 {code} 历史数据到 {output_path}")
    return 0


def handle_build_pending(config: AppConfig, stocks_file: Path, trade_date: str | None) -> int:
    trade_date = trade_date or datetime.today().strftime("%Y%m%d")
    loader = StockPoolLoader(
        excel_path=stocks_file,
        invalid_log_path=config.paths.data_root / "invalid_codes.log",
        logger=logging.getLogger("StockPoolLoaderCLI"),
    )
    codes = loader.load()
    if not codes:
        print("股票池为空，无法生成待下单任务。")
        return 1

    store = PositionStore(config.paths.data_root / "trading.db")
    engine = SignalEngine()
    signals = []
    skipped = []
    for code in codes:
        csv_path = config.paths.stocks_dir / f"{code}.csv"
        if not csv_path.exists():
            skipped.append(code)
            continue
        df = pd.read_csv(csv_path)
        try:
            new_signals, updated_pos = engine.evaluate(code, df, store.get(code))
        except Exception as exc:
            logging.getLogger("SignalEngine").error("解析 %s 失败：%s", code, exc)
            continue
        store.upsert(updated_pos)
        signals.extend(new_signals)

    builder = PendingOrderBuilder(config.paths.pending_orders_dir)
    output_path = builder.build(signals, trade_date, config.orders.volume_per_trade)
    print(f"生成待下单任务 {output_path}，共 {len(signals)} 条信号，缺少数据 {len(skipped)} 条。")
    if skipped:
        print("缺少行情文件的代码：", ", ".join(skipped[:5]), "..." if len(skipped) > 5 else "")
    return 0


def handle_run_orders(config: AppConfig, trade_date: str | None, file_path: str | None) -> int:
    if file_path:
        pending_path = Path(file_path)
    else:
        trade_date = trade_date or datetime.today().strftime("%Y%m%d")
        pending_path = config.paths.pending_orders_dir / f"{trade_date}.json"
    if not pending_path.exists():
        print(f"待下单文件不存在：{pending_path}")
        return 1
    executor = OrderExecutor(config, WindClient())
    try:
        count = executor.execute(pending_path)
    except WindClientError as exc:
        print(f"执行下单失败：{exc}")
        return 1
    print(f"执行完成，共提交 {count} 笔订单。结果写回 {pending_path}")
    return 0


def handle_reconcile(config: AppConfig, pending_file: str | None, trade_date: str | None) -> int:
    if pending_file:
        path = Path(pending_file)
    else:
        trade_date = trade_date or datetime.today().strftime("%Y%m%d")
        path = config.paths.pending_orders_dir / f"{trade_date}.json"
    if not path.exists():
        print(f"找不到待下单文件：{path}")
        return 1
    reconciler = TradeReconciler(config, WindClient())
    report_path = reconciler.reconcile(path, trade_date=trade_date)
    print(f"核对完成，结果写入 {report_path}")
    return 0


def handle_run_eod(config: AppConfig, stocks_file: Path, trade_date: str | None) -> int:
    trade_date = trade_date or datetime.today().strftime("%Y%m%d")
    loader = StockPoolLoader(
        excel_path=stocks_file,
        invalid_log_path=config.paths.data_root / "invalid_codes.log",
        logger=logging.getLogger("StockPoolLoaderCLI"),
    )
    codes = loader.load()
    if not codes:
        print("股票池为空，无法继续。")
        return 1
    store = PositionStore(config.paths.data_root / "trading.db")
    engine = SignalEngine()
    builder = PendingOrderBuilder(config.paths.pending_orders_dir)
    client = WindClient()
    fetcher = DataFetcher(client=client, strategy=config.strategy)
    signals = []
    failed_fetch = []
    with client.session():
        for code in codes:
            try:
                df = fetcher.fetch_history(code)
                fetcher.save_history(df, config.paths.stocks_dir / f"{code}.csv")
            except Exception as exc:
                logging.getLogger("DataFetcher").error("下载 %s 失败：%s", code, exc)
                failed_fetch.append(code)
                continue
            pos = store.get(code)
            new_signals, updated_pos = engine.evaluate(code, df, pos)
            store.upsert(updated_pos)
            signals.extend(new_signals)
    pending_path = builder.build(signals, trade_date, config.orders.volume_per_trade)
    print(
        f"EOD 完成：成功下载 {len(codes) - len(failed_fetch)} / {len(codes)}，"
        f"生成 {len(signals)} 条信号，待下单文件 {pending_path}"
    )
    if failed_fetch:
        print("下载失败的代码：", ", ".join(failed_fetch[:5]), "..." if len(failed_fetch) > 5 else "")
    return 0


def handle_dashboard(config: AppConfig, trade_date: str | None) -> int:
    from wind_trader.dashboard import Dashboard
    trade_date = trade_date or datetime.today().strftime("%Y%m%d")
    dash = Dashboard(config)
    summary, html_path = dash.build_console_summary(trade_date)
    print(summary)
    return 0


def handle_tui(
    config: AppConfig,
    trade_date: str | None,
    filter_text: str | None,
    rows: int,
) -> int:
    from wind_trader.tui import render_tui
    trade_date = trade_date or datetime.today().strftime("%Y%m%d")
    render_tui(config, trade_date, filter_text=filter_text, max_rows=rows)
    return 0


def handle_ui_streamlit(
    config: AppConfig,
    trade_date: str | None,
    port: int,
    host: str,
    config_path: str,
) -> int:
    """Launch Streamlit app with given parameters."""
    td = trade_date or datetime.today().strftime("%Y%m%d")
    streamlit_script = Path(__file__).parent / "ui" / "streamlit_app.py"
    if not streamlit_script.exists():
        print(f"找不到 Streamlit 脚本：{streamlit_script}")
        return 1
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(streamlit_script),
        f"--server.port={port}",
        f"--server.address={host}",
        "--",
        "--config",
        str(config_path),
        "--trade-date",
        td,
    ]
    print("启动 Streamlit:", " ".join(cmd))
    try:
        return subprocess.run(cmd).returncode
    except FileNotFoundError:
        print("未安装 streamlit，请先执行：pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
