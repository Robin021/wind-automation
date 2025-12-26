"""
数据源抽象基类
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import date
from pydantic import BaseModel


class StockQuote(BaseModel):
    """股票行情数据"""
    code: str
    name: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    pre_close: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    date: Optional[str] = None


class DailyData(BaseModel):
    """日线数据"""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: Optional[float] = None


class DataSourceBase(ABC):
    """数据源抽象基类"""
    
    name: str = "base"
    priority: int = 0  # 优先级，数字越小优先级越高
    
    def __init__(self):
        self._is_available = False
        self._last_error: Optional[str] = None
    
    @property
    def is_available(self) -> bool:
        return self._is_available
    
    @property
    def last_error(self) -> Optional[str]:
        return self._last_error
    
    @abstractmethod
    async def initialize(self) -> bool:
        """初始化数据源连接"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass
    
    @abstractmethod
    async def get_realtime_quote(self, code: str) -> StockQuote:
        """获取实时行情
        
        Args:
            code: 股票代码，如 600000.SH
            
        Returns:
            StockQuote: 行情数据
        """
        pass
    
    @abstractmethod
    async def get_daily_data(
        self, 
        code: str, 
        start_date: date, 
        end_date: date
    ) -> List[DailyData]:
        """获取日线数据
        
        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            List[DailyData]: 日线数据列表
        """
        pass
    
    @abstractmethod
    async def get_stock_list(self) -> List[Dict[str, Any]]:
        """获取股票列表
        
        Returns:
            List[Dict]: 股票列表，每个元素包含 code, name, market 等字段
        """
        pass

    @abstractmethod
    async def get_market_indices(self) -> List[StockQuote]:
        """获取市场指数行情"""
        pass

    @abstractmethod
    async def get_sector_data(self) -> List[Dict[str, Any]]:
        """获取板块数据"""
        pass
    
    def _normalize_code(self, code: str) -> str:
        """标准化股票代码格式
        
        将各种格式统一为 600000.SH 格式
        """
        code = code.upper().strip()
        
        # 已经是标准格式
        if '.' in code:
            return code
        
        # 根据代码前缀判断市场
        if code.startswith(('6', '5')):
            return f"{code}.SH"
        elif code.startswith(('0', '3')):
            return f"{code}.SZ"
        elif code.startswith(('8', '4')):
            return f"{code}.BJ"
        
        return code

