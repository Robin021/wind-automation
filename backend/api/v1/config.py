"""
系统配置 API
"""
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.core.database import get_db
from backend.core.config import settings
from backend.models.user import User
from backend.models.vip_config import VipConfig, VipPriceConfig
from backend.models.system_config import SystemConfig
from backend.api.v1.auth import get_current_admin

router = APIRouter()


# ============ Schemas ============

class VipConfigCreate(BaseModel):
    level: int
    name: str
    stock_limit: int
    description: Optional[str] = None


class VipConfigResponse(BaseModel):
    id: int
    level: int
    name: str
    stock_limit: int
    description: Optional[str]
    
    class Config:
        from_attributes = True


class VipPriceConfigBase(BaseModel):
    vip_level: int
    price_fen: int
    duration_months: int = 3
    enabled: bool = True

class VipPriceConfigResponse(VipPriceConfigBase):
    id: int
    
    class Config:
        from_attributes = True

class FreeTrialConfig(BaseModel):
    free_trial_days: int


# ============ Routes ============

@router.get("/vip-levels", response_model=List[VipConfigResponse])
async def get_vip_levels(db: Session = Depends(get_db)):
    """获取所有 VIP 等级配置"""
    configs = db.query(VipConfig).order_by(VipConfig.level).all()
    
    # 如果数据库没有配置，返回默认配置
    if not configs:
        return [
            VipConfigResponse(
                id=0,
                level=level,
                name=info["name"],
                stock_limit=info["stock_limit"],
                description=None,
            )
            for level, info in settings.DEFAULT_VIP_LEVELS.items()
        ]
    
    return configs


@router.post("/vip-levels", response_model=VipConfigResponse)
async def create_or_update_vip_level(
    config_data: VipConfigCreate,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """创建或更新 VIP 等级配置（管理员）"""
    existing = db.query(VipConfig).filter(VipConfig.level == config_data.level).first()
    
    if existing:
        # 更新现有配置
        for field, value in config_data.model_dump().items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # 创建新配置
        config = VipConfig(**config_data.model_dump())
        db.add(config)
        db.commit()
        db.refresh(config)
        return config


@router.delete("/vip-levels/{level}")
async def delete_vip_level(
    level: int,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """删除 VIP 等级配置（管理员）"""
    config = db.query(VipConfig).filter(VipConfig.level == level).first()
    if not config:
        raise HTTPException(status_code=404, detail="VIP 等级配置不存在")
    
    db.delete(config)
    db.commit()
    return {"message": f"VIP 等级 {level} 配置已删除"}


@router.post("/vip-levels/init")
async def init_vip_levels(
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """初始化 VIP 等级配置（从默认值）"""
    # 清除现有配置
    db.query(VipConfig).delete()
    
    # 插入默认配置
    for level, info in settings.DEFAULT_VIP_LEVELS.items():
        config = VipConfig(
            level=level,
            name=info["name"],
            stock_limit=info["stock_limit"],
        )
        db.add(config)
    
    db.commit()
    return {"message": "VIP 等级配置已初始化"}


@router.get("/vip-prices", response_model=List[VipPriceConfigResponse])
async def get_vip_prices(db: Session = Depends(get_db)):
    """获取 VIP 价格配置"""
    try:
        prices = db.query(VipPriceConfig).order_by(VipPriceConfig.vip_level).all()
        # Convert integer (0/1) to bool for response if needed, 
        # but pydantic with from_attributes=True usually handles int->bool conversion if strict is false.
        # Actually sqlalchemy SQLite might return int. Pydantic handles int to bool (1->True, 0->False).
        return prices
    except Exception as e:
        print(f"Error fetching vip prices: {e}")
        return []


@router.post("/vip-prices", response_model=VipPriceConfigResponse)
async def update_vip_price(
    config_data: VipPriceConfigBase,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """更新 VIP 价格配置"""
    existing = db.query(VipPriceConfig).filter(VipPriceConfig.vip_level == config_data.vip_level).first()
    
    if existing:
        existing.price_fen = config_data.price_fen
        existing.duration_months = config_data.duration_months
        existing.enabled = 1 if config_data.enabled else 0
        db.commit()
        db.refresh(existing)
        return existing
    else:
        new_config = VipPriceConfig(
            vip_level=config_data.vip_level,
            price_fen=config_data.price_fen,
            duration_months=config_data.duration_months,
            enabled=1 if config_data.enabled else 0
        )
        db.add(new_config)
        db.commit()
        db.refresh(new_config)
        return new_config


@router.get("/free-trial", response_model=FreeTrialConfig)
async def get_free_trial(db: Session = Depends(get_db)):
    """获取免费试用期天数"""
    config = db.query(SystemConfig).filter(SystemConfig.key == "free_trial_days").first()
    days = int(config.value) if config else 0
    return FreeTrialConfig(free_trial_days=days)


@router.post("/free-trial")
async def update_free_trial(
    config: FreeTrialConfig,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """更新免费试用期天数"""
    existing = db.query(SystemConfig).filter(SystemConfig.key == "free_trial_days").first()
    if existing:
        existing.value = str(config.free_trial_days)
    else:
        existing = SystemConfig(key="free_trial_days", value=str(config.free_trial_days))
        db.add(existing)
    
    db.commit()
    return {"message": "配置已更新", "free_trial_days": config.free_trial_days}

