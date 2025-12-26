"""
支付 API
- 订单管理
- 微信支付创建/回调
"""
import uuid
from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
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
    provider = Column(String(20), nullable=False, default="wechat")  # wechat/alipay
    channel = Column(String(20), nullable=False, default="native")  # native/h5/jsapi
    out_trade_no = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vip_level = Column(Integer, nullable=False)
    duration_months = Column(Integer, nullable=False, default=3)
    amount_fen = Column(Integer, nullable=False)  # 金额（分）
    status = Column(String(20), nullable=False, default="pending")  # pending/paid/failed/cancelled
    is_test = Column(Boolean, nullable=False, default=False)  # 是否测试订单
    paid_at = Column(DateTime)
    note = Column(String(255))  # 备注
    raw_notify = Column(Text)  # 原始回调数据
    
    prepay_id = Column(String(128))
    code_url = Column(String(256))
    h5_url = Column(String(512))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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


@router.post("/query-status/{out_trade_no}")
async def query_order_status(
    out_trade_no: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """
    主动查询订单支付状态（用于回调未收到时手动同步）
    """
    from backend.services.wechat_pay import query_order
    
    order = db.query(PaymentOrder).filter(PaymentOrder.out_trade_no == out_trade_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此订单")
    
    if order.status == "paid":
        return {"message": "订单已支付", "status": order.status}
    
    # 如果是测试订单，不查询微信
    if order.is_test:
        return {"message": "测试订单请使用 Mock 回调", "status": order.status}
    
    # 调用微信支付查询接口
    success, data = query_order(out_trade_no)
    
    if not success or not data:
        raise HTTPException(status_code=500, detail="查询微信支付订单失败")
    
    trade_state = data.get("trade_state")
    
    if trade_state == "SUCCESS":
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
        db.commit()
        return {"message": "订单已支付成功", "status": "paid", "trade_state": trade_state}
    
    elif trade_state in ("CLOSED", "REVOKED", "PAYERROR"):
        order.status = "failed"
        order.note = f"支付失败: {trade_state}"
        db.commit()
        return {"message": "订单支付失败", "status": "failed", "trade_state": trade_state}
    
    else:
        return {"message": f"订单状态: {trade_state}", "status": order.status, "trade_state": trade_state}


@router.post("/wechat/create", response_model=CreateOrderResult)
async def create_wechat_order(
    payload: OrderCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """创建微信支付订单"""
    from backend.models.vip_config import VipConfig
    from backend.services.wechat_pay import create_native_order, create_h5_order
    
    price_fen, duration_months, enabled = _get_price_for_level(db, payload.vip_level)
    
    if not enabled or price_fen <= 0:
        raise HTTPException(status_code=400, detail=f"VIP{payload.vip_level} 暂不可购买，请联系管理员配置价格")
    
    is_mock = _is_mock_mode()
    out_trade_no = _generate_trade_no()
    
    # 获取 VIP 等级名称用于订单描述
    vip_config = db.query(VipConfig).filter(VipConfig.level == payload.vip_level).first()
    vip_name = vip_config.name if vip_config else f"VIP{payload.vip_level}"
    description = f"Wind Automation {vip_name} - {duration_months}个月"
    
    order = PaymentOrder(
        provider="wechat",
        out_trade_no=out_trade_no,
        user_id=current_user.id,
        vip_level=payload.vip_level,
        amount_fen=price_fen,
        duration_months=duration_months,
        channel=payload.channel,
        status="pending",
        is_test=is_mock,
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
        if payload.channel == "native":
            success, msg, code_url = create_native_order(
                out_trade_no=out_trade_no,
                description=description,
                amount_fen=price_fen,
            )
            if not success:
                raise HTTPException(status_code=500, detail=msg)
            order.code_url = code_url
            pay_response.code_url = code_url
            
        elif payload.channel == "h5":
            # H5 支付需要用户 IP，这里用占位符，实际应从 request 获取
            success, msg, h5_url = create_h5_order(
                out_trade_no=out_trade_no,
                description=description,
                amount_fen=price_fen,
                payer_ip="127.0.0.1",  # TODO: 从请求头获取真实 IP
            )
            if not success:
                raise HTTPException(status_code=500, detail=msg)
            order.h5_url = h5_url
            pay_response.h5_url = h5_url
            
        else:
            # JSAPI 需要 openid，暂不支持
            raise HTTPException(status_code=400, detail="JSAPI 支付需要微信 OpenID，请使用 Native 或 H5 支付")
    
    db.add(order)
    db.commit()
    db.refresh(order)
    
    return CreateOrderResult(order=order, pay=pay_response)


@router.post("/wechat/notify/mock")
async def wechat_notify_mock(
    payload: MockNotify,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """
    Mock 支付回调（仅在 Mock 模式下使用，用于测试）
    """
    if not _is_mock_mode():
        raise HTTPException(status_code=403, detail="真实支付模式下请勿使用 Mock 回调")
    
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


@router.post("/wechat/notify")
async def wechat_notify_real(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    真实微信支付回调（由微信服务器调用）
    需要验签解密
    """
    import json
    import logging
    
    logger = logging.getLogger(__name__)
    
    # 获取请求体
    body = await request.body()
    body_str = body.decode("utf-8")
    
    # 获取微信支付需要的请求头（注意 Starlette 会把 header 名转成小写）
    headers = {
        "Wechatpay-Timestamp": request.headers.get("wechatpay-timestamp", ""),
        "Wechatpay-Nonce": request.headers.get("wechatpay-nonce", ""),
        "Wechatpay-Signature": request.headers.get("wechatpay-signature", ""),
        "Wechatpay-Serial": request.headers.get("wechatpay-serial", ""),
        "Wechatpay-Signature-Type": request.headers.get("wechatpay-signature-type", "WECHATPAY2-SHA256-RSA2048"),
    }
    
    logger.info(f"收到微信支付回调: headers={headers}, body_str={body_str}")
    
    # 使用 wechatpayv3 SDK 验签并解密
    try:
        from backend.services.wechat_pay import get_wxpay
        wxpay = get_wxpay()
        result = wxpay.callback(headers=headers, body=body_str)
        
        if not result:
            logger.error(f"微信支付回调验签失败. Headers: {headers}, Body: {body_str}")
            return {"code": "FAIL", "message": "验签失败"}
        
        data = result
        logger.info(f"微信支付回调解密成功: {data}")
    except Exception as e:
        logger.exception(f"微信支付回调验签异常: {e}. Headers: {headers}")
        return {"code": "FAIL", "message": f"验签异常: {str(e)}"}
    
    
    # 获取订单号和支付状态
    out_trade_no = data.get("out_trade_no")
    trade_state = data.get("trade_state")
    
    if not out_trade_no:
        logger.error("解密后缺少订单号")
        return {"code": "FAIL", "message": "缺少订单号"}
    
    order = db.query(PaymentOrder).filter(PaymentOrder.out_trade_no == out_trade_no).first()
    if not order:
        logger.error(f"订单不存在: {out_trade_no}")
        return {"code": "FAIL", "message": "订单不存在"}
    
    # 保存原始回调数据
    order.raw_notify = json.dumps(data, ensure_ascii=False)
    
    if order.status == "paid":
        # 已处理过，直接返回成功
        logger.info(f"订单已支付，忽略回调: {out_trade_no}")
        return {"code": "SUCCESS", "message": "成功"}
    
    if trade_state == "SUCCESS":
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
        logger.info(f"订单支付成功: {out_trade_no}")
    elif trade_state in ("CLOSED", "REVOKED", "PAYERROR"):
        order.status = "failed"
        order.note = f"支付失败: {trade_state}"
        logger.info(f"订单支付失败: {out_trade_no}, state={trade_state}")
    else:
        # 其他状态可能是 USERPAYING 等
        logger.info(f"订单状态更新: {out_trade_no}, state={trade_state}")
    
    db.commit()
    return {"code": "SUCCESS", "message": "成功"}
