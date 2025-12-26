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
    ENABLE_AKSHARE: bool = True
    
    # 日志
    LOG_LEVEL: str = "INFO"
    
    # 微信支付 V3 配置
    WECHAT_PAY_MOCK: bool = True  # 是否使用 Mock 模式
    WECHAT_PAY_MCHID: str = ""  # 商户号
    WECHAT_PAY_MERCHANT_SERIAL_NO: str = ""  # 商户证书序列号
    WECHAT_PAY_MERCHANT_PRIVATE_KEY_PATH: str = ""  # 商户私钥路径
    WECHAT_PAY_API_V3_KEY: str = ""  # APIv3 密钥
    WECHAT_PAY_NOTIFY_URL: str = ""  # 支付回调通知 URL
    WECHAT_PAY_APPID_MP: str = ""  # 公众号 AppID
    WECHAT_PAY_APPID_MINI: str = ""  # 小程序 AppID
    WECHAT_PAY_PLATFORM_CERT_PATH: str = ""  # 平台证书路径
    WECHAT_PAY_PLATFORM_SERIAL_NO: str = ""  # 平台证书序列号
    
    # VIP 默认配置（可被数据库配置覆盖）
    DEFAULT_VIP_LEVELS: dict = {
        0: {"name": "免费用户", "stock_limit": 5},
        1: {"name": "VIP1", "stock_limit": 10},
        2: {"name": "VIP2", "stock_limit": 20},
        3: {"name": "VIP3", "stock_limit": 50},
        4: {"name": "SVIP", "stock_limit": -1},  # -1 表示不限
    }


settings = Settings()

