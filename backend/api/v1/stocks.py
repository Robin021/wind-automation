"""
股票池管理 API
"""
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
import pandas as pd
from io import BytesIO

from backend.core.database import get_db
from backend.models.stock import Stock
from backend.models.user import User
from backend.api.v1.auth import get_current_admin, get_current_user

router = APIRouter()


# ============ Schemas ============

class StockCreate(BaseModel):
    code: str
    name: str
    market: Optional[str] = None
    industry: Optional[str] = None
    is_st: bool = False
    is_kcb: bool = False
    is_cyb: bool = False


class StockResponse(BaseModel):
    id: int
    code: str
    name: str
    market: Optional[str]
    industry: Optional[str]
    is_st: bool
    is_kcb: bool
    is_cyb: bool
    is_active: bool
    last_price: Optional[float]
    
    class Config:
        from_attributes = True


class StockList(BaseModel):
    total: int
    items: List[StockResponse]


class StockBatchDelete(BaseModel):
    ids: List[int]


# ============ Routes ============

@router.get("", response_model=StockList)
async def list_stocks(
    _: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    is_active: Optional[bool] = True,
    market: Optional[str] = None,
    keyword: Optional[str] = None,
):
    """获取股票列表"""
    query = db.query(Stock)
    
    if is_active is not None:
        query = query.filter(Stock.is_active == is_active)
    if market:
        query = query.filter(Stock.market == market)
    if keyword:
        query = query.filter(
            (Stock.code.contains(keyword)) | (Stock.name.contains(keyword))
        )
    
    total = query.count()
    stocks = query.offset(skip).limit(limit).all()
    
    return {"total": total, "items": stocks}


@router.post("", response_model=StockResponse)
async def create_stock(
    stock_data: StockCreate,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """添加股票（管理员）"""
    # 检查是否已存在
    if db.query(Stock).filter(Stock.code == stock_data.code).first():
        raise HTTPException(status_code=400, detail="股票代码已存在")
    
    stock = Stock(**stock_data.model_dump())
    db.add(stock)
    db.commit()
    db.refresh(stock)
    
    return stock


@router.post("/import")
async def import_stocks(
    file: UploadFile = File(...),
    _: Annotated[User, Depends(get_current_admin)] = None,
    db: Session = Depends(get_db),
):
    """批量导入股票（从 Excel）"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="请上传 Excel 文件")
    
    content = await file.read()
    df = pd.read_excel(BytesIO(content))
    
    # 期望的列：code, name, market, industry
    required_cols = ['code', 'name']
    if not all(col in df.columns for col in required_cols):
        raise HTTPException(status_code=400, detail=f"Excel 必须包含列: {required_cols}")
    
    # 预取数据库已有的代码以便一次性去重，同时跟踪文件内重复
    existing_codes = {code for (code,) in db.query(Stock.code).all()}
    seen_in_file = set()
    
    imported = 0
    skipped = 0
    invalid = 0
    
    for _, row in df.iterrows():
        raw_code = row.get('code')
        raw_name = row.get('name')
        
        if pd.isna(raw_code) or pd.isna(raw_name):
            invalid += 1
            continue
        
        code = str(raw_code).strip()
        name = str(raw_name).strip()
        
        if not code or not name:
            invalid += 1
            continue
        
        if code in existing_codes or code in seen_in_file:
            skipped += 1
            continue
        
        seen_in_file.add(code)
        
        market_val = row.get('market')
        industry_val = row.get('industry')
        
        stock = Stock(
            code=code,
            name=name,
            market=str(market_val).strip() if pd.notna(market_val) else None,
            industry=str(industry_val).strip() if pd.notna(industry_val) else None,
        )
        db.add(stock)
        imported += 1
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # 仍然捕获到唯一约束错误时给出更友好的提示
        raise HTTPException(status_code=400, detail="导入失败：存在重复的股票代码，请检查文件数据")
    
    return {
        "message": f"导入完成：新增 {imported}，跳过 {skipped}（已存在/重复），无效 {invalid}",
        "imported": imported,
        "skipped": skipped,
        "invalid": invalid,
    }


@router.put("/{stock_id}", response_model=StockResponse)
async def update_stock(
    stock_id: int,
    stock_data: StockCreate,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """更新股票信息（管理员）"""
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")
    
    for field, value in stock_data.model_dump().items():
        setattr(stock, field, value)
    
    db.commit()
    db.refresh(stock)
    return stock


@router.delete("/{stock_id}")
async def delete_stock(
    stock_id: int,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """删除股票（管理员）"""
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")
    
    db.delete(stock)
    db.commit()
    return {"message": "股票已删除"}


@router.post("/batch-delete")
async def batch_delete_stocks(
    payload: StockBatchDelete,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """批量删除股票（管理员）"""
    ids = list({i for i in payload.ids if i is not None})
    if not ids:
        raise HTTPException(status_code=400, detail="请提供要删除的股票 ID 列表")
    
    deleted = db.query(Stock).filter(Stock.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    
    return {"message": f"批量删除完成：删除 {deleted} 条", "deleted": deleted}


@router.post("/{stock_id}/toggle-active")
async def toggle_stock_active(
    stock_id: int,
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
):
    """切换股票启用/禁用状态（管理员）"""
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")
    
    stock.is_active = not stock.is_active
    db.commit()
    
    return {"message": f"股票已{'启用' if stock.is_active else '禁用'}", "is_active": stock.is_active}
