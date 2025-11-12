from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class Signal:
    code: str
    side: str  # "Buy" or "Sell"
    signal_time: str
    price_hint: Optional[float] = None
    reference_price: Optional[float] = None
    security_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PendingOrder:
    code: str
    side: str
    volume: int
    limit_price: float
    signal_time: str
    trade_date: str
    request_id: Optional[str] = None
    status: str = "Pending"
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
