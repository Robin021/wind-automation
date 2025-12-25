"""
Tushare 数据源
"""
from typing import List, Dict, Any
from datetime import date, timedelta
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
            
            import tushare as ts
            # 使用自定义域名（若配置）连接 Tushare
            ts.set_token(settings.TUSHARE_TOKEN)
            self._pro = ts.pro_api(settings.TUSHARE_TOKEN)
            
            # 测试连接
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
            # 轻量健康检查：只要 token 有效可调用接口就视为可用
            self._is_available = True
            self._last_error = None
            return True
            
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
            start_str = start_date.strftime('%Y%m%d')
            end_str = end_date.strftime('%Y%m%d')

            loop = asyncio.get_event_loop()

            def _fetch_with_adj():
                daily = self._pro.daily(ts_code=ts_code, start_date=start_str, end_date=end_str)
                try:
                    adj = self._pro.adj_factor(ts_code=ts_code, start_date=start_str, end_date=end_str)
                except Exception:
                    adj = None
                if adj is not None and not adj.empty and daily is not None and not daily.empty:
                    daily = daily.merge(adj[["trade_date", "adj_factor"]], on="trade_date", how="left")
                    daily = daily.sort_values("trade_date")
                    # Wind CHO 口径前复权：使用最新因子为基准
                    latest_factor = daily["adj_factor"].dropna().iloc[-1] if daily["adj_factor"].notna().any() else None
                    if latest_factor and latest_factor != 0:
                        ratio = daily["adj_factor"] / latest_factor
                        for col in ["open", "high", "low", "close", "pre_close"]:
                            if col in daily.columns:
                                daily[col] = daily[col] * ratio
                        if "amount" in daily.columns:
                            daily["amount"] = daily["amount"] * ratio
                return daily

            df = await loop.run_in_executor(None, _fetch_with_adj)
            
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
            
            return result
            
        except Exception as e:
            raise RuntimeError(f"获取日线数据失败: {e}")
    
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
