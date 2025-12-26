"""API v1 路由汇总"""
from fastapi import APIRouter

from backend.api.v1 import auth, users, stocks, allocations, config, datasources, signals, subscriptions

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["认证"])
router.include_router(users.router, prefix="/users", tags=["用户管理"])
router.include_router(stocks.router, prefix="/stocks", tags=["股票池"])
router.include_router(allocations.router, prefix="/allocations", tags=["股票分配"])
router.include_router(config.router, prefix="/config", tags=["系统配置"])
router.include_router(datasources.router, prefix="/datasources", tags=["数据源"])
router.include_router(signals.router, prefix="/signals", tags=["信号"])
router.include_router(subscriptions.router, prefix="/subscriptions", tags=["订阅"])

