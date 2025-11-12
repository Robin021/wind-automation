from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List

from .config import AppConfig
from .models import PendingOrder
from .storage import PositionStore, Position
from .wind_client import WindClient

logger = logging.getLogger("TradeReconciler")


class TradeReconciler:
    """Reconcile orders/trades via Wind tquery."""

    def __init__(self, config: AppConfig, client: WindClient):
        self.config = config
        self.client = client
        self.store = PositionStore(config.paths.data_root / "trading.db")

    def reconcile(self, pending_file: Path, trade_date: str | None = None) -> Path:
        trade_date = trade_date or datetime.today().strftime("%Y%m%d")
        orders = self._load_pending(pending_file)
        if not orders:
            logger.info("No pending orders in %s", pending_file)
            return self._write_report([], trade_date)

        with self.client.session():
            logon = self.client.tlogon(
                self.config.wind.broker_id,
                self.config.wind.department_id,
                self.config.wind.logon_account,
                self.config.wind.password,
                self.config.wind.account_type,
            )
            logon_id = logon.Data[0][0]
            logger.info("Login successful for reconciliation, LogonID=%s", logon_id)

            trades = []
            trade_details = []
            for order in orders:
                if not order.request_id:
                    logger.warning("Order %s missing RequestID, skip reconciliation.", order.code)
                    continue
                result = self.client.tquery(
                    "Order",
                    f"LogonID={logon_id};RequestID={order.request_id}",
                )
                trade = self._parse_order_query(result, order)
                trades.append(trade)
                trade_info = self._query_trade(logon_id, order, trade)
                if trade_info:
                    trade_details.append(trade_info)
                self._update_position(order, trade)
            report_path = self._write_report(trades, trade_details, trade_date)

        self.store.close()
        return report_path

    def _load_pending(self, path: Path) -> List[PendingOrder]:
        with Path(path).open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [PendingOrder(**item) for item in data]

    def _parse_order_query(self, result, order: PendingOrder):
        error_code = getattr(result, "ErrorCode", None)
        if error_code and error_code != 0:
            return {
                "code": order.code,
                "side": order.side,
                "status": "QueryError",
                "error_code": error_code,
                "order_price": order.limit_price,
                "traded_volume": 0,
            }
        fields = getattr(result, "Fields", [])
        data = getattr(result, "Data", [])
        order_dict = {field: column[0] for field, column in zip(fields, data)}
        return {
            "code": order.code,
            "side": order.side,
            "status": order_dict.get("OrderStatus", "Unknown"),
            "order_price": order_dict.get("OrderPrice", order.limit_price),
            "traded_price": order_dict.get("TradedPrice", 0),
            "traded_volume": order_dict.get("TradedVolume", 0),
            "order_number": order_dict.get("OrderNumber"),
            "request_id": order.request_id,
        }

    def _query_trade(self, logon_id: str, order: PendingOrder, order_info: dict):
        try:
            result = self.client.tquery(
                "Trade",
                f"LogonID={logon_id};WindCode={order.code}",
            )
        except Exception as exc:
            logger.warning("Trade query failed for %s: %s", order.code, exc)
            return None
        fields = getattr(result, "Fields", [])
        data = getattr(result, "Data", [])
        if not fields or not data:
            return None
        trade_dict = {field: column[0] for field, column in zip(fields, data)}
        trade_dict.update({"code": order.code, "side": order.side, "request_id": order.request_id})
        return trade_dict

    def _update_position(self, order: PendingOrder, trade_info: dict) -> None:
        pos = self.store.get(order.code) or Position(code=order.code, status=0)
        if order.side.lower() == "buy" and trade_info.get("traded_volume", 0) > 0:
            pos.status = 1
            pos.hold_volume = trade_info["traded_volume"]
            pos.last_buy_price = trade_info.get("traded_price")
            pos.pending_sell_since = None
        elif order.side.lower() == "sell" and trade_info.get("traded_volume", 0) >= pos.hold_volume:
            pos.status = 0
            pos.hold_volume = 0
            pos.last_sell_price = trade_info.get("traded_price")
            pos.pending_sell_since = None
        pos.update_time = datetime.utcnow().isoformat()
        self.store.upsert(pos)

    def _write_report(self, trades: List[dict], trade_details: List[dict], trade_date: str) -> Path:
        trades_dir = self.config.paths.trades_dir
        trades_dir.mkdir(parents=True, exist_ok=True)
        csv_path = trades_dir / f"{trade_date}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "code",
                    "side",
                    "status",
                    "order_price",
                    "traded_price",
                    "traded_volume",
                    "order_number",
                    "request_id",
                ],
            )
            writer.writeheader()
            for trade in trades:
                writer.writerow(trade)
        logger.info("Wrote trade report to %s", csv_path)
        md_path = self.config.paths.reports_dir / f"{trade_date}_reconcile.md"
        self.config.paths.reports_dir.mkdir(parents=True, exist_ok=True)
        success = sum(1 for t in trades if t["status"].lower().startswith("success"))
        failures = sum(1 for t in trades if t["status"].lower().startswith("queryerror"))
        with md_path.open("w", encoding="utf-8") as fh:
            fh.write(f"# Reconcile Report {trade_date}\n\n")
            fh.write(f"- Total orders: {len(trades)}\n")
            fh.write(f"- Success: {success}\n")
            fh.write(f"- Failures: {failures}\n")
            fh.write(f"- Trades fetched: {len(trade_details)}\n\n")
            fh.write("## Trades\n")
            for trade in trade_details:
                fh.write(f"- {trade.get('code')} side={trade.get('side')} volume={trade.get('TradedVolume')} price={trade.get('TradedPrice')}\n")
        logger.info("Wrote reconcile report to %s", md_path)
        return md_path
