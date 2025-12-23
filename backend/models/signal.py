"""
交易日信号表
"""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Date, DateTime, Float, UniqueConstraint

from backend.core.database import Base


class Signal(Base):
    """每个交易日、每只股票的最新信号"""

    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint("trade_date", "code", name="uq_signal_trade_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    code = Column(String(20), nullable=False, index=True)
    name = Column(String(50))
    signal = Column(String(20), nullable=False)  # Buy / Sell / Hold
    price = Column(Float)
    note = Column(String(200))
    generated_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<Signal {self.trade_date} {self.code} {self.signal}>"

