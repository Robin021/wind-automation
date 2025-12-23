"""
用户订阅权益（VIP有效期）
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer

from backend.core.database import Base


class UserSubscription(Base):
    """用户订阅表（每个用户一条有效订阅记录）"""

    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)

    vip_level = Column(Integer, nullable=False, default=0)

    starts_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<UserSubscription user_id={self.user_id} vip={self.vip_level} expires_at={self.expires_at}>"






