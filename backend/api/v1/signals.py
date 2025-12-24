"""
信号计算与查询
"""
from datetime import date, datetime, timedelta
import asyncio
import logging
from typing import Annotated, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from backend.api.v1.auth import get_current_admin, get_current_user
from backend.datasources.manager import datasource_manager

import pandas as pd
from backend.core.database import get_db
from backend.models.signal import Signal
from backend.models.stock import Stock
from backend.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


def _safe_float(value: object) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _prepare_match_and_volume(
    df: pd.DataFrame,
    source_name: str,
) -> Tuple[pd.Series, pd.Series]:
    close = df["close"].astype(float)
    volume = df["volume"].astype(float)
    amount = df["amount"] if "amount" in df.columns else None

    volume_multiplier = 1.0
    amount_multiplier = 1.0
    if source_name == "tushare":
        volume_multiplier = 100.0  # Tushare: vol=手
        amount_multiplier = 1000.0  # Tushare: amount=千元
    elif source_name == "akshare":
        volume_multiplier = 100.0  # AKShare: 成交量通常为手
        amount_multiplier = 1.0  # AKShare: 成交额通常为元

    volume_shares = volume * volume_multiplier
    if amount is None:
        return close, volume_shares

    amount_yuan = amount.astype(float) * amount_multiplier
    valid = (volume_shares > 0) & (amount_yuan > 0)
    match_price = amount_yuan.where(valid) / volume_shares.where(valid)
    match_price = match_price.replace([float("inf"), -float("inf")], pd.NA)
    match_price = match_price.where(match_price.notna(), close)
    return match_price, volume_shares


def _compute_cho_metrics(
    df: pd.DataFrame,
    source_name: str,
    short: int,
    long: int,
    smooth: int,
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """计算 CHO/MACHO 指标（与离线公式保持一致）."""
    match_price, volume_shares = _prepare_match_and_volume(df, source_name)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    denom = (high + low).replace(0, pd.NA)
    multiplier = (2 * match_price - high - low) / denom
    multiplier = multiplier.replace([float("inf"), -float("inf")], pd.NA)
    multiplier = multiplier.fillna(0.0)
    money_flow = multiplier * volume_shares
    mid = money_flow.cumsum()

    cho_short = mid.rolling(window=short, min_periods=1).mean()
    cho_long = mid.rolling(window=long, min_periods=1).mean()
    cho = cho_short - cho_long
    macho = cho.rolling(window=smooth, min_periods=1).mean()
    return match_price, mid, cho_short, cho_long, cho, macho


class SignalSchema(BaseModel):
    id: int
    trade_date: date
    code: str
    name: Optional[str]
    signal: str
    price: Optional[float]
    match_price: Optional[float]
    mid: Optional[float]
    cho_short: Optional[float]
    cho_long: Optional[float]
    cho: Optional[float]
    macho: Optional[float]
    note: Optional[str]
    generated_at: datetime

    class Config:
        from_attributes = True


class SignalList(BaseModel):
    total: int
    items: List[SignalSchema]


@router.post("/run")
async def run_signals(
    _: Annotated[User, Depends(get_current_admin)],
    db: Session = Depends(get_db),
    trade_date: date = Query(default_factory=date.today),
):
    """
    计算并写入信号

    逻辑：
    - 行情使用前复权/不复权：按数据源返回（AKShare 已前复权，Tushare 默认不复权）
    - 成交量/成交额按数据源换算为股/元
    - MATCH 优先使用成交额/成交量（换算为 VWAP），无数据时使用收盘价
    - CHO 参数：short=3, long=24, smooth=24（smooth 仅用于 MACHO 计算）
    - MID:=SUM(VOLUME*(2*MATCH-HIGH-LOW)/(HIGH+LOW),0)
    - CHO:=MA(MID,SHORT)-MA(MID,LONG)
    - MACHO:=MA(CHO,N)
    - 买入：CHO_t > CHO_{t-1}
    - 卖出：CHO_t < CHO_{t-1}
    - 否则：Hold
    - price 使用当日收盘价
    """
    stocks = db.query(Stock).filter(Stock.is_active == True).all()
    if not stocks:
        raise HTTPException(status_code=400, detail="无可用股票池")

    # 确保数据源已初始化（不会重复初始化）
    await datasource_manager.initialize()

    # 在开始计算前，先测试一下是否已经限频
    # 如果已经限频，等待一段时间再开始
    logger.info("检测限频状态...")
    test_code = stocks[0].code if stocks else "000001.SZ"
    try:
        test_start = trade_date - timedelta(days=10)  # 只测试最近10天，减少消耗
        await datasource_manager.get_daily_data(
            code=test_code,
            start_date=test_start,
            end_date=trade_date,
        )
        logger.info("限频检测通过，开始计算")
    except Exception as e:
        error_msg = str(e)
        if "每分钟最多访问" in error_msg or "800次" in error_msg:
            logger.warning("检测到已触发限频，等待 70 秒后开始计算...")
            await asyncio.sleep(70)
        else:
            logger.warning(f"限频检测失败（非限频错误）: {error_msg}")

    now = datetime.utcnow()
    created = 0
    updated = 0
    failed = []
    api_call_count = 0  # 记录实际 API 调用次数

    # 回看窗口，满足 long/smooth 计算
    lookback_days = 180

    # 分批拉取，避免触发 Tushare 每分钟限频（800次/分钟）
    batch_size = 80
    pause_seconds = 5
    rate_limit_wait = 70
    
    logger.info(f"开始信号计算，共 {len(stocks)} 只股票，理论上需要 {len(stocks)} 次 API 调用")

    for start_idx in range(0, len(stocks), batch_size):
        batch = stocks[start_idx:start_idx + batch_size]
        rate_limit_hit = False
        for idx, s in enumerate(batch):
            try:
                # 每只股票之间添加小延迟（除了第一只），进一步降低请求频率
                if idx > 0:
                    await asyncio.sleep(0.05)  # 50ms 延迟，兼顾限频与速度
                
                start_date = trade_date - timedelta(days=lookback_days)
                data, source_name = await datasource_manager.get_daily_data(
                    code=s.code,
                    start_date=start_date,
                    end_date=trade_date,
                    with_source=True,
                )
                api_call_count += 1  # 记录 API 调用次数
                if not data or len(data) < 2:
                    raise ValueError("行情不足")

                df = pd.DataFrame(data)
                # 确保日期排序
                df = df.sort_values("date")

                short, long, smooth = 3, 24, 24
                (
                    match_price,
                    mid,
                    cho_short,
                    cho_long,
                    cho,
                    macho,
                ) = _compute_cho_metrics(df, source_name, short, long, smooth)

                if len(df) < 2:
                    sig_value = "Hold"
                else:
                    cho_now = cho.iloc[-1]
                    cho_prev = cho.iloc[-2]
                    if pd.isna(cho_now) or pd.isna(cho_prev):
                        sig_value = "Hold"
                    elif cho_now > cho_prev:
                        sig_value = "Buy"
                    elif cho_now < cho_prev:
                        sig_value = "Sell"
                    else:
                        sig_value = "Hold"

                price = _safe_float(df["close"].iloc[-1])
                match_latest = _safe_float(match_price.iloc[-1]) if len(match_price) else None
                mid_latest = _safe_float(mid.iloc[-1]) if len(mid) else None
                cho_short_latest = _safe_float(cho_short.iloc[-1]) if len(cho_short) else None
                cho_long_latest = _safe_float(cho_long.iloc[-1]) if len(cho_long) else None
                cho_latest = _safe_float(cho.iloc[-1]) if len(cho) else None
                macho_latest = _safe_float(macho.iloc[-1]) if len(macho) else None

                payload = {
                    "trade_date": trade_date,
                    "code": s.code,
                    "name": s.name,
                    "signal": sig_value,
                    "price": price,
                    "match_price": match_latest,
                    "mid": mid_latest,
                    "cho_short": cho_short_latest,
                    "cho_long": cho_long_latest,
                    "cho": cho_latest,
                    "macho": macho_latest,
                    "note": None,
                    "generated_at": now,
                }

                existing = db.query(Signal.id).filter(Signal.trade_date == trade_date, Signal.code == s.code).first()
                stmt = sqlite_insert(Signal).values(**payload)
                update_cols = {k: stmt.excluded[k] for k in payload.keys() if k not in ("trade_date", "code")}
                db.execute(
                    stmt.on_conflict_do_update(
                        index_elements=["trade_date", "code"],
                        set_=update_cols,
                    )
                )
                if existing:
                    updated += 1
                else:
                    created += 1
            except Exception as e:
                error_msg = str(e)
                failed.append({"code": s.code, "error": error_msg})
                # 检测限频错误
                if "每分钟最多访问" in error_msg or "800次" in error_msg:
                    rate_limit_hit = True
                continue
        
        # 如果本批遇到限频，等待更长时间
        if rate_limit_hit:
            logger.warning(f"检测到限频，等待 {rate_limit_wait} 秒后继续...")
            await asyncio.sleep(rate_limit_wait)
        # 分批间暂停，降低限频风险
        elif start_idx + batch_size < len(stocks):
            await asyncio.sleep(pause_seconds)

    db.commit()
    logger.info(f"信号计算完成：实际 API 调用次数 = {api_call_count}，成功 = {created + updated}，失败 = {len(failed)}")
    return {
        "message": "信号计算完成",
        "trade_date": str(trade_date),
        "created": created,
        "updated": updated,
        "failed": failed,
        "api_call_count": api_call_count,  # 返回实际调用次数，方便排查
    }


@router.get("", response_model=SignalList)
async def list_signals(
    _: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
    trade_date: Optional[date] = None,
    code: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    """查询信号"""
    query = db.query(Signal)
    if trade_date:
        query = query.filter(Signal.trade_date == trade_date)
    if code:
        query = query.filter(Signal.code == code)

    total = query.count()
    items = query.order_by(Signal.trade_date.desc(), Signal.code).offset(skip).limit(limit).all()
    return {"total": total, "items": items}
