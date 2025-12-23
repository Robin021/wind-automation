"""
VIP 等级配置模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime

from backend.core.database import Base


class VipConfig(Base):
    """VIP 等级配置表（后台可调）"""
    __tablename__ = "vip_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # VIP 等级 (0-4)
    level = Column(Integer, unique=True, nullable=False)
    
    # 等级名称
    name = Column(String(50), nullable=False)
    
    # 股票数量上限 (-1 表示不限)
    stock_limit = Column(Integer, nullable=False)
    
    # 等级描述
    description = Column(String(200))
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<VipConfig level={self.level} name={self.name} limit={self.stock_limit}>"

