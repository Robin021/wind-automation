"""
用户管理 API（管理员）
"""
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import secrets

from backend.core.database import get_db
from backend.core.security import get_password_hash
from backend.models.user import User
from backend.api.v1.auth import get_current_admin, UserResponse

router = APIRouter()


# ============ Schemas ============

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    vip_level: Optional[int] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class UserList(BaseModel):
    total: int
    items: List[UserResponse]


class UserCreateAdmin(BaseModel):
    username: str
    email: EmailStr
    password: Optional[str] = None
    vip_level: int = 0
    is_admin: bool = False
    is_active: bool = True


class UserCreateResponse(UserResponse):
    temp_password: Optional[str] = None


class ResetPassword(BaseModel):
    new_password: Optional[str] = None


# ============ Routes ============

@router.get("", response_model=UserList)
async def list_users(
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
    vip_level: Optional[int] = None,
    is_active: Optional[bool] = None,
):
    """获取用户列表（管理员）"""
    query = db.query(User)
    
    if vip_level is not None:
        query = query.filter(User.vip_level == vip_level)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    total = query.count()
    users = query.offset(skip).limit(limit).all()
    
    return {"total": total, "items": users}


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """获取用户详情（管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """更新用户信息（管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """删除用户（管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    db.delete(user)
    db.commit()
    return {"message": "用户已删除"}


@router.post("/create", response_model=UserCreateResponse)
async def create_user(
    user_data: UserCreateAdmin,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """管理员创建用户"""
    # 唯一性检查
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    pwd = user_data.password or secrets.token_hex(4)
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(pwd),
        vip_level=user_data.vip_level,
        is_admin=user_data.is_admin,
        is_active=user_data.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 返回时不暴露密码，但在 detail 提示临时密码
    resp = UserResponse.model_validate(user)
    resp_dict = resp.model_dump()
    resp_dict["temp_password"] = pwd if user_data.password is None else None
    return resp_dict


@router.post("/{user_id}/set-vip")
async def set_user_vip(
    user_id: int,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
    vip_level: int = Query(..., ge=0, le=4),
):
    """设置用户 VIP 等级（管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user.vip_level = vip_level
    db.commit()
    db.refresh(user)
    
    return {"message": f"用户 VIP 等级已设置为 {vip_level}", "user": UserResponse.model_validate(user)}


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    payload: ResetPassword,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """重置用户密码（管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    new_pwd = payload.new_password or secrets.token_hex(4)
    user.hashed_password = get_password_hash(new_pwd)
    db.commit()
    db.refresh(user)

    return {
        "message": "密码已重置",
        "user": UserResponse.model_validate(user),
        "temp_password": None if payload.new_password else new_pwd,
    }

