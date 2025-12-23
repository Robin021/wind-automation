
import bcrypt
import passlib
from passlib.context import CryptContext
import sys

print(f"Python version: {sys.version}")
print(f"Bcrypt version: {bcrypt.__version__}")
print(f"Passlib version: {passlib.__version__}")

password = "Admin123"
if len(sys.argv) > 1:
    password = sys.argv[1]

print(f"Testing password: '{password}'")
print(f"Password length (chars): {len(password)}")
print(f"Password length (bytes): {len(password.encode('utf-8'))}")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

try:
    hashed = pwd_context.hash(password)
    print(f"Successfully hashed. Result start: {hashed[:10]}...")
except Exception as e:
    print(f"Error during hashing: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
