import pandas as pd

from wind_trader.signals import SignalEngine
from wind_trader.storage import Position


def make_history(cho_values):
    rows = []
    for idx, value in enumerate(cho_values, start=1):
        rows.append(
            {
                "date": f"2024-01-{idx:02d}",
                "CHO": value,
                "CLOSE": 10 + idx,
            }
        )
    return pd.DataFrame(rows)


def test_signal_engine_buy_signal_when_cho_rises():
    engine = SignalEngine()
    history = make_history([1, 2])
    signals, updated_pos = engine.evaluate("600000.SH", history, None)
    assert len(signals) == 1
    assert signals[0].side == "Buy"
    assert updated_pos.status == 0  # status change handled elsewhere


def test_signal_engine_sell_signal_after_pending():
    engine = SignalEngine()
    pos = Position(code="600000.SH", status=1, pending_sell_since="2024-01-01")
    history = make_history([2, 1])
    signals, updated_pos = engine.evaluate("600000.SH", history, pos)
    assert len(signals) == 1
    assert signals[0].side == "Sell"
    assert updated_pos.pending_sell_since is None
