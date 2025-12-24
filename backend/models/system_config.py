"""
系统配置表（键值对）
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint

from backend.core.database import Base


class SystemConfig(Base):
    """简单的 key/value 配置存储"""
    __tablename__ = "system_configs"
    __table_args__ = (UniqueConstraint("key", name="uq_system_config_key"),)

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, index=True)
    value = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SystemConfig {self.key}={self.value}>"
