"""
支付 / 订阅 API（微信支付为主）

说明：
- 目前先提供 mock 模式，便于本地联调（不需要接微信证书/签名）
- 真实微信支付 V3 接入可在后续补齐（验签、下单、解密回调等）
"""
from __future__ import annotations

from datetime import datetime
import json
import secrets
from typing import Annotated, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.config import settings
from backend.api.v1.auth import get_current_admin, get_current_user
from backend.models.user import User
from backend.models.payment_order import PaymentOrder
from backend.models.vip_price_config import VipPriceConfig
from backend.services.subscription_service import grant_or_extend_subscription
from backend.services.wechatpay_v3 import WechatPayConfig, WechatPayV3Client, decrypt_wechat_resource

router = APIRouter()


class CreateWechatOrder(BaseModel):
    vip_level: int
    channel: Literal["native", "h5", "jsapi_mp", "jsapi_mini"] = "native"
    # JSAPI 需要 openid（公众号/小程序不同）
    openid: Optional[str] = None
    # H5 需要客户端 IP（可由后端从 Request 推断，允许显式传入覆盖）
    client_ip: Optional[str] = None


class WechatPayParams(BaseModel):
    channel: str
    code_url: Optional[str] = None
    h5_url: Optional[str] = None
    prepay_id: Optional[str] = None


class PaymentOrderResponse(BaseModel):
    id: int
    out_trade_no: str
    provider: str
    channel: str
    vip_level: int
    duration_months: int
    amount_fen: int
    status: str
    created_at: datetime
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CreateWechatOrderResponse(BaseModel):
    order: PaymentOrderResponse
    pay: WechatPayParams


class OrderList(BaseModel):
    total: int
    items: List[PaymentOrderResponse]


class MockNotify(BaseModel):
    out_trade_no: str
    success: bool = True


def _gen_out_trade_no() -> str:
    # 规则：短一些方便人工排查，且足够随机避免冲突
    return f"wx_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(6)}"


def _get_price_or_400(db: Session, vip_level: int) -> VipPriceConfig:
    price = db.query(VipPriceConfig).filter(VipPriceConfig.vip_level == vip_level).first()
    if not price or not price.enabled:
        raise HTTPException(status_code=400, detail="该 VIP 等级暂不可购买（未配置价格或未启用）")
    if price.duration_months != 3:
        raise HTTPException(status_code=400, detail="当前仅支持 3 个月订阅")
    if price.price_fen <= 0:
        raise HTTPException(status_code=400, detail="价格配置不合法")
    return price


@router.post("/wechat/create", response_model=CreateWechatOrderResponse)
async def create_wechat_order(
    payload: CreateWechatOrder,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    request: Request = None,
):
    """创建微信支付订单（mock/真实下单的统一入口）"""
    if payload.vip_level < 1 or payload.vip_level > 4:
        raise HTTPException(status_code=400, detail="vip_level 必须在 1-4 之间")

    price = _get_price_or_400(db, payload.vip_level)
    out_trade_no = _gen_out_trade_no()

    order = PaymentOrder(
        provider="wechat",
        channel=payload.channel,
        out_trade_no=out_trade_no,
        user_id=current_user.id,
        vip_level=payload.vip_level,
        duration_months=price.duration_months,
        amount_fen=price.price_fen,
        status="pending",
        is_test=bool(getattr(settings, "WECHAT_PAY_MOCK", True)),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # mock 模式：直接返回可展示的“支付参数”
    if getattr(settings, "WECHAT_PAY_MOCK", True):
        if payload.channel == "native":
            pay = WechatPayParams(channel=payload.channel, code_url=f"weixin://wxpay/bizpayurl?pr=mock_{out_trade_no}")
        elif payload.channel == "h5":
            pay = WechatPayParams(channel=payload.channel, h5_url=f"https://mock-wechatpay.local/h5pay?out_trade_no={out_trade_no}")
        else:
            pay = WechatPayParams(channel=payload.channel, prepay_id=f"mock_prepay_{out_trade_no}")
        return {"order": order, "pay": pay}

    # 真实微信支付 V3
    cfg = WechatPayConfig(
        mchid=settings.WECHAT_PAY_MCHID,
        merchant_serial_no=settings.WECHAT_PAY_MERCHANT_SERIAL_NO,
        merchant_private_key_path=settings.WECHAT_PAY_MERCHANT_PRIVATE_KEY_PATH,
        api_v3_key=settings.WECHAT_PAY_API_V3_KEY,
        notify_url=settings.WECHAT_PAY_NOTIFY_URL,
        appid_mp=settings.WECHAT_PAY_APPID_MP,
        appid_mini=settings.WECHAT_PAY_APPID_MINI,
        base_url=settings.WECHAT_PAY_BASE_URL,
        platform_cert_path=settings.WECHAT_PAY_PLATFORM_CERT_PATH or None,
        platform_serial_no=settings.WECHAT_PAY_PLATFORM_SERIAL_NO or None,
    )
    client = WechatPayV3Client(cfg)

    description = f"VIP{payload.vip_level} 订阅（3个月）"

    if payload.channel == "native":
        code_url, _raw = await client.create_native(
            appid=cfg.appid_mp,
            description=description,
            out_trade_no=out_trade_no,
            total_fen=order.amount_fen,
        )
        if not code_url:
            raise HTTPException(status_code=502, detail="微信下单失败：未返回 code_url")
        return {"order": order, "pay": WechatPayParams(channel="native", code_url=code_url)}

    if payload.channel == "h5":
        ip = payload.client_ip
        if not ip and request is not None and request.client is not None:
            ip = request.client.host
        if not ip:
            raise HTTPException(status_code=400, detail="H5 下单需要 client_ip")
        h5_url, _raw = await client.create_h5(
            appid=cfg.appid_mp,
            description=description,
            out_trade_no=out_trade_no,
            total_fen=order.amount_fen,
            client_ip=ip,
        )
        if not h5_url:
            raise HTTPException(status_code=502, detail="微信下单失败：未返回 h5_url")
        return {"order": order, "pay": WechatPayParams(channel="h5", h5_url=h5_url)}

    # JSAPI：公众号/小程序都走 /v3/pay/transactions/jsapi，区别是 appid + openid
    if payload.channel in ("jsapi_mp", "jsapi_mini"):
        if not payload.openid:
            raise HTTPException(status_code=400, detail="JSAPI 下单需要 openid（建议先做绑定）")
        appid = cfg.appid_mp if payload.channel == "jsapi_mp" else cfg.appid_mini
        prepay_id, _raw = await client.create_jsapi(
            appid=appid,
            description=description,
            out_trade_no=out_trade_no,
            total_fen=order.amount_fen,
            openid=payload.openid,
        )
        if not prepay_id:
            raise HTTPException(status_code=502, detail="微信下单失败：未返回 prepay_id")
        return {"order": order, "pay": WechatPayParams(channel=payload.channel, prepay_id=prepay_id)}

    raise HTTPException(status_code=400, detail="不支持的支付渠道")


@router.post("/wechat/notify")
async def wechat_notify(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    微信支付回调入口：
    - mock 模式：直接用 out_trade_no + success 驱动订单变更与订阅生效
    - 真实模式：后续补齐验签/解密/幂等
    """
    body = (await request.body()).decode("utf-8")

    # mock 模式继续保留：方便本地手工打回调
    if getattr(settings, "WECHAT_PAY_MOCK", True):
        payload = MockNotify.model_validate_json(body)
        order = db.query(PaymentOrder).filter(PaymentOrder.out_trade_no == payload.out_trade_no).first()
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")
        if order.status == "paid":
            return {"code": "SUCCESS", "message": "already paid"}
        if not payload.success:
            order.status = "failed"
            db.commit()
            return {"code": "SUCCESS", "message": "marked failed"}
        order.status = "paid"
        order.paid_at = datetime.utcnow()
        order.raw_notify = body
    else:
        # 真实微信支付回调：验签 + 解密 resource
        cfg = WechatPayConfig(
            mchid=settings.WECHAT_PAY_MCHID,
            merchant_serial_no=settings.WECHAT_PAY_MERCHANT_SERIAL_NO,
            merchant_private_key_path=settings.WECHAT_PAY_MERCHANT_PRIVATE_KEY_PATH,
            api_v3_key=settings.WECHAT_PAY_API_V3_KEY,
            notify_url=settings.WECHAT_PAY_NOTIFY_URL,
            appid_mp=settings.WECHAT_PAY_APPID_MP,
            appid_mini=settings.WECHAT_PAY_APPID_MINI,
            base_url=settings.WECHAT_PAY_BASE_URL,
            platform_cert_path=settings.WECHAT_PAY_PLATFORM_CERT_PATH or None,
            platform_serial_no=settings.WECHAT_PAY_PLATFORM_SERIAL_NO or None,
        )
        client = WechatPayV3Client(cfg)

        # headers 小写化以兼容不同 ASGI 实现
        hdrs = {k: v for k, v in request.headers.items()}
        if not client.verify_notify_signature(hdrs, body):
            raise HTTPException(status_code=400, detail="微信回调验签失败")

        data = json.loads(body)
        resource = data.get("resource") or {}
        plain = decrypt_wechat_resource(
            api_v3_key=cfg.api_v3_key,
            associated_data=resource.get("associated_data", ""),
            nonce=resource.get("nonce", ""),
            ciphertext=resource.get("ciphertext", ""),
        )
        out_trade_no = plain.get("out_trade_no")
        trade_state = plain.get("trade_state")
        if not out_trade_no:
            raise HTTPException(status_code=400, detail="回调缺少 out_trade_no")
        order = db.query(PaymentOrder).filter(PaymentOrder.out_trade_no == out_trade_no).first()
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")
        if order.status == "paid":
            return {"code": "SUCCESS", "message": "already paid"}

        order.raw_notify = body
        if trade_state != "SUCCESS":
            order.status = "failed"
            db.commit()
            return {"code": "SUCCESS", "message": f"trade_state={trade_state}"}

        order.status = "paid"
        order.paid_at = datetime.utcnow()

    user = db.query(User).filter(User.id == order.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    grant_or_extend_subscription(db, user=user, vip_level=order.vip_level, duration_months=order.duration_months)
    db.commit()
    return {"code": "SUCCESS", "message": "paid and granted"}


@router.get("/my-orders", response_model=OrderList)
async def my_orders(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
):
    query = db.query(PaymentOrder).filter(PaymentOrder.user_id == current_user.id)
    total = query.count()
    items = query.order_by(PaymentOrder.created_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": items}


@router.get("/orders", response_model=OrderList)
async def list_orders_admin(
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
):
    query = db.query(PaymentOrder)
    if status:
        query = query.filter(PaymentOrder.status == status)
    if user_id:
        query = query.filter(PaymentOrder.user_id == user_id)
    total = query.count()
    items = query.order_by(PaymentOrder.created_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": items}

