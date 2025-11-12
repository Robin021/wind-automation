from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from .config import AppConfig
from .models import PendingOrder
from .wind_client import WindClient, WindClientError
from .retry import retry_call

logger = logging.getLogger("OrderExecutor")


TRADE_SIDE_MAP = {
    "BUY": "Buy",
    "SELL": "Sell",
}


class OrderExecutor:
    """Submit pending orders through Wind trading interface."""

    def __init__(self, config: AppConfig, client: WindClient):
        self.config = config
        self.client = client

    def load_pending(self, path: Path) -> List[PendingOrder]:
        with Path(path).open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [PendingOrder(**item) for item in data]

    def save_pending(self, orders: List[PendingOrder], path: Path) -> None:
        with Path(path).open("w", encoding="utf-8") as fh:
            json.dump([order.to_dict() for order in orders], fh, ensure_ascii=False, indent=2)

    def execute(self, pending_path: Path) -> int:
        orders = self.load_pending(pending_path)
        if not orders:
            logger.info("No pending orders to execute.")
            return 0

        with self.client.session():
            logon = self.client.tlogon(
                self.config.wind.broker_id,
                self.config.wind.department_id,
                self.config.wind.logon_account,
                self.config.wind.password,
                self.config.wind.account_type,
            )
            logon_id = logon.Data[0][0]
            logger.info("Login successful, LogonID=%s", logon_id)

            for order in orders:
                try:
                    response = retry_call(
                        lambda: self.client.torder(
                            order.code,
                            order.side,
                            order.limit_price,
                            order.volume,
                            f"OrderType=LMT;LogonID={logon_id}",
                        ),
                        attempts=self.config.orders.retry.attempts,
                        delays=self.config.orders.retry.backoff_seconds,
                        exceptions=(WindClientError, RuntimeError),
                        logger=logger,
                        operation=f"torder {order.code}",
                    )
                    req_id = getattr(response, "Data", [[None]])[0][0] if hasattr(response, "Data") else None
                    order.request_id = req_id
                    order.status = "Submitted"
                    logger.info(
                        "Submitted %s %s @ %s, request_id=%s",
                        order.side,
                        order.code,
                        order.limit_price,
                        req_id,
                    )
                except WindClientError as exc:
                    order.status = "Failed"
                    order.notes = str(exc)
                    logger.error("Order for %s failed: %s", order.code, exc)

        self.save_pending(orders, pending_path)
        return len(orders)
