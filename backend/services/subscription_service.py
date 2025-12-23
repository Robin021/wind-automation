"""
订阅权益服务：计算有效 VIP、开通/续费 3 个月订阅
"""
from __future__ import annotations

from datetime import datetime, timezone
import calendar

from sqlalchemy.orm import Session

from backend.models.user import User
from backend.models.user_subscription import UserSubscription


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def add_months(dt: datetime, months: int) -> datetime:
    """
    给 datetime 加月份（按自然月，处理月底溢出）。
    例如：1/31 + 1 month -> 2/28(或2/29)
    """
    year = dt.year
    month = dt.month + months
    year += (month - 1) // 12
    month = ((month - 1) % 12) + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


def get_active_subscription(db: Session, user_id: int, now: datetime | None = None) -> UserSubscription | None:
    now = now or _utcnow()
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == user_id).first()
    if not sub:
        return None
    if sub.expires_at <= now:
        return None
    return sub


def get_effective_vip_level(db: Session, user: User, now: datetime | None = None) -> int:
    """
    计算有效 VIP：
    - 有订阅且未到期：返回订阅 vip_level
    - 否则：返回 0
    """
    sub = get_active_subscription(db, user.id, now=now)
    return sub.vip_level if sub else 0


def grant_or_extend_subscription(
    db: Session,
    user: User,
    vip_level: int,
    duration_months: int = 3,
    now: datetime | None = None,
) -> UserSubscription:
    """
    支付成功后开通/续费订阅：
    - 若已有订阅且未到期：在 expires_at 基础上 + duration
    - 若无订阅或已到期：从 now 开始 + duration
    同步把 users.vip_level 更新为购买等级（兼容现有逻辑/前端展示），但真正权限以订阅表为准。
    """
    now = now or _utcnow()
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
    if sub and sub.expires_at > now:
        base = sub.expires_at
        sub.vip_level = vip_level
        sub.expires_at = add_months(base, duration_months)
    else:
        if sub is None:
            sub = UserSubscription(user_id=user.id, vip_level=vip_level, starts_at=now, expires_at=add_months(now, duration_months))
            db.add(sub)
        else:
            sub.vip_level = vip_level
            sub.starts_at = now
            sub.expires_at = add_months(now, duration_months)

    user.vip_level = vip_level
    db.commit()
    db.refresh(sub)
    db.refresh(user)
    return sub






