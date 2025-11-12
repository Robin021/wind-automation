from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

import pandas as pd

from .storage import Position
from .models import Signal


class SignalEngine:
    """Generate trading signals based on CHO indicator."""

    def __init__(self):
        pass

    def evaluate(self, code: str, history: pd.DataFrame, position: Position | None) -> Tuple[List[Signal], Position]:
        history = history.sort_values("date")
        if len(history) < 2:
            return [], position or Position(code=code, status=0, update_time=datetime.utcnow().isoformat())

        pos = position or Position(code=code, status=0, update_time=datetime.utcnow().isoformat())
        signals: List[Signal] = []
        latest = history.iloc[-1]
        prev = history.iloc[-2]

        cho_latest = float(latest["CHO"])
        cho_prev = float(prev["CHO"])
        signal_time = str(latest["date"])

        close_price = float(latest["CLOSE"])
        security_name = str(latest.get("SEC_NAME", "")) if "SEC_NAME" in latest else None

        if pos.status == 0 and cho_latest > cho_prev:
            signals.append(Signal(code=code, side="Buy", signal_time=signal_time))
            pos.last_signal_time = signal_time
        elif pos.status == 1:
            if pos.pending_sell_since:
                if cho_latest < cho_prev:
                    signals.append(Signal(code=code, side="Sell", signal_time=signal_time))
                    pos.pending_sell_since = None
                    pos.last_signal_time = signal_time
                else:
                    pos.pending_sell_since = None
            else:
                if cho_latest < cho_prev:
                    pos.pending_sell_since = signal_time

        pos.update_time = datetime.utcnow().isoformat()
        for sig in signals:
            sig.reference_price = close_price
            sig.price_hint = close_price
            sig.security_name = security_name

        return signals, pos
