"""
股票分配 API
"""
from typing import Annotated, List, Optional
from datetime import date
import random

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.core.database import get_db
from backend.core.config import settings
from backend.models.stock import Stock
from backend.models.user import User
from backend.models.allocation import Allocation
from backend.models.signal import Signal
from backend.models.vip_config import VipConfig
from backend.api.v1.auth import get_current_admin, get_current_user

router = APIRouter()


# ============ Schemas ============

class AllocationResponse(BaseModel):
    id: int
    user_id: int
    stock_id: int
    batch_date: date
    vip_level_at_allocation: int
    status: str
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    signal: Optional[str] = None
    signal_price: Optional[float] = None
    signal_time: Optional[str] = None
    
    class Config:
        from_attributes = True


class AllocationList(BaseModel):
    total: int
    items: List[AllocationResponse]


class AllocationResult(BaseModel):
    user_id: int
    username: str
    vip_level: int
    stock_limit: int
    allocated_count: int
    stocks: List[dict]


# ============ Helper Functions ============

def get_vip_stock_limit(db: Session, vip_level: int) -> int:
    """获取 VIP 等级对应的股票数量限制"""
    config = db.query(VipConfig).filter(VipConfig.level == vip_level).first()
    if config:
        return config.stock_limit
    # 使用默认配置
    default = settings.DEFAULT_VIP_LEVELS.get(vip_level, {})
    return default.get("stock_limit", 5)


def _cleanup_invalid_allocations(db: Session, user_id: Optional[int] = None) -> int:
    """删除指向已删除/停用股票的分配记录，避免占位."""
    query = (
        db.query(Allocation)
        .outerjoin(Stock, Allocation.stock_id == Stock.id)
        .filter(or_(Stock.id == None, Stock.is_active == False))
    )
    if user_id:
        query = query.filter(Allocation.user_id == user_id)
    removed = query.delete(synchronize_session=False)
    if removed:
        db.commit()
    return removed


# ============ Routes ============

@router.get("/my", response_model=AllocationList)
async def get_my_allocations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    batch_date: Optional[date] = None,
    status: Optional[str] = "active",
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    """获取当前用户的股票分配"""
    _cleanup_invalid_allocations(db, user_id=current_user.id)

    query = db.query(Allocation).filter(Allocation.user_id == current_user.id)
    
    if batch_date:
        query = query.filter(Allocation.batch_date == batch_date)
    if status:
        query = query.filter(Allocation.status == status)
    
    total = query.count()
    allocations = query.offset(skip).limit(limit).all()
    
    # 附加股票信息
    items = []
    for alloc in allocations:
        stock = db.query(Stock).filter(Stock.id == alloc.stock_id).first()
        item = AllocationResponse.model_validate(alloc)
        if stock:
            item.stock_code = stock.code
            item.stock_name = stock.name
            sig = (
                db.query(Signal)
                .filter(Signal.code == stock.code)
                .order_by(Signal.trade_date.desc(), Signal.generated_at.desc())
                .first()
            )
            if sig:
                item.signal = sig.signal
                item.signal_price = sig.price
                item.signal_time = sig.generated_at.isoformat()
        items.append(item)
    
    return {"total": total, "items": items}


@router.get("", response_model=AllocationList)
async def list_allocations(
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
    user_id: Optional[int] = None,
    batch_date: Optional[date] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """获取分配列表（管理员）"""
    _cleanup_invalid_allocations(db)
    query = db.query(Allocation)
    
    if user_id:
        query = query.filter(Allocation.user_id == user_id)
    if batch_date:
        query = query.filter(Allocation.batch_date == batch_date)
    
    total = query.count()
    allocations = query.offset(skip).limit(limit).all()
    
    # 附加股票信息
    items = []
    for alloc in allocations:
        stock = db.query(Stock).filter(Stock.id == alloc.stock_id).first()
        item = AllocationResponse.model_validate(alloc)
        if stock:
            item.stock_code = stock.code
            item.stock_name = stock.name
            sig = (
                db.query(Signal)
                .filter(Signal.code == stock.code)
                .order_by(Signal.trade_date.desc(), Signal.generated_at.desc())
                .first()
            )
            if sig:
                item.signal = sig.signal
                item.signal_price = sig.price
                item.signal_time = sig.generated_at.isoformat()
        items.append(item)
    
    return {"total": total, "items": items}


@router.post("/allocate")
async def allocate_stocks(
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
    user_ids: Optional[List[int]] = Query(None, description="指定用户ID列表，为空则分配给所有活跃用户"),
    batch_date: date = Query(default_factory=date.today),
):
    """执行股票分配（管理员）"""
    # 获取要分配的用户
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids), User.is_active == True).all()
    else:
        users = db.query(User).filter(User.is_active == True).all()
    
    if not users:
        raise HTTPException(status_code=400, detail="没有可分配的用户")
    
    # 获取活跃的股票池
    active_stocks = db.query(Stock).filter(Stock.is_active == True).all()
    if not active_stocks:
        raise HTTPException(status_code=400, detail="股票池为空")
    
    results = []
    
    for user in users:
        # 获取该用户的股票限额
        stock_limit = get_vip_stock_limit(db, user.vip_level)
        
        # 清除该用户当天的旧分配
        db.query(Allocation).filter(
            Allocation.user_id == user.id,
            Allocation.batch_date == batch_date
        ).delete()
        
        # 确定分配数量
        if stock_limit == -1:  # 不限
            alloc_count = len(active_stocks)
            selected_stocks = active_stocks
        else:
            alloc_count = min(stock_limit, len(active_stocks))
            selected_stocks = random.sample(active_stocks, alloc_count)
        
        # 创建分配记录
        user_stocks = []
        for stock in selected_stocks:
            allocation = Allocation(
                user_id=user.id,
                stock_id=stock.id,
                batch_date=batch_date,
                vip_level_at_allocation=user.vip_level,
                status="active",
            )
            db.add(allocation)
            user_stocks.append({"code": stock.code, "name": stock.name})
        
        results.append(AllocationResult(
            user_id=user.id,
            username=user.username,
            vip_level=user.vip_level,
            stock_limit=stock_limit,
            allocated_count=alloc_count,
            stocks=user_stocks,
        ))
    
    db.commit()
    
    return {
        "message": f"分配完成：{len(results)} 个用户",
        "batch_date": str(batch_date),
        "results": [r.model_dump() for r in results],
    }


@router.delete("/clear")
async def clear_allocations(
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
    batch_date: Optional[date] = None,
    user_id: Optional[int] = None,
):
    """清除分配记录（管理员）"""
    query = db.query(Allocation)
    
    if batch_date:
        query = query.filter(Allocation.batch_date == batch_date)
    if user_id:
        query = query.filter(Allocation.user_id == user_id)
    
    count = query.count()
    query.delete()
    db.commit()
    
    return {"message": f"已清除 {count} 条分配记录"}
