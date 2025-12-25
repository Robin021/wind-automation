"""
数据源管理器
支持多数据源优先级切换和自动降级
"""
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import date, datetime
import logging

from backend.datasources.base import DataSourceBase, StockQuote, DailyData
from backend.datasources.tushare_source import TushareDataSource
from backend.datasources.akshare_source import AKShareDataSource
from backend.core.config import settings

logger = logging.getLogger(__name__)


class DataSourceManager:
    """数据源管理器"""
    
    def __init__(self):
        self._sources: List[DataSourceBase] = []
        self._initialized = False
        self._last_check_time: Optional[datetime] = None
    
    async def initialize(self):
        """初始化所有数据源"""
        if self._initialized:
            return
        
        # 注册数据源（按优先级排序）
        sources = [TushareDataSource()]
        if settings.ENABLE_AKSHARE:
            sources.append(AKShareDataSource())
        
        for source in sources:
            logger.info(f"初始化数据源: {source.name}")
            try:
                await source.initialize()
                self._sources.append(source)
                logger.info(f"数据源 {source.name} 初始化{'成功' if source.is_available else '失败'}")
            except Exception as e:
                logger.error(f"数据源 {source.name} 初始化异常: {e}")
        
        # 按优先级排序
        self._sources.sort(key=lambda x: x.priority)
        self._initialized = True
    
    def get_status(self) -> List[Dict[str, Any]]:
        """获取所有数据源状态"""
        return [
            {
                "name": source.name,
                "is_available": source.is_available,
                "priority": source.priority,
                "error_message": source.last_error,
                "last_check": self._last_check_time.isoformat() if self._last_check_time else None,
            }
            for source in self._sources
        ]
    
    async def health_check(self) -> List[Dict[str, Any]]:
        """检查所有数据源健康状态"""
        results = []
        for source in self._sources:
            try:
                is_healthy = await source.health_check()
                results.append({
                    "name": source.name,
                    "is_available": is_healthy,
                    "error_message": source.last_error,
                })
            except Exception as e:
                results.append({
                    "name": source.name,
                    "is_available": False,
                    "error_message": str(e),
                })
        
        self._last_check_time = datetime.now()
        return results
    
    def _get_available_source(self) -> DataSourceBase:
        """获取第一个可用的数据源"""
        for source in self._sources:
            if source.is_available:
                return source
        raise RuntimeError("没有可用的数据源")
    
    async def get_realtime_quote(self, code: str) -> StockQuote:
        """获取实时行情（自动降级）"""
        if not self._initialized:
            await self.initialize()
        if not any(src.is_available for src in self._sources):
            await self.health_check()

        last_error = None
        for source in self._sources:
            if not source.is_available:
                try:
                    await source.health_check()
                except Exception:
                    pass
                if not source.is_available:
                    continue
            
            try:
                logger.debug(f"尝试从 {source.name} 获取 {code} 行情")
                return await source.get_realtime_quote(code)
            except Exception as e:
                logger.warning(f"数据源 {source.name} 获取行情失败: {e}")
                last_error = e
                continue
        
        raise RuntimeError(f"所有数据源均获取失败: {last_error}")
    
    async def get_daily_data(
        self,
        code: str,
        start_date: date,
        end_date: date,
        with_source: bool = False,
    ) -> Union[List[Dict[str, Any]], Tuple[List[Dict[str, Any]], str]]:
        """获取日线数据（自动降级）"""
        if not self._initialized:
            await self.initialize()
        if not any(src.is_available for src in self._sources):
            await self.health_check()

        last_error = None
        for source in self._sources:
            if not source.is_available:
                try:
                    await source.health_check()
                except Exception:
                    pass
                if not source.is_available:
                    continue
            
            try:
                logger.debug(f"尝试从 {source.name} 获取 {code} 日线数据")
                data = await source.get_daily_data(code, start_date, end_date)
                payload = [d.model_dump() for d in data]
                if with_source:
                    return payload, source.name
                return payload
            except Exception as e:
                logger.warning(f"数据源 {source.name} 获取日线数据失败: {e}")
                last_error = e
                continue
        
        raise RuntimeError(f"所有数据源均获取失败: {last_error}")
    
    async def get_stock_list(self) -> List[Dict[str, Any]]:
        """获取股票列表（自动降级）"""
        if not self._initialized:
            await self.initialize()
        if not any(src.is_available for src in self._sources):
            await self.health_check()

        last_error = None
        for source in self._sources:
            if not source.is_available:
                try:
                    await source.health_check()
                except Exception:
                    pass
                if not source.is_available:
                    continue
            
            try:
                logger.debug(f"尝试从 {source.name} 获取股票列表")
                return await source.get_stock_list()
            except Exception as e:
                logger.warning(f"数据源 {source.name} 获取股票列表失败: {e}")
                last_error = e
                continue
        
        raise RuntimeError(f"所有数据源均获取失败: {last_error}")


# 全局单例
datasource_manager = DataSourceManager()
