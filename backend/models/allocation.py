"""
股票分配记录模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship

from backend.core.database import Base


class Allocation(Base):
    """用户股票分配记录表"""
    __tablename__ = "allocations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    
    # 分配批次（用于区分不同时间的分配）
    batch_date = Column(Date, nullable=False, index=True)
    
    # 分配时的 VIP 等级（记录历史）
    vip_level_at_allocation = Column(Integer, nullable=False)
    
    # 状态
    status = Column(String(20), default="active")  # active, expired, cancelled
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Allocation user={self.user_id} stock={self.stock_id}>"

