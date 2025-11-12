from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence

from .models import PendingOrder, Signal
from .pricing import (
    calc_limit_price,
    infer_limit_pct,
    infer_tick_size,
)

logger = logging.getLogger("PendingOrderBuilder")


class PendingOrderBuilder:
    """Convert signals into pending order JSON files."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build(
        self,
        signals: Sequence[Signal],
        trade_date: str,
        volume_per_trade: int,
    ) -> Path:
        orders: List[PendingOrder] = []
        for signal in signals:
            if signal.reference_price is None:
                logger.warning("Signal %s lacks reference price, skip.", signal.code)
                continue
            pct = infer_limit_pct(signal.code, signal.security_name)
            tick = infer_tick_size(signal.code)
            limit_price = calc_limit_price(
                reference_price=signal.reference_price,
                direction=signal.side,
                pct=pct,
                tick_size=tick,
            )
            order = PendingOrder(
                code=signal.code,
                side=signal.side,
                volume=volume_per_trade,
                limit_price=limit_price,
                signal_time=signal.signal_time,
                trade_date=trade_date,
            )
            orders.append(order)

        path = self.output_dir / f"{trade_date}.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump([order.to_dict() for order in orders], fh, ensure_ascii=False, indent=2)
        logger.info("Generated %s pending orders at %s", len(orders), path)
        return path

    def list_files(self) -> List[Path]:
        return sorted(self.output_dir.glob("*.json"))

    def load(self, path: Path) -> List[PendingOrder]:
        with Path(path).open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [PendingOrder(**item) for item in data]
