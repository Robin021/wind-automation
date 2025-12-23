"""
AKShare 数据源
"""
from typing import List, Dict, Any
from datetime import date
import asyncio

from backend.datasources.base import DataSourceBase, StockQuote, DailyData


class AKShareDataSource(DataSourceBase):
    """AKShare 数据源（免费，无需 token）"""
    
    name = "akshare"
    priority = 2  # 备用数据源
    
    def __init__(self):
        super().__init__()
        self._ak = None
    
    async def initialize(self) -> bool:
        """初始化 AKShare"""
        try:
            import akshare as ak
            self._ak = ak
            
            # 测试连接
            await self.health_check()
            return self._is_available
            
        except ImportError:
            self._last_error = "akshare 库未安装"
            self._is_available = False
            return False
        except Exception as e:
            self._last_error = str(e)
            self._is_available = False
            return False
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            if not self._ak:
                self._is_available = False
                return False
            
            # 尝试获取交易日历来测试
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: self._ak.tool_trade_date_hist_sina()
            )
            
            self._is_available = df is not None and len(df) > 0
            if not self._is_available:
                self._last_error = "无法获取数据"
            else:
                self._last_error = None
            
            return self._is_available
            
        except Exception as e:
            self._last_error = str(e)
            self._is_available = False
            return False
    
    def _convert_code_for_ak(self, code: str) -> tuple:
        """转换代码格式为 AKShare 格式
        
        Returns:
            tuple: (symbol, market) 如 ('600000', 'sh')
        """
        code = code.upper().strip()
        
        if '.' in code:
            symbol, market = code.split('.')
            return symbol, market.lower()
        
        # 根据代码前缀判断市场
        if code.startswith(('6', '5')):
            return code, 'sh'
        elif code.startswith(('0', '3')):
            return code, 'sz'
        elif code.startswith(('8', '4')):
            return code, 'bj'
        
        return code, 'sh'
    
    async def get_realtime_quote(self, code: str) -> StockQuote:
        """获取实时行情"""
        if not self._is_available:
            raise RuntimeError("AKShare 数据源不可用")
        
        try:
            symbol, market = self._convert_code_for_ak(code)
            
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: self._ak.stock_zh_a_spot_em()
            )
            
            if df is None or df.empty:
                raise ValueError(f"无法获取行情数据")
            
            # 查找对应股票
            row = df[df['代码'] == symbol]
            if row.empty:
                raise ValueError(f"未找到股票 {code}")
            
            row = row.iloc[0]
            return StockQuote(
                code=code,
                name=row.get('名称', ''),
                open=float(row['今开']) if row.get('今开') else None,
                high=float(row['最高']) if row.get('最高') else None,
                low=float(row['最低']) if row.get('最低') else None,
                close=float(row['最新价']) if row.get('最新价') else None,
                pre_close=float(row['昨收']) if row.get('昨收') else None,
                volume=float(row['成交量']) if row.get('成交量') else None,
                amount=float(row['成交额']) if row.get('成交额') else None,
            )
            
        except Exception as e:
            raise RuntimeError(f"获取实时行情失败: {e}")
    
    async def get_daily_data(
        self, 
        code: str, 
        start_date: date, 
        end_date: date
    ) -> List[DailyData]:
        """获取日线数据"""
        if not self._is_available:
            raise RuntimeError("AKShare 数据源不可用")
        
        try:
            symbol, market = self._convert_code_for_ak(code)
            full_symbol = f"{market}{symbol}"
            
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: self._ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d'),
                    adjust="qfq",  # 前复权
                )
            )
            
            if df is None or df.empty:
                return []
            
            result = []
            for _, row in df.iterrows():
                result.append(DailyData(
                    date=str(row['日期']),
                    open=float(row['开盘']),
                    high=float(row['最高']),
                    low=float(row['最低']),
                    close=float(row['收盘']),
                    volume=float(row['成交量']),
                    amount=float(row.get('成交额', 0)),
                ))
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"获取日线数据失败: {e}")
    
    async def get_stock_list(self) -> List[Dict[str, Any]]:
        """获取股票列表"""
        if not self._is_available:
            raise RuntimeError("AKShare 数据源不可用")
        
        try:
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: self._ak.stock_zh_a_spot_em()
            )
            
            if df is None or df.empty:
                return []
            
            result = []
            for _, row in df.iterrows():
                code = row['代码']
                # 转换为标准格式
                if code.startswith(('6', '5')):
                    market = 'SH'
                elif code.startswith(('0', '3')):
                    market = 'SZ'
                elif code.startswith(('8', '4')):
                    market = 'BJ'
                else:
                    market = ''
                
                result.append({
                    'code': f"{code}.{market}" if market else code,
                    'name': row['名称'],
                    'market': market,
                })
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"获取股票列表失败: {e}")

