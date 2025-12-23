"""
支付订单（微信支付等）
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from backend.core.database import Base


class PaymentOrder(Base):
    """支付订单表"""

    __tablename__ = "payment_orders"

    id = Column(Integer, primary_key=True, index=True)

    provider = Column(String(20), nullable=False, default="wechat")  # wechat/alipay/stripe...
    channel = Column(String(20), nullable=False, default="native")  # native/h5/jsapi_mp/jsapi_mini

    out_trade_no = Column(String(64), unique=True, nullable=False, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    vip_level = Column(Integer, nullable=False)
    duration_months = Column(Integer, nullable=False, default=3)
    amount_fen = Column(Integer, nullable=False)

    status = Column(String(20), nullable=False, default="pending")  # pending/paid/failed/closed/refund
    is_test = Column(Boolean, default=False, nullable=False)

    paid_at = Column(DateTime, nullable=True)
    note = Column(String(255), nullable=True)

    raw_notify = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<PaymentOrder out_trade_no={self.out_trade_no} status={self.status} amount_fen={self.amount_fen}>"






