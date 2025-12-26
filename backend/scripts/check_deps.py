
import sys
import bcrypt
import passlib
from passlib.context import CryptContext

print(f"Python: {sys.version}")
print(f"bcrypt version: {bcrypt.__version__}")
try:
    print(f"bcrypt about: {bcrypt.__about__}")
except AttributeError:
    print("bcrypt has no __about__ (Likely version 4.0+)")

print(f"passlib version: {passlib.__version__}")

pwd_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=False,
)

try:
    hash_ = pwd_context.hash("test_password")
    print(f"Hash success: {hash_}")
    print("Verification Succeeded!")
except Exception as e:
    print(f"Hash failed: {e}")
    sys.exit(1)
