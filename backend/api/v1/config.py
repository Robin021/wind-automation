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
from backend.models.vip_config import VipConfig
from backend.models.vip_price_config import VipPriceConfig
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


# ============ VIP Price Schemas ============

class VipPriceUpsert(BaseModel):
    vip_level: int
    price_fen: int
    enabled: bool = True
    duration_months: int = 3


class VipPriceResponse(BaseModel):
    id: int
    vip_level: int
    price_fen: int
    enabled: bool
    duration_months: int

    class Config:
        from_attributes = True


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


@router.get("/vip-prices", response_model=List[VipPriceResponse])
async def get_vip_prices(db: Session = Depends(get_db)):
    """获取 VIP 价格配置（用于前端展示/下单定价）"""
    prices = db.query(VipPriceConfig).order_by(VipPriceConfig.vip_level).all()
    return prices


@router.post("/vip-prices", response_model=VipPriceResponse)
async def upsert_vip_price(
    payload: VipPriceUpsert,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """创建或更新 VIP 价格配置（管理员）"""
    if payload.vip_level < 0 or payload.vip_level > 4:
        raise HTTPException(status_code=400, detail="vip_level 必须在 0-4 之间")
    if payload.duration_months != 3:
        raise HTTPException(status_code=400, detail="当前仅支持 3 个月订阅")
    if payload.price_fen < 0:
        raise HTTPException(status_code=400, detail="price_fen 不能为负数")

    existing = db.query(VipPriceConfig).filter(VipPriceConfig.vip_level == payload.vip_level).first()
    if existing:
        existing.price_fen = payload.price_fen
        existing.enabled = payload.enabled
        existing.duration_months = payload.duration_months
        db.commit()
        db.refresh(existing)
        return existing

    rec = VipPriceConfig(
        vip_level=payload.vip_level,
        price_fen=payload.price_fen,
        enabled=payload.enabled,
        duration_months=payload.duration_months,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.delete("/vip-prices/{vip_level}")
async def delete_vip_price(
    vip_level: int,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """删除 VIP 价格配置（管理员）"""
    rec = db.query(VipPriceConfig).filter(VipPriceConfig.vip_level == vip_level).first()
    if not rec:
        raise HTTPException(status_code=404, detail="VIP 价格配置不存在")
    db.delete(rec)
    db.commit()
    return {"message": f"VIP{vip_level} 价格配置已删除"}

