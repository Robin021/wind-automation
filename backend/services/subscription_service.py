"""
订阅服务
"""
from datetime import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from backend.models.user import User
from backend.models.user_subscription import UserSubscription


def grant_or_extend_subscription(
    db: Session,
    user: User,
    vip_level: int,
    duration_months: int,
) -> UserSubscription:
    """
    发放或续期订阅
    - 如果已有订阅且未过期，则在现有到期日基础上延长
    - 否则从当前时间开始计算
    """
    now = datetime.utcnow()
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
    
    if sub:
        # 已有订阅记录
        base_date = sub.expires_at if sub.expires_at > now else now
        sub.vip_level = vip_level
        sub.expires_at = base_date + relativedelta(months=duration_months)
        sub.updated_at = now
    else:
        # 新建订阅
        sub = UserSubscription(
            user_id=user.id,
            vip_level=vip_level,
            starts_at=now,
            expires_at=now + relativedelta(months=duration_months),
        )
        db.add(sub)
    
    # 同步更新用户 vip_level
    user.vip_level = vip_level
    db.commit()
    db.refresh(sub)
    return sub


def get_effective_vip_level(db: Session, user: User, now: datetime = None) -> int:
    """
    获取用户实际生效的 VIP 等级
    - 如果有有效订阅，返回订阅等级
    - 否则返回用户表中的 vip_level（可能是管理员手工设置或默认0）
    """
    if now is None:
        now = datetime.utcnow()
    
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
    
    if sub and sub.expires_at > now:
        return sub.vip_level
    
    # 订阅过期或无订阅，返回用户表中的等级
    return user.vip_level
