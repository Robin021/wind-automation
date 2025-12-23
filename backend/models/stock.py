"""
股票模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float

from backend.core.database import Base


class Stock(Base):
    """股票池表"""
    __tablename__ = "stocks"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 股票基本信息
    code = Column(String(20), unique=True, index=True, nullable=False)  # 如 600000.SH
    name = Column(String(50), nullable=False)
    market = Column(String(10))  # SH, SZ, BJ
    
    # 分类标签
    industry = Column(String(50))  # 行业
    is_st = Column(Boolean, default=False)  # 是否 ST
    is_kcb = Column(Boolean, default=False)  # 是否科创板
    is_cyb = Column(Boolean, default=False)  # 是否创业板
    
    # 状态
    is_active = Column(Boolean, default=True)  # 是否在池中
    
    # 最新行情（缓存）
    last_price = Column(Float)
    last_update = Column(DateTime)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Stock {self.code} {self.name}>"

