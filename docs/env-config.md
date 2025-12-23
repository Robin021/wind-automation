# 环境变量配置指南

## 创建配置文件

在项目根目录创建 `.env.local` 文件：

```bash
touch .env.local
```

## 配置项说明

```ini
# ===========================================
# 数据源配置
# ===========================================
TUSHARE_TOKEN=你的tushare_token

# ===========================================
# 数据库配置（可选）
# 默认使用 SQLite: sqlite:///data/app.db
# ===========================================
# DATABASE_URL=postgresql://user:password@localhost:5432/wind_automation

# ===========================================
# JWT 认证密钥
# 用于用户登录鉴权，请设置一个复杂的随机字符串
# ===========================================
SECRET_KEY=your_random_secret_key_here

# ===========================================
# 服务配置
# ===========================================
API_HOST=0.0.0.0
API_PORT=8000

# ===========================================
# 日志级别 (DEBUG, INFO, WARNING, ERROR)
# ===========================================
LOG_LEVEL=INFO
```

## 获取 Tushare Token

1. 注册 [Tushare](https://tushare.pro/) 账号
2. 登录后在个人中心获取 token
3. 将 token 填入 `TUSHARE_TOKEN`

## 生成 SECRET_KEY

可以用 Python 生成：

```python
import secrets
print(secrets.token_hex(32))
```

