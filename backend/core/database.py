"""
数据库连接与会话管理
"""
from sqlalchemy import create_engine, inspect, text
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
    # 确保所有模型被 import，避免 Base.metadata 里缺表
    # noqa: F401
    import backend.models  # type: ignore
    Base.metadata.create_all(bind=engine)
    _ensure_signals_columns()


def _ensure_signals_columns():
    """轻量级迁移：为 signals 表补齐新增列."""
    inspector = inspect(engine)
    if "signals" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("signals")}
    desired = {
        "match_price": "FLOAT",
        "mid": "FLOAT",
        "cho_short": "FLOAT",
        "cho_long": "FLOAT",
        "cho": "FLOAT",
        "macho": "FLOAT",
    }
    missing = {name: ddl for name, ddl in desired.items() if name not in existing}
    if not missing:
        return

    with engine.begin() as conn:
        for name, ddl in missing.items():
            conn.execute(text(f"ALTER TABLE signals ADD COLUMN {name} {ddl}"))


def get_db():
    """获取数据库会话（依赖注入用）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
