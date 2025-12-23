"""
Tushare 数据源
"""
from typing import List, Dict, Any
from datetime import date
import asyncio

from backend.datasources.base import DataSourceBase, StockQuote, DailyData
from backend.core.config import settings


class TushareDataSource(DataSourceBase):
    """Tushare 数据源"""
    
    name = "tushare"
    priority = 1  # 最高优先级
    
    def __init__(self):
        super().__init__()
        self._pro = None
    
    async def initialize(self) -> bool:
        """初始化 Tushare 连接"""
        try:
            if not settings.TUSHARE_TOKEN:
                self._last_error = "TUSHARE_TOKEN 未配置"
                self._is_available = False
                return False
            
            # 如果已经初始化过且可用，直接返回，避免重复调用 health_check
            if self._pro and self._is_available:
                return True
            
            import tushare as ts
            # 使用自定义域名（若配置）连接 Tushare
            ts.set_token(settings.TUSHARE_TOKEN)
            self._pro = ts.pro_api(settings.TUSHARE_TOKEN)
            custom_base = getattr(settings, "TUSHARE_BASE_URL", "http://api.tushare.pro")
            if custom_base:
                # 某些版本的 tushare 不接受 base 参数，这里直接覆盖内部 http_url
                try:
                    self._pro._DataApi__http_url = custom_base  # type: ignore[attr-defined]
                except Exception:
                    pass
            
            # 只在首次初始化时测试连接，避免重复调用消耗配额
            if not self._is_available:
                await self.health_check()
            return self._is_available
            
        except ImportError:
            self._last_error = "tushare 库未安装"
            self._is_available = False
            return False
        except Exception as e:
            self._last_error = str(e)
            self._is_available = False
            return False
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            if not self._pro:
                self._is_available = False
                return False
            
            # 尝试获取交易日历来测试连接
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None, 
                lambda: self._pro.trade_cal(exchange='SSE', is_open='1', limit=1)
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
    
    async def get_realtime_quote(self, code: str) -> StockQuote:
        """获取实时行情"""
        if not self._is_available:
            raise RuntimeError("Tushare 数据源不可用")
        
        # Tushare pro 不提供实时行情，使用日线最新数据替代
        # 或者可以用 ts.get_realtime_quotes()
        try:
            import tushare as ts
            
            # 转换代码格式：600000.SH -> 600000
            ts_code = code.split('.')[0]
            
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: ts.get_realtime_quotes(ts_code)
            )
            
            if df is None or df.empty:
                raise ValueError(f"无法获取 {code} 的行情数据")
            
            row = df.iloc[0]
            return StockQuote(
                code=code,
                name=row.get('name', ''),
                open=float(row['open']) if row.get('open') else None,
                high=float(row['high']) if row.get('high') else None,
                low=float(row['low']) if row.get('low') else None,
                close=float(row['price']) if row.get('price') else None,
                pre_close=float(row['pre_close']) if row.get('pre_close') else None,
                volume=float(row['volume']) if row.get('volume') else None,
                amount=float(row['amount']) if row.get('amount') else None,
                date=row.get('date', ''),
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
            raise RuntimeError("Tushare 数据源不可用")
        
        try:
            # 转换代码格式：600000.SH -> 600000.SH (tushare pro 使用相同格式)
            ts_code = self._normalize_code(code)
            
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: self._pro.daily(
                    ts_code=ts_code,
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d'),
                )
            )
            
            if df is None or df.empty:
                return []
            
            result = []
            for _, row in df.iterrows():
                result.append(DailyData(
                    date=row['trade_date'],
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row['vol'],
                    amount=row.get('amount'),
                ))
            
            # 按日期正序排列
            result.reverse()
            return result
            
        except Exception as e:
            error_msg = str(e)
            # 如果是限频错误，提供更详细的提示
            if "每分钟最多访问" in error_msg or "800次" in error_msg:
                raise RuntimeError(f"获取日线数据失败: {error_msg} (可能是数据量过大或限频规则限制)")
            raise RuntimeError(f"获取日线数据失败: {error_msg}")
    
    async def get_stock_list(self) -> List[Dict[str, Any]]:
        """获取股票列表"""
        if not self._is_available:
            raise RuntimeError("Tushare 数据源不可用")
        
        try:
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: self._pro.stock_basic(
                    exchange='',
                    list_status='L',
                    fields='ts_code,symbol,name,area,industry,market,list_date'
                )
            )
            
            if df is None or df.empty:
                return []
            
            result = []
            for _, row in df.iterrows():
                result.append({
                    'code': row['ts_code'],
                    'name': row['name'],
                    'market': row['market'],
                    'industry': row.get('industry', ''),
                    'area': row.get('area', ''),
                    'list_date': row.get('list_date', ''),
                })
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"获取股票列表失败: {e}")

