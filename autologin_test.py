import os
import re
config_file = os.path.expanduser("~/.Wind/WFT/users/Auth/user.config")
with open(config_file, "r", encoding="utf-8") as f:
  content = f.read()
match = re.search(r'isAutoLogin="(\d+)"', content)
if match:
  is_auto_login = match.group(1)
  print(is_auto_login)
else:
  print("isAutoLogin not found")

