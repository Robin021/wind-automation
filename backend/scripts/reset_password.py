import sys
import os

# Add the project root to the python path so imports work
sys.path.append(os.getcwd())

from backend.core.database import SessionLocal
from backend.models.user import User
from backend.core.security import get_password_hash

def reset_password(username, new_password):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"User '{username}' not found.")
            return

        print(f"Resetting password for user: {username}")
        user.hashed_password = get_password_hash(new_password)
        db.commit()
        print("Password reset successfully.")
    except Exception as e:
        print(f"Error resetting password: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python backend/scripts/reset_password.py <username> <new_password>")
        sys.exit(1)
    
    username = sys.argv[1]
    new_password = sys.argv[2]
    reset_password(username, new_password)
