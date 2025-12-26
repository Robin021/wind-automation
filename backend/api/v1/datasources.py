"""
数据源 API
"""
from typing import Annotated, List, Optional, Dict, Any
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.models.user import User
from backend.api.v1.auth import get_current_user, get_current_admin
from backend.datasources.manager import datasource_manager

router = APIRouter()


# ============ Schemas ============

class DataSourceStatus(BaseModel):
    name: str
    is_available: bool
    priority: int
    last_check: Optional[str] = None
    error_message: Optional[str] = None


class StockQuote(BaseModel):
    code: str
    name: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    date: Optional[str] = None


# ============ Routes ============

@router.get("/status", response_model=List[DataSourceStatus])
async def get_datasource_status(
    _: Annotated[User, Depends(get_current_admin)],
):
    """获取数据源状态（管理员）"""
    return datasource_manager.get_status()


@router.post("/check")
async def check_datasources(
    _: Annotated[User, Depends(get_current_admin)],
):
    """检查所有数据源健康状态（管理员）"""
    results = await datasource_manager.health_check()
    return {"results": results}


@router.get("/quote/{code}", response_model=StockQuote)
async def get_stock_quote(
    code: str,
    _: Annotated[User, Depends(get_current_user)],
):
    """获取股票实时行情"""
    try:
        quote = await datasource_manager.get_realtime_quote(code)
        return quote
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取行情失败: {str(e)}")


@router.get("/daily/{code}")
async def get_daily_data(
    code: str,
    _: Annotated[User, Depends(get_current_user)],
    start_date: date = Query(...),
    end_date: date = Query(default_factory=date.today),
):
    """获取股票日线数据"""
    try:
        data = await datasource_manager.get_daily_data(
            code=code,
            start_date=start_date,
            end_date=end_date,
        )
        return {"code": code, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")


@router.get("/indices", response_model=List[StockQuote])
async def get_market_indices(
    _: Annotated[User, Depends(get_current_user)],
):
    """获取主要市场指数"""
    try:
        return await datasource_manager.get_market_indices()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取指数失败: {str(e)}")


@router.get("/sectors", response_model=List[Dict[str, Any]])
async def get_sector_rankings(
    _: Annotated[User, Depends(get_current_user)],
):
    """获取板块涨跌幅排行"""
    try:
        return await datasource_manager.get_sector_data()
    except Exception as e:
        # 避免前端报错，返回空列表
        print(f"Error fetching sectors: {e}")  # Simple logging
        return []

