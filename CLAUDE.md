# EasyRAG 项目指令 (CLAUDE.md)

> 本文件是 EasyRAG 项目的 Claude Code 指令。所有 agent 在本仓库工作前**必须**阅读并遵循。

---

## 1. 项目概述

EasyRAG 是智能文档检索（RAG）系统，含对话、知识库、工作流、Agent、工具、技能、MCP、待办、设置等模块。

- **前端**：Vue 3 + Pinia + Element Plus + Vue Flow（`frontend/`，12 模块已全 mock 完成）
- **后端**：Python 3.11 + FastAPI + SQLAlchemy 2.0 (async)（`backend/`，开发中）
- **状态**：后端 Plan 1（基础设施）已完成，正在按 9 份 plan 推进 Plan 2-9

---

## 2. 技术栈

| 层 | 选型 |
|----|------|
| 后端框架 | FastAPI + Uvicorn（async） |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| 数据库 | PostgreSQL 16 + pgvector + pg_trgm |
| 缓存/队列 | Redis 7 |
| 异步任务 | ARQ |
| 对象存储 | 本地 FS（抽象层）→ MinIO |
| LLM/Embedding/Rerank | LangChain 1.X + 云 API（OpenAI 兼容）+ provider 抽象 |
| 工作流引擎 | LangGraph + PostgresSaver |
| 认证 | JWT（python-jose）+ passlib(bcrypt) |
| 日志/追踪 | structlog + Langfuse（自部署，可切 LangSmith） |
| 包管理 | **uv** |
| 前端 | Vue 3 + TS + Pinia + Element Plus + Vue Flow |

---

## 3. 开发环境

- **本机**：Windows，用 **uv** 管理 Python 3.11（`uv venv --python 3.11`，`uv run ...`）。本机**不起 Docker**。
- **基础设施（虚拟机 192.168.137.13）**：PostgreSQL+pgvector(:5432)、Redis(:6379)、MinIO(:9000)、Langfuse(:3030)、OpenSandbox(:8090)。已通过 `docker-compose.yml.bak` 跑起。
- **凭据**：PG user `easyrag` / pwd `easyrag2026`；Redis pwd `easyrag2026`。
- **V2 数据库**：`easyrag_v2`（V1 的 `easyrag` 库保留，勿动）。
- 连接串：`postgresql+asyncpg://easyrag:easyrag2026@192.168.137.13:5432/easyrag_v2`

---

## 4. 常用命令（在 `backend/` 下执行）

```bash
# 环境
uv venv --python 3.11
uv pip install -e ".[dev]"          # 或 uv sync

# 测试
uv run pytest                       # 全量
uv run pytest tests/test_xxx.py -v  # 单文件

# 起服务
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 数据库迁移
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "描述"

# Python/SQL 一次性脚本（临时装包）
uv run --with asyncpg python -c "..."
```

---

## 5. ⚡ 命令授权（用户明确授权，务必遵循）

**用户已授权：本项目中所有 `cmd` / `git` / `uv` / `pytest` / `alembic` / `docker` / `curl` / `powershell` 等命令，agent 可直接运行，无需询问权限。**

**唯一例外：删除文件或破坏性操作（`rm` / `git rm` / `git reset --hard` / `DROP` 等）必须先询问用户确认。**

> 含义：agent 不要为运行命令而暂停确认；看到需要跑的 git/uv/pytest 命令直接跑。只有删除文件类操作才停下来问。

---

## 6. 开发约定

### 6.1 API 契约（后端必须对齐前端）
- 基础路径 `/api/v2`
- 统一响应 `{ code, message, data }`，`code === 0` 成功
- **业务异常返回 HTTP 200 + code**（非 0），适配前端 axios 拦截器（HTTP 4xx/5xx 会走 error 分支丢失 message）
- 错误码分段：`40001-40099` 参数/请求，`40100-40199` 认证（40101/40102 触发前端 refresh），`40400+` 不存在，`42901` 并发，`50001+` 服务端
- JWT：`Authorization: Bearer <token>`；access 2h + refresh 7d
- SSE 流式：`/chat`、`/executions/:id/stream`

### 6.2 代码规范
- **异步优先**：`async def` + asyncpg + async session
- **所有后端方法必须写中文 docstring** 解释其用途（用户要求，强制）
- 文件职责单一，遵循各 plan 的目录结构
- 密钥加密存储（`app/security/crypto.py` Fernet），`.env` 不入库
- Windows 测试：conftest 设 `WindowsSelectorEventLoopPolicy` + function-scope engine dispose（asyncpg 要求）

### 6.3 TDD
- 先写失败测试 → 实现 → 测试通过 → commit
- 每个 Task 末尾 `git commit`（conventional commits：`feat:`/`fix:`/`chore:`/`test:`/`docs:`）

### 6.4 提交与分支
- 当前后端开发分支：`feat/backend`
- `main` 为稳定分支，不在 `main` 上直接开发

---

## 7. 目录结构

```
EasyRag/
├── backend/                  # 后端（FastAPI）
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py         # Pydantic Settings
│   │   ├── api/v2/           # 路由（auth/health/...）
│   │   ├── models/           # ORM
│   │   ├── schemas/          # Pydantic 请求响应
│   │   ├── services/         # 业务编排
│   │   ├── core/             # 领域算法（retrieval/parser/agent/engine）
│   │   ├── providers/        # LangChain provider / storage / trace / sandbox
│   │   ├── security/         # jwt / password / crypto / init_admin
│   │   ├── db/               # session / redis
│   │   ├── sse/              # SSE emitter / bus
│   │   └── worker/           # ARQ 任务
│   ├── alembic/              # 迁移
│   ├── tests/
│   └── pyproject.toml
├── frontend/                 # 前端（Vue3）
├── docs/
│   ├── backend-plans/        # 后端设计方案（主方案 + Phase2/3 详细设计）
│   └── superpowers/plans/    # 9 份实施 plan（Phase1/2/3）
├── deploy/                   # init.sql 等
├── docker-compose.yml.bak    # 虚拟机基础设施编排（参考）
└── CLAUDE.md                 # 本文件
```

---

## 8. 关联文档（工作前必读相关部分）

- 设计总方案：`docs/backend-plans/后端开发设计方案.md`
- Phase2/3 详细设计（含 LangChain 1.X）：`docs/backend-plans/后端设计方案-Phase2-3详细设计.md`
- 9 份实施 plan：`docs/superpowers/plans/2026-08-08-phase1-*.md` 及 `phase2-*.md`
- 前端契约：`frontend/src/api/*.ts`、`frontend/src/types/*.ts`、`frontend/src/mock/index.ts`

---

## 9. 当前进度

- ✅ Plan 1（基础设施）：脚手架/config/DB/ORM/统一响应/auth(JWT)/health/logging，22 测试绿，admin/admin123 可登录，连虚拟机 easyrag_v2
- ⏳ Plan 2-9：settings/provider/langchain_factory → 知识库解析 → 检索 → chat → elements → workflow → tools/skills/mcp → agents/Phase3

---

## 10. 重要决策（Grill-Me 结论，勿随意更改）

- 模型走**云 API + provider 抽象**（无 GPU）
- tracing **可切换** LangSmith / 自部署 Langfuse / none（`TRACING_PROVIDER`）
- 工作流引擎 **LangGraph + PostgresSaver**
- chat/agents 用 **LangChain 1.X**（LCEL + create_react_agent）
- 代码沙箱用虚拟机 **OpenSandbox** (:8090)，非自建 docker-py
- Phase1 单用户 admin，Phase3 再加 RBAC

详见 `docs/backend-plans/` 与记忆 `backend-design-decisions-2026-08-08`。
