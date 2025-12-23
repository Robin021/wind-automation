"""
初始化管理员账户脚本
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.database import SessionLocal, create_db_and_tables
from backend.core.security import get_password_hash
from backend.models.user import User


def create_admin(username: str = "admin", email: str = "admin@example.com", password: str = "admin123"):
    """创建管理员账户"""
    # 确保表已创建
    create_db_and_tables()
    
    db = SessionLocal()
    try:
        # 检查是否已存在
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"管理员 {username} 已存在")
            return
        
        # 创建管理员
        admin = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            is_admin=True,
            vip_level=4,  # SVIP
        )
        db.add(admin)
        db.commit()
        
        print(f"管理员创建成功！")
        print(f"用户名: {username}")
        print(f"密码: {password}")
        print(f"请登录后立即修改密码！")
        
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="创建管理员账户")
    parser.add_argument("--username", default="admin", help="用户名")
    parser.add_argument("--email", default="admin@example.com", help="邮箱")
    parser.add_argument("--password", default="admin123", help="密码")
    
    args = parser.parse_args()
    create_admin(args.username, args.email, args.password)

