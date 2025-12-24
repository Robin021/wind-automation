"""
股票分配 API
"""
from typing import Annotated, List, Optional, Literal
from datetime import date, datetime, timedelta
import random

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field

from backend.core.database import get_db
from backend.core.config import settings
from backend.models.stock import Stock
from backend.models.user import User
from backend.models.allocation import Allocation
from backend.models.signal import Signal
from backend.models.vip_config import VipConfig
from backend.api.v1.auth import get_current_admin, get_current_user
from backend.services.subscription_service import get_effective_vip_level
from backend.models.system_config import SystemConfig

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


class ManualAllocatePayload(BaseModel):
    """手工分配/随机抽取指定数量（适用于 VIP0 定制）"""
    user_id: int
    batch_date: date = Field(default_factory=date.today)
    mode: Literal["random_buy", "manual"] = "random_buy"
    count: int = Field(5, ge=1)
    stock_ids: Optional[List[int]] = None


# ============ Helper Functions ============

def _get_free_trial_days(db: Session) -> int:
    cfg = db.query(SystemConfig).filter(SystemConfig.key == "FREE_TRIAL_DAYS").first()
    if not cfg:
        return getattr(settings, "FREE_TRIAL_DAYS", 0)
    try:
        return max(0, int(cfg.value))
    except (TypeError, ValueError):
        return 0


def get_vip_stock_limit(db: Session, vip_level: int, user: Optional[User] = None) -> int:
    """
    获取 VIP 等级对应的股票数量限制
    - 若配置了 FREE_TRIAL_DAYS，则对 VIP0 的免费试用期过期后限制为 0
    """
    config = db.query(VipConfig).filter(VipConfig.level == vip_level).first()
    limit = config.stock_limit if config else settings.DEFAULT_VIP_LEVELS.get(vip_level, {}).get("stock_limit", 5)

    if (
        vip_level == 0
        and user is not None
        and user.created_at
    ):
        trial_days = _get_free_trial_days(db)
        if trial_days > 0:
            expire_at = user.created_at + timedelta(days=trial_days)
            if datetime.utcnow() >= expire_at:
                return 0
    # 使用默认配置
    return limit


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
    base_query = db.query(Allocation).filter(Allocation.user_id == current_user.id)

    # 默认只返回最新批次的“active”分配，避免累积历史批次导致数量叠加
    if status:
        base_query = base_query.filter(Allocation.status == status)

    if batch_date:
        query = base_query.filter(Allocation.batch_date == batch_date)
    else:
        latest_batch = (
            base_query.with_entities(Allocation.batch_date)
            .order_by(Allocation.batch_date.desc())
            .first()
        )
        if latest_batch:
            query = base_query.filter(Allocation.batch_date == latest_batch[0])
        else:
            query = base_query
    
    # 按当前有效 VIP 限制返回的数量，避免历史异常/重复分配导致数量超额
    effective_vip = get_effective_vip_level(db, current_user)
    stock_limit_cap = get_vip_stock_limit(db, effective_vip, current_user)
    max_allowed = None if stock_limit_cap == -1 else stock_limit_cap

    total_all = query.count()
    total = min(total_all, max_allowed) if max_allowed is not None else total_all

    data_query = query.order_by(Allocation.id.desc())
    if max_allowed is not None:
        if skip >= max_allowed:
            allocations = []
        else:
            page_limit = min(limit, max_allowed - skip)
            allocations = data_query.offset(skip).limit(page_limit).all()
    else:
        allocations = data_query.offset(skip).limit(limit).all()
    
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
        # 订阅到期则视为 VIP0（不依赖 users.vip_level 的历史值）
        effective_vip = get_effective_vip_level(db, user)
        # 获取该用户的股票限额
        stock_limit = get_vip_stock_limit(db, effective_vip, user)
        
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
                vip_level_at_allocation=effective_vip,
                status="active",
            )
            db.add(allocation)
            user_stocks.append({"code": stock.code, "name": stock.name})
        
        results.append(AllocationResult(
            user_id=user.id,
            username=user.username,
            vip_level=effective_vip,
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


@router.post("/manual-allocate")
async def manual_allocate(
    payload: ManualAllocatePayload,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """
    手工/定向分配（常用于 VIP0）：
    - mode=random_buy：从最新交易日的 Buy 信号中随机抽取 count 只
    - mode=manual：admin 提供 stock_ids 列表
    """
    user = db.query(User).filter(User.id == payload.user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在或已禁用")

    stock_limit = get_vip_stock_limit(db, get_effective_vip_level(db, user), user)
    if stock_limit != -1 and payload.count > stock_limit:
        raise HTTPException(status_code=400, detail=f"数量超出当前 VIP 限额（{stock_limit}）")

    # 先清理该日期的旧分配
    db.query(Allocation).filter(
        Allocation.user_id == user.id,
        Allocation.batch_date == payload.batch_date
    ).delete()

    if payload.mode == "manual":
        if not payload.stock_ids:
            raise HTTPException(status_code=400, detail="mode=manual 时需要提供 stock_ids")
        selected_stocks = db.query(Stock).filter(Stock.id.in_(payload.stock_ids)).all()
        if not selected_stocks:
            raise HTTPException(status_code=400, detail="stock_ids 无效或为空")
    else:
        latest_trade_date = db.query(func.max(Signal.trade_date)).filter(Signal.signal == "Buy").scalar()
        if not latest_trade_date:
            raise HTTPException(status_code=400, detail="暂无 Buy 信号可用")
        buy_q = (
            db.query(Stock)
            .join(Signal, Signal.code == Stock.code)
            .filter(
                Signal.trade_date == latest_trade_date,
                Signal.signal == "Buy",
                Stock.is_active == True,
            )
        )
        buy_list = buy_q.all()
        if not buy_list:
            raise HTTPException(status_code=400, detail="最新交易日无符合条件的 Buy 信号")
        take = min(payload.count, len(buy_list))
        selected_stocks = random.sample(buy_list, take)

    allocations = []
    for stock in selected_stocks[: payload.count]:
        alloc = Allocation(
            user_id=user.id,
            stock_id=stock.id,
            batch_date=payload.batch_date,
            vip_level_at_allocation=get_effective_vip_level(db, user),
            status="active",
        )
        db.add(alloc)
        allocations.append({"code": stock.code, "name": stock.name})

    db.commit()

    return {
        "message": f"已为用户 {user.username} 分配 {len(allocations)} 只股票",
        "batch_date": str(payload.batch_date),
        "vip_level": get_effective_vip_level(db, user),
        "stock_limit": stock_limit,
        "stocks": allocations,
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
