"""
订阅/会员 API
- 查询当前订阅
- mock 环境下自助开通（无真实支付）
- 管理员手工发放
"""
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.v1.auth import get_current_admin, get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.models.user import User
from backend.models.user_subscription import UserSubscription
from backend.services.subscription_service import (
    grant_or_extend_subscription,
    get_effective_vip_level,
)

router = APIRouter()


class SubscriptionInfo(BaseModel):
    vip_level: int  # users.vip_level
    effective_vip: int  # 实际生效（订阅 > 手工设置 > 过期则 0）
    source: str  # subscription/manual/expired/free
    starts_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    has_subscription: bool
    mock_enabled: bool


def _build_info(db: Session, user: User) -> SubscriptionInfo:
    now = datetime.utcnow()
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
    effective = get_effective_vip_level(db, user, now=now)

    manual_override = bool(sub and user.vip_level != sub.vip_level)
    if sub and sub.expires_at > now:
        source = "manual" if manual_override else "subscription"
    elif sub and sub.expires_at <= now:
        source = "manual" if manual_override and user.vip_level > 0 else "expired"
    elif user.vip_level > 0:
        source = "manual"
    else:
        source = "free"

    return SubscriptionInfo(
        vip_level=user.vip_level,
        effective_vip=effective,
        source=source,
        starts_at=sub.starts_at if sub else None,
        expires_at=sub.expires_at if sub else None,
        has_subscription=sub is not None,
        mock_enabled=bool(getattr(settings, "WECHAT_PAY_MOCK", True)),
    )


@router.get("/me", response_model=SubscriptionInfo)
async def get_my_subscription(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """获取当前用户订阅信息"""
    return _build_info(db, current_user)


class MockUpgradePayload(BaseModel):
    vip_level: int = Field(..., ge=1, le=4)
    duration_months: int = Field(3, ge=1, le=24)


@router.post("/mock-upgrade", response_model=SubscriptionInfo)
async def mock_upgrade(
    payload: MockUpgradePayload,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """
    在 mock 环境下自助开通/续费订阅（便于本地/测试，无需支付）
    注意：生产环境应关闭 WECHAT_PAY_MOCK，并通过支付回调开通
    """
    if not getattr(settings, "WECHAT_PAY_MOCK", True):
        raise HTTPException(status_code=400, detail="当前环境不允许直接开通，请通过支付完成")

    grant_or_extend_subscription(
        db,
        user=current_user,
        vip_level=payload.vip_level,
        duration_months=payload.duration_months,
    )
    return _build_info(db, current_user)


class GrantPayload(BaseModel):
    user_id: int
    vip_level: int = Field(..., ge=0, le=4)
    duration_months: int = Field(3, ge=1, le=24)


@router.post("/grant", response_model=SubscriptionInfo)
async def grant_subscription(
    payload: GrantPayload,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """管理员手工发放/续费订阅"""
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    grant_or_extend_subscription(
        db,
        user=user,
        vip_level=payload.vip_level,
        duration_months=payload.duration_months,
    )
    return _build_info(db, user)
