"""
VIP 价格配置（订阅定价）
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer

from backend.core.database import Base


class VipPriceConfig(Base):
    """VIP 价格配置表（管理员可调）"""

    __tablename__ = "vip_price_configs"

    id = Column(Integer, primary_key=True, index=True)

    # VIP 等级 (0-4)，一般只启用 1-4
    vip_level = Column(Integer, unique=True, nullable=False, index=True)

    # 订阅周期（月），当前产品固定 3 个月，但留个字段方便未来扩展
    duration_months = Column(Integer, default=3, nullable=False)

    # 价格（分）
    price_fen = Column(Integer, nullable=False)

    enabled = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<VipPriceConfig vip={self.vip_level} months={self.duration_months} "
            f"price_fen={self.price_fen} enabled={self.enabled}>"
        )






