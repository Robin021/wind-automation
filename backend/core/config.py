"""
应用配置管理
使用 pydantic-settings 从环境变量加载配置
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""
    
    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # 数据库
    DATABASE_URL: str = "sqlite:///./data/app.db"
    
    # JWT 认证
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天
    
    # API 服务
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    # 数据源
    TUSHARE_TOKEN: str = ""
    # 可自定义 Tushare 代理域名
    TUSHARE_BASE_URL: str = "http://api.tushare.pro"
    ENABLE_AKSHARE: bool = False

    # ============ WeChat Pay (V3) ============
    # 开发/联调阶段建议开启 mock，不依赖微信证书与真实下单
    WECHAT_PAY_MOCK: bool = True
    WECHAT_PAY_MCHID: str = ""
    WECHAT_PAY_MERCHANT_SERIAL_NO: str = ""
    WECHAT_PAY_MERCHANT_PRIVATE_KEY_PATH: str = ""
    WECHAT_PAY_API_V3_KEY: str = ""
    WECHAT_PAY_NOTIFY_URL: str = ""
    WECHAT_PAY_APPID_MP: str = ""
    WECHAT_PAY_APPID_MINI: str = ""
    WECHAT_PAY_BASE_URL: str = "https://api.mch.weixin.qq.com"
    # 平台证书或微信支付公钥 PEM 路径（用于回调验签）
    WECHAT_PAY_PLATFORM_CERT_PATH: str = ""
    WECHAT_PAY_PLATFORM_SERIAL_NO: str = ""
    
    # 日志
    LOG_LEVEL: str = "INFO"
    
    # VIP 默认配置（可被数据库配置覆盖）
    DEFAULT_VIP_LEVELS: dict = {
        0: {"name": "免费用户", "stock_limit": 5},
        1: {"name": "VIP1", "stock_limit": 10},
        2: {"name": "VIP2", "stock_limit": 20},
        3: {"name": "VIP3", "stock_limit": 50},
        4: {"name": "SVIP", "stock_limit": -1},  # -1 表示不限
    }


settings = Settings()
