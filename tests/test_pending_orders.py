from pathlib import Path

from wind_trader.models import Signal
from wind_trader.pending_orders import PendingOrderBuilder


def test_pending_order_builder(tmp_path):
    builder = PendingOrderBuilder(tmp_path)
    signals = [
        Signal(code="600000.SH", side="Buy", signal_time="2024-01-01", reference_price=10.0),
        Signal(code="300750.SZ", side="Sell", signal_time="2024-01-01", reference_price=20.0),
    ]
    output = builder.build(signals, "20240102", volume_per_trade=100)
    assert output.exists()
    data = output.read_text(encoding="utf-8")
    assert "600000.SH" in data
    assert "300750.SZ" in data
