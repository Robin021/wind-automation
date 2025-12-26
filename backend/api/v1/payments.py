"""
支付 API
- 订单管理
- 微信支付创建/回调
"""
import uuid
from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Session

from backend.api.v1.auth import get_current_user
from backend.core.config import settings
from backend.core.database import Base, get_db
from backend.models.user import User
from backend.services.subscription_service import grant_or_extend_subscription

router = APIRouter()


# ============ Order Model ============

class PaymentOrder(Base):
    """支付订单表"""
    __tablename__ = "payment_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    out_trade_no = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vip_level = Column(Integer, nullable=False)
    amount_fen = Column(Integer, nullable=False)  # 金额（分）
    duration_months = Column(Integer, nullable=False, default=3)
    channel = Column(String(32), default="native")  # native/h5/jsapi
    status = Column(String(32), default="pending")  # pending/paid/failed/cancelled
    prepay_id = Column(String(128))
    code_url = Column(String(256))
    h5_url = Column(String(512))
    is_test = Column(Integer, default=0)  # 是否测试订单
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    paid_at = Column(DateTime)


# ============ Schemas ============

class OrderCreate(BaseModel):
    vip_level: int = Field(..., ge=1, le=4)
    channel: str = Field("native", pattern="^(native|h5|jsapi)$")


class OrderResponse(BaseModel):
    id: int
    out_trade_no: str
    user_id: int
    vip_level: int
    amount_fen: int
    duration_months: int
    channel: str
    status: str
    is_test: bool
    created_at: datetime
    paid_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class PayResponse(BaseModel):
    prepay_id: Optional[str] = None
    code_url: Optional[str] = None
    h5_url: Optional[str] = None


class CreateOrderResult(BaseModel):
    order: OrderResponse
    pay: PayResponse


class OrderList(BaseModel):
    total: int
    items: List[OrderResponse]


class MockNotify(BaseModel):
    out_trade_no: str
    success: bool = True


# ============ Helpers ============

def _get_price_for_level(db: Session, vip_level: int) -> tuple:
    """获取指定等级的价格配置，返回 (price_fen, duration_months, enabled)"""
    from backend.models.vip_config import VipPriceConfig
    
    config = db.query(VipPriceConfig).filter(VipPriceConfig.vip_level == vip_level).first()
    if config:
        return config.price_fen, config.duration_months, bool(config.enabled)
    return 0, 3, False


def _generate_trade_no() -> str:
    """生成订单号"""
    now = datetime.utcnow()
    return f"WX{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


def _is_mock_mode() -> bool:
    """检查是否为测试模式"""
    mock_val = getattr(settings, "WECHAT_PAY_MOCK", "true")
    if isinstance(mock_val, bool):
        return mock_val
    return str(mock_val).lower() in ("true", "1", "yes")


# ============ Routes ============

@router.get("/my-orders", response_model=OrderList)
async def get_my_orders(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """获取当前用户的订单列表"""
    query = db.query(PaymentOrder).filter(PaymentOrder.user_id == current_user.id)
    total = query.count()
    items = query.order_by(PaymentOrder.created_at.desc()).offset(skip).limit(limit).all()
    return OrderList(total=total, items=items)


@router.post("/wechat/create", response_model=CreateOrderResult)
async def create_wechat_order(
    payload: OrderCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """创建微信支付订单"""
    price_fen, duration_months, enabled = _get_price_for_level(db, payload.vip_level)
    
    if not enabled or price_fen <= 0:
        raise HTTPException(status_code=400, detail=f"VIP{payload.vip_level} 暂不可购买，请联系管理员配置价格")
    
    is_mock = _is_mock_mode()
    out_trade_no = _generate_trade_no()
    
    order = PaymentOrder(
        out_trade_no=out_trade_no,
        user_id=current_user.id,
        vip_level=payload.vip_level,
        amount_fen=price_fen,
        duration_months=duration_months,
        channel=payload.channel,
        status="pending",
        is_test=1 if is_mock else 0,
    )
    
    pay_response = PayResponse()
    
    if is_mock:
        # Mock 模式：生成假的支付信息
        order.prepay_id = f"mock_prepay_{uuid.uuid4().hex[:16]}"
        order.code_url = f"weixin://wxpay/bizpayurl?mock={out_trade_no}"
        pay_response.prepay_id = order.prepay_id
        pay_response.code_url = order.code_url
    else:
        # 真实支付模式：调用微信支付 API
        # TODO: 集成真实微信支付
        raise HTTPException(status_code=501, detail="真实微信支付尚未实现，请开启 WECHAT_PAY_MOCK=true")
    
    db.add(order)
    db.commit()
    db.refresh(order)
    
    return CreateOrderResult(order=order, pay=pay_response)


@router.post("/wechat/notify")
async def wechat_notify(
    payload: MockNotify,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """
    处理支付回调（Mock 模式下用于模拟支付成功）
    真实模式下应由微信服务器调用，需要验签
    """
    order = db.query(PaymentOrder).filter(PaymentOrder.out_trade_no == payload.out_trade_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此订单")
    
    if order.status == "paid":
        return {"message": "订单已支付", "order_id": order.id}
    
    if payload.success:
        order.status = "paid"
        order.paid_at = datetime.utcnow()
        
        # 发放订阅
        user = db.query(User).filter(User.id == order.user_id).first()
        if user:
            grant_or_extend_subscription(
                db,
                user=user,
                vip_level=order.vip_level,
                duration_months=order.duration_months,
            )
    else:
        order.status = "failed"
    
    db.commit()
    return {"message": "支付状态已更新", "status": order.status}
