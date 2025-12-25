"""
数据库连接与会话管理
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.core.config import settings

# 创建引擎
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=settings.LOG_LEVEL == "DEBUG",
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 模型基类
Base = declarative_base()


def create_db_and_tables():
    """创建所有数据库表"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话（依赖注入用）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

