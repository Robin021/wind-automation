# 项目启动指南

## 环境要求

- Python 3.10+
- Node.js 18+
- pnpm / npm / yarn

## 一、配置环境变量

在项目根目录创建 `.env.local` 文件：

```bash
# 数据源
TUSHARE_TOKEN=你的tushare_token

# JWT密钥（可用 python -c "import secrets; print(secrets.token_hex(32))" 生成）
SECRET_KEY=your_random_secret_key

# 服务配置
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
```

## 二、启动后端

```bash
# 1. 进入后端目录
cd backend

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 初始化数据库和管理员账户
cd ..
python -m backend.scripts.init_admin

# 5. 启动后端服务
python -m backend.main
```

后端将运行在 http://localhost:8000

访问 http://localhost:8000/docs 可查看 API 文档

## 三、启动前端

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖
npm install
# 或 pnpm install

# 3. 启动开发服务器
npm run dev
```

前端将运行在 http://localhost:5173

## 四、默认账户

运行 `init_admin` 脚本后会创建默认管理员账户：

- 用户名：`admin`
- 密码：`admin123`

**请登录后立即修改密码！**

## 五、目录结构

```
wind-automation/
├── backend/                 # 后端代码
│   ├── api/v1/             # API 路由
│   ├── core/               # 核心配置
│   ├── datasources/        # 数据源模块
│   ├── models/             # 数据库模型
│   ├── services/           # 业务逻辑
│   ├── scripts/            # 脚本
│   ├── main.py             # 入口
│   └── requirements.txt    # 依赖
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── api/           # API 调用
│   │   ├── layouts/       # 布局组件
│   │   ├── router/        # 路由
│   │   ├── stores/        # Pinia 状态
│   │   ├── styles/        # 样式
│   │   └── views/         # 页面组件
│   └── package.json
├── data/                   # 数据目录
├── docs/                   # 文档
└── .env.local             # 环境变量（自行创建）
```

## 六、常见问题

### 1. Tushare 报错 "积分不足"

Tushare 免费用户有调用频率和积分限制，如果报错会自动降级到 AKShare。

### 2. 数据库文件位置

SQLite 数据库文件默认位于 `data/app.db`

### 3. 清空数据

删除 `data/app.db` 文件后重新运行 `init_admin` 脚本

