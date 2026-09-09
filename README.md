# EasyRAG

智能 RAG 管理后台，包含 Vue 3 前端与 FastAPI 后端。

## 前置条件

| 工具 | 最低版本 | 说明 |
|------|---------|------|
| Node.js | 18+ | 前端构建与开发 |
| Python | 3.11+ | 后端运行时 |
| uv | 0.11+ | Python 包管理（后端） |
| PostgreSQL | 15+ | 后端数据库（带 pgvector 扩展） |
| Redis | 7+ | 后端缓存与任务队列 |

## 快速开始

### 1. 前端（Mock 模式，无需后端）

前端当前阶段为**全 Mock 开发**，启动后所有接口由 Mock 层拦截，无需后端即可运行。

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器（Mock 已默认开启）
npm run dev
```

启动后访问 http://localhost:3000

**Mock 开关** 由环境变量 ``VITE_USE_MOCK`` 控制，默认值在 ``frontend/.env.development`` 中已设为 ``true``：

```env
VITE_API_BASE=/api/v2
VITE_USE_MOCK=true
```

也可通过命令行临时指定：

```bash
# Windows CMD
set VITE_USE_MOCK=true && npm run dev

# PowerShell
$env:VITE_USE_MOCK="true"; npm run dev
```

或者直接双击 ``frontend/start-dev.cmd`` 一键启动。

**切换到真实后端**：将 ``VITE_USE_MOCK`` 改为 ``false``，Vite 开发服务器会自动将 ``/api`` 请求代理到 ``http://localhost:8080``（配置见 ``frontend/vite.config.ts``）。

### 2. 后端

```bash
cd backend

# 1. 复制环境配置
cp .env.example .env
# 编辑 .env，填入实际的数据库地址、密钥等

# 2. 创建虚拟环境并安装依赖
uv sync

# 3. 初始化数据库迁移
uv run alembic upgrade head

# 4. 启动服务（默认端口 8080）
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

启动后访问 http://localhost:8080 查看健康探针，API 文档见 http://localhost:8080/docs

**后端配置**（``backend/.env``）关键字段：

| 变量 | 说明 | 示例 |
|------|------|------|
| ``DATABASE_URL`` | PostgreSQL 连接串 | ``postgresql+asyncpg://easyrag:easyrag2026@192.168.137.13:5432/easyrag_v2`` |
| ``REDIS_URL`` | Redis 连接串 | ``redis://:easyrag2026@192.168.137.13:6379/0`` |
| ``SECRET_KEY`` | JWT 签名密钥 | 随机字符串 |
| ``INIT_ADMIN_USERNAME`` | 初始管理员用户名 | ``admin`` |
| ``INIT_ADMIN_PASSWORD`` | 初始管理员密码 | ``admin123`` |
| ``CORS_ORIGINS`` | 允许的前端来源 | ``http://localhost:3000`` |

## 项目结构

```
EasyRAG/
├── frontend/           # Vue 3 + TypeScript + Vite 前端
│   ├── src/
│   │   ├── api/        # Axios 接口层
│   │   ├── mock/       # Mock 数据与拦截
│   │   ├── views/      # 页面组件
│   │   ├── stores/     # Pinia 状态管理
│   │   └── ...
│   ├── .env.development
│   ├── start-dev.cmd   # Windows 一键启动脚本
│   └── vite.config.ts
├── backend/            # FastAPI 后端
│   ├── app/
│   │   ├── api/v2/     # REST 接口
│   │   ├── models/     # 数据模型
│   │   ├── services/   # 业务逻辑
│   │   ├── worker/     # 异步任务
│   │   └── main.py     # 应用入口
│   ├── alembic/        # 数据库迁移
│   ├── .env.example
│   └── pyproject.toml
├── docs/               # 设计文档与模块计划
└── frontend-prototype/ # 视觉原型（只读参考）
```

## 常用命令

| 命令 | 说明 |
|------|------|
| ``cd frontend && npm run dev`` | 前端开发（Mock 模式） |
| ``cd frontend && npm run build`` | 前端类型检查 + 构建 |
| ``cd backend && uv run uvicorn app.main:app --reload`` | 后端开发 |
| ``cd backend && uv run alembic upgrade head`` | 数据库迁移 |
| ``cd backend && uv run pytest`` | 后端测试 |

## 参考文档

- 前端开发规范：``frontend/AGENTS.md``
- 模块计划：``docs/frontend-plans/``
- 总体设计：``docs/superpowers/specs/``
- 接口契约：``新版RAG需求设计文档_V2*.md``
