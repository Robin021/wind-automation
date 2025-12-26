"""
安全相关：密码哈希、JWT 令牌
"""
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.core.config import settings

# --- Compatibility Patch for passlib + bcrypt 4.0+ ---
# See: https://github.com/pyca/bcrypt/issues/684
import bcrypt
if hasattr(bcrypt, "__version__") and bcrypt.__version__.startswith("4."):
    import passlib.handlers.bcrypt
    
    # 1. Fix missing __about__ attribute
    if not hasattr(bcrypt, "__about__"):
        class About:
            __version__ = bcrypt.__version__
        bcrypt.__about__ = About()
    
    # 2. Fix ValueError: password cannot be longer than 72 bytes during bug detection
    # Modern bcrypt doesn't have the wrap bug, so we can mock the check.
    def _mock_detect_wrap_bug(ident):
        return False
        
    passlib.handlers.bcrypt.detect_wrap_bug = _mock_detect_wrap_bug
# -----------------------------------------------------

# 密码哈希上下文：优先使用 bcrypt_sha256，兼容旧 bcrypt 哈希
pwd_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=False,
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT 访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """解码 JWT 令牌"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
print('Patch verification script loaded')
