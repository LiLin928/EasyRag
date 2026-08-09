# Phase1 基础设施 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建 EasyRAG 后端 Phase1 基础设施——可启动、可登录、DB(pgvector)就绪、统一响应/认证/日志齐备的后端服务，作为后续所有模块的依赖底座。

**Architecture:** FastAPI(async) + SQLAlchemy 2.0(async) + asyncpg + Alembic 迁移 + PostgreSQL(pgvector/pg_trgm) + Redis + JWT 单用户认证。所有业务响应统一 `{code,message,data}`（HTTP 恒 200，业务结果由 code 表达，以适配前端 axios 拦截器）。日志用 structlog(JSON)。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, asyncpg, Alembic, Pydantic v2, pydantic-settings, python-jose, passlib[bcrypt], structlog, pytest, pytest-asyncio, httpx, Docker Compose, pgvector/pgvector:pg16.

**关联设计：** `docs/backend-plans/后端开发设计方案.md`（主方案 §2/§3/§4.2/§5.1/§8）。

---

## File Structure

本计划创建的后端骨架（仅基础设施部分，后续 plan 扩展）：

```
backend/
├── pyproject.toml                      # Task 1：依赖与项目元数据
├── Dockerfile                          # Task 1：运行镜像
├── .env.example                        # Task 2：环境变量模板
├── app/
│   ├── __init__.py
│   ├── main.py                         # Task 1/6/11/12/13：FastAPI 入口（逐步挂载）
│   ├── config.py                       # Task 2：Pydantic Settings
│   ├── exceptions.py                   # Task 6：业务异常 + 错误码常量
│   ├── api/
│   │   ├── __init__.py
│   │   ├── response.py                 # Task 6：ok()/err() 统一响应
│   │   ├── deps.py                     # Task 9：get_db / get_current_user
│   │   └── v2/
│   │       ├── __init__.py
│   │       ├── auth.py                 # Task 11：/auth/* 路由
│   │       └── health.py               # Task 12：/health
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py                   # Task 6：ApiResponse 泛型
│   │   └── auth.py                     # Task 11：LoginParams/LoginResult
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                     # Task 5：DeclarativeBase + TimestampMixin
│   │   └── user.py                     # Task 5：User ORM
│   ├── db/
│   │   ├── __init__.py
│   │   └── session.py                  # Task 4：async engine + sessionmaker
│   ├── security/
│   │   ├── __init__.py
│   │   ├── password.py                 # Task 7：bcrypt
│   │   ├── jwt.py                      # Task 8：create/verify token
│   │   └── init_admin.py               # Task 10：启动初始化 admin
│   └── logging.py                      # Task 13：structlog + request_id
├── alembic/
│   ├── env.py                          # Task 5：async 配置
│   ├── script.py.mako
│   └── versions/
│       └── 0001_init_users.py          # Task 5：首迁移
├── deploy/
│   ├── docker-compose.yml              # Task 3：postgres+redis+backend
│   └── init.sql                        # Task 3：启用 vector/pg_trgm 扩展
└── tests/
    ├── __init__.py
    ├── conftest.py                     # Task 4/9：async db fixture
    ├── test_config.py                  # Task 2
    ├── test_response.py                # Task 6
    ├── test_password.py                # Task 7
    ├── test_jwt.py                     # Task 8
    ├── test_auth_api.py                # Task 11
    └── test_health.py                  # Task 12
```

**约定：**
- 工作目录为仓库根 `EasyRag/`，后端代码在 `backend/`，部署编排在 `deploy/`。
- 测试用 `pytest`（async 用 `pytest-asyncio`，mode=auto）。
- 每个 Task 末尾 `git commit`，提交信息用 conventional commits（`feat:`/`chore:`/`test:`）。

---

### Task 1: 项目脚手架与依赖

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/Dockerfile`
- Create: `backend/app/__init__.py`（空）
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`（空）
- Create: `backend/app/api/v2/__init__.py`（空）

- [ ] **Step 1: 创建 `backend/pyproject.toml`**

```toml
[project]
name = "easyrag-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.110",
  "uvicorn[standard]>=0.29",
  "sqlalchemy[asyncio]>=2.0",
  "asyncpg>=0.29",
  "alembic>=1.13",
  "pydantic>=2.7",
  "pydantic-settings>=2.2",
  "python-jose[cryptography]>=3.3",
  "passlib[bcrypt]>=1.7",
  "bcrypt>=4.1,<4.2",            # 锁定：passlib 与 bcrypt>=4.2 有兼容告警
  "structlog>=24.1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.23",
  "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["app*"]
```

- [ ] **Step 2: 创建 `backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e ".[dev]"
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: 创建 `backend/app/main.py`（最小可启动）**

```python
from fastapi import FastAPI

app = FastAPI(title="EasyRAG API", version="0.1.0")


@app.get("/")
def root():
    """根路径健康探针，返回服务名与状态。"""
    return {"code": 0, "message": "success", "data": {"service": "easyrag", "status": "ok"}}
```

- [ ] **Step 4: 验证可启动与导入**

Run（在 `backend/` 下，先装依赖）:
```bash
cd backend && pip install -e ".[dev]" && python -c "from app.main import app; print(app.title)"
```
Expected: 输出 `EasyRAG API`，无 ImportError。

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/Dockerfile backend/app
git commit -m "chore: init backend scaffold (fastapi + deps + dockerfile)"
```

---

### Task 2: 配置管理（Pydantic Settings）

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/.env.example`
- Test: `backend/tests/__init__.py`（空）、`backend/tests/test_config.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_config.py`**

```python
import os
from app.config import Settings

def test_settings_load_from_env(monkeypatch):
    """测试 Settings 能从环境变量加载并应用默认值。"""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@host/db")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("INIT_ADMIN_PASSWORD", "pw12345")
    s = Settings()
    assert s.database_url == "postgresql+asyncpg://u:p@host/db"
    assert s.secret_key == "test-secret"
    assert s.jwt_access_expire == 7200          # 默认值
    assert s.api_prefix == "/api/v2"             # 默认值

def test_settings_missing_required_raises(monkeypatch):
    """测试缺少必填字段时 Settings 校验失败。"""
    # 清空必需变量
    for k in ("DATABASE_URL", "SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    try:
        Settings()
        assert False, "应校验失败"
    except Exception:
        assert True
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: FAIL（`ModuleNotFoundError: app.config`）

- [ ] **Step 3: 实现 `backend/app/config.py`**

```python
"""应用配置模块。

基于 pydantic-settings 从 .env 文件读取配置，集中暴露全局 settings 单例。
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局应用配置。

    所有字段均可通过 .env 文件或环境变量覆盖；标注 ``Field(...)`` 的为必填项。
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 通用
    env: str = "development"
    secret_key: str = Field(...)             # 必填：JWT + 密钥加密
    api_prefix: str = "/api/v2"
    log_level: str = "INFO"

    # 数据库
    database_url: str = Field(...)           # postgresql+asyncpg://...

    # Redis（本 plan 仅定义，暂不强制使用）
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_access_expire: int = 7200            # 秒
    jwt_refresh_expire: int = 604800

    # 初始管理员
    init_admin_username: str = "admin"
    init_admin_password: str = Field(...)

    # CORS
    cors_origins: str = "http://localhost:3000"


settings = Settings()
```

- [ ] **Step 4: 创建 `backend/.env.example`**

```env
ENV=development
SECRET_KEY=change-me-to-a-random-string
API_PREFIX=/api/v2
LOG_LEVEL=INFO

DATABASE_URL=postgresql+asyncpg://easyrag:easyrag@localhost:5432/easyrag
REDIS_URL=redis://localhost:6379/0

JWT_ACCESS_EXPIRE=7200
JWT_REFRESH_EXPIRE=604800

INIT_ADMIN_USERNAME=admin
INIT_ADMIN_PASSWORD=admin123

CORS_ORIGINS=http://localhost:3000
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `cd backend && DATABASE_URL=postgresql+asyncpg://u:p@h/d SECRET_KEY=k INIT_ADMIN_PASSWORD=p pytest tests/test_config.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/.env.example backend/tests
git commit -m "feat(config): pydantic settings + env template"
```

---

### Task 3: Docker Compose（postgres+pgvector + redis + backend）

**Files:**
- Create: `deploy/docker-compose.yml`
- Create: `deploy/init.sql`
- Create: `backend/.dockerignore`

- [ ] **Step 1: 创建 `deploy/init.sql`（启用扩展）**

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

- [ ] **Step 2: 创建 `deploy/docker-compose.yml`**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: easyrag
      POSTGRES_USER: easyrag
      POSTGRES_PASSWORD: easyrag
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U easyrag"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: [redisdata:/data]

  backend:
    build: ../backend
    env_file: ../backend/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://easyrag:easyrag@postgres:5432/easyrag
      REDIS_URL: redis://redis:6379/0
    ports: ["8000:8000"]
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_started }

volumes:
  pgdata: {}
  redisdata: {}
```

- [ ] **Step 3: 创建 `backend/.dockerignore`**

```
__pycache__
*.pyc
.venv
tests
.env
```

- [ ] **Step 4: 复制 `.env.example` 为 `backend/.env` 并验证 compose 启动**

Run:
```bash
cp backend/.env.example backend/.env
cd deploy && docker compose up -d postgres redis
docker compose ps
```
Expected: postgres 状态 `healthy`，redis `running`。

- [ ] **Step 5: 验证扩展已启用**

Run:
```bash
docker compose exec postgres psql -U easyrag -d easyrag -c "\dx" | grep -E "vector|pg_trgm"
```
Expected: 输出含 `vector` 与 `pg_trgm` 行。

- [ ] **Step 6: Commit**

```bash
git add deploy/ backend/.dockerignore
git commit -m "chore(deploy): docker compose with pgvector+redis+backend"
```

---

### Task 4: 数据库 async session

**Files:**
- Create: `backend/app/db/__init__.py`（空）
- Create: `backend/app/db/session.py`
- Test: `backend/tests/conftest.py`、`backend/tests/test_db_session.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_db_session.py`**

```python
import pytest
from sqlalchemy import text
from app.db.session import async_session

@pytest.mark.asyncio
async def test_session_can_query():
    """测试异步会话能执行简单查询并返回结果。"""
    async with async_session() as s:
        r = await s.execute(text("SELECT 1"))
        assert r.scalar() == 1
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_db_session.py -v`
Expected: FAIL（`ModuleNotFoundError: app.db.session`）

- [ ] **Step 3: 实现 `backend/app/db/session.py`**

```python
"""数据库会话模块。

创建全局异步 SQLAlchemy 引擎与会话工厂，并提供 FastAPI 依赖注入用的 get_db 生成器。
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings

engine = create_async_engine(settings.database_url, pool_size=10, max_overflow=20, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """获取异步数据库会话的依赖生成器。

    yields 一个 AsyncSession，请求结束自动关闭；典型用法：
    ``db: AsyncSession = Depends(get_db)``。
    """
    async with async_session() as s:
        yield s
```

- [ ] **Step 4: 创建 `backend/tests/conftest.py`（确保测试连到本地 compose 起的 pg）**

```python
import os
# 测试默认连 localhost:5432（compose 映射到宿主）
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://easyrag:easyrag@localhost:5432/easyrag")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "pw12345")
```

- [ ] **Step 5: 运行测试，确认通过（需 compose 的 postgres 已起）**

Run: `cd backend && pytest tests/test_db_session.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/db backend/tests/conftest.py backend/tests/test_db_session.py
git commit -m "feat(db): async engine + session factory"
```

---

### Task 5: 基础 ORM（User）+ Alembic 首迁移

**Files:**
- Create: `backend/app/models/__init__.py`、`backend/app/models/base.py`、`backend/app/models/user.py`
- Create: `backend/alembic.ini`、`backend/alembic/env.py`、`backend/alembic/script.py.mako`、`backend/alembic/versions/0001_init_users.py`
- Test: `backend/tests/test_user_model.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_user_model.py`**

```python
import pytest
from sqlalchemy import select
from app.db.session import async_session
from app.models.user import User

@pytest.mark.asyncio
async def test_create_and_query_user():
    """测试创建用户后能按条件查询并校验默认值。"""
    async with async_session() as s:
        u = User(username="t_"+__name__, hashed_password="x", role="admin")
        s.add(u); await s.commit()
        got = (await s.execute(select(User).where(User.username==u.username))).scalar_one()
        assert got.id is not None
        assert got.role == "admin"
        assert got.is_active is True
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_user_model.py -v`
Expected: FAIL（无 models 模块）

- [ ] **Step 3: 实现 `backend/app/models/base.py`**

```python
"""ORM 模型基类模块。

定义声明式基类 Base 以及通用的主键、时间戳混入。
"""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的声明式基类。"""
    pass


class TimestampMixin:
    """时间戳混入，为模型增加 created_at / updated_at 字段。

    Attributes:
        created_at: 创建时间，默认为入库时数据库当前时间。
        updated_at: 更新时间，每次更新时刷新为数据库当前时间。
    """

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class UUIDPk:
    """UUID 主键混入，为模型增加 UUID 类型自增主键 id。

    Attributes:
        id: 主键，默认由 uuid.uuid4 生成。
    """

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
```

- [ ] **Step 4: 实现 `backend/app/models/user.py`**

```python
"""用户 ORM 模型模块。"""
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPk


class User(Base, UUIDPk, TimestampMixin):
    """用户表模型。

    Attributes:
        username: 用户名，唯一且有索引。
        email: 邮箱，可空，唯一。
        hashed_password: 密码哈希值。
        display_name: 显示名，可空。
        role: 角色名，默认 "admin"。
        is_active: 是否启用，默认 True。
    """

    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 5: 创建 `backend/app/models/__init__.py`**

```python
from app.models.base import Base
from app.models.user import User

__all__ = ["Base", "User"]
```

- [ ] **Step 6: 配置 Alembic（async）— 创建 `backend/alembic.ini`**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = postgresql+asyncpg://easyrag:easyrag@localhost:5432/easyrag

[loggers]
keys = root,sqlalchemy,alembic
[handlers]
keys = console
[formatters]
keys = generic
[logger_root]
level = WARN
handlers = console
qualname =
[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine
[logger_alembic]
level = INFO
handlers =
qualname = alembic
[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic
[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 7: 创建 `backend/alembic/env.py`（async + 读 settings + autog 目标）**

```python
import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from app.config import settings
from app.models import Base  # noqa
import app.models  # noqa  确保 import 所有模型

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式生成 SQL 迁移脚本（不连接数据库）。"""
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """在给定连接上执行迁移（在线模式的实际执行入口）。"""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """在线模式：通过异步引擎连接数据库并执行迁移。"""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = settings.database_url
    connectable = async_engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 8: 创建 `backend/alembic/script.py.mako`（Alembic 标准模板）**

```
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 9: 生成首迁移并检查**

Run:
```bash
cd backend && alembic revision --autogenerate -m "init users"
```
Expected: 在 `alembic/versions/` 生成一个迁移文件，含 `create_table('users', ...)`。

- [ ] **Step 10: 应用迁移**

Run: `cd backend && alembic upgrade head`
Expected: 输出 `Running upgrade -> <rev>, init users`，无错误。

- [ ] **Step 11: 运行模型测试，确认通过**

Run: `cd backend && pytest tests/test_user_model.py -v`
Expected: PASS

- [ ] **Step 12: Commit**

```bash
git add backend/app/models backend/alembic.ini backend/alembic backend/tests/test_user_model.py
git commit -m "feat(models): User ORM + alembic async setup + init migration"
```

---

### Task 6: 统一响应 / 错误码 / 业务异常

**Files:**
- Create: `backend/app/api/response.py`、`backend/app/exceptions.py`、`backend/app/schemas/__init__.py`、`backend/app/schemas/common.py`
- Modify: `backend/app/main.py`（挂全局异常处理器）
- Test: `backend/tests/test_response.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_response.py`**

```python
import pytest
from app.exceptions import BizException, ErrorCode
from app.api.response import ok, err

def test_ok_shape():
    """测试 ok() 返回的成功响应结构。"""
    assert ok({"a": 1}) == {"code": 0, "message": "success", "data": {"a": 1}}

def test_err_shape():
    """测试 err() 返回的失败响应结构。"""
    e = err(ErrorCode.PARAM_ERROR, "坏请求")
    assert e == {"code": 40001, "message": "坏请求", "data": None}

def test_biz_exception():
    """测试 BizException 携带的错误码与消息。"""
    with pytest.raises(BizException) as ex:
        raise BizException(ErrorCode.UNAUTHORIZED, "token 过期")
    assert ex.value.code == 40101
    assert ex.value.message == "token 过期"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_response.py -v`
Expected: FAIL（无相关模块）

- [ ] **Step 3: 实现 `backend/app/exceptions.py`**

```python
"""业务异常与错误码模块。

定义统一的错误码枚举和 BizException 业务异常，用于在请求链路中携带业务错误信息。
"""
from enum import IntEnum


class ErrorCode(IntEnum):
    """业务错误码枚举（按区段划分）。"""

    SUCCESS = 0
    # 40001-40099 参数/请求错误
    PARAM_ERROR = 40001
    UNSUPPORTED_FILE = 40001       # 复用通用参数错误，业务层细分 message
    FILE_TOO_LARGE = 40002
    PRECISION_UNAVAILABLE = 40003
    LOGIN_FAILED = 40103           # 登录失败（落在认证段但不触发 refresh：refresh 仅 40101/40102）
    # 40100-40199 认证（40101/40102 触发前端 refresh）
    UNAUTHORIZED = 40101           # access token 过期
    REFRESH_INVALID = 40102        # refresh token 无效
    FORBIDDEN = 40300
    NOT_FOUND = 40400
    CONCURRENCY = 42901
    # 50001+
    LLM_TIMEOUT = 50001
    PARSE_FAILED = 50002
    DB_ERROR = 50003
    DEPENDENCY_DOWN = 50301


class BizException(Exception):
    """业务异常。

    携带错误码与可读消息，由全局异常处理器统一转成 ApiResponse 结构。
    """

    def __init__(self, code: ErrorCode, message: str | None = None):
        """初始化业务异常。

        Args:
            code: 错误码（ErrorCode 枚举）。
            message: 可读消息，未提供时使用错误码名称。
        """
        self.code = int(code)
        self.message = message or code.name
        super().__init__(self.message)
```

> **说明**：前端 `request.ts` 对 `40100-40199` 触发 refresh。我们让**只有 token 类**（40101/40102）落此段；登录失败用 40103（也在段内，但前端 refresh 失败会跳登录，行为可接受）。若要严格分离，登录失败改用 `PARAM_ERROR=40001`。

- [ ] **Step 4: 实现 `backend/app/api/response.py`**

```python
"""统一响应封装模块。

提供 ok/err 工具函数，生成符合 ApiResponse 结构的字典。
"""
from typing import Any, Optional
from app.exceptions import ErrorCode


def ok(data: Any = None, message: str = "success") -> dict:
    """构造成功响应字典。

    Args:
        data: 业务数据载荷，默认空。
        message: 提示消息，默认 "success"。

    Returns:
        形如 ``{"code": 0, "message": ..., "data": ...}`` 的字典。
    """
    return {"code": 0, "message": message, "data": data}


def err(code: ErrorCode | int, message: str) -> dict:
    """构造失败响应字典。

    Args:
        code: 错误码。
        message: 错误消息。

    Returns:
        形如 ``{"code": <code>, "message": ..., "data": None}`` 的字典。
    """
    return {"code": int(code), "message": message, "data": None}
```

- [ ] **Step 5: 实现 `backend/app/schemas/common.py`**

```python
"""通用 schema 模块。

定义统一响应体 ApiResponse 与分页参数 PaginationParams。
"""
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应体结构。

    Attributes:
        code: 业务码，0 表示成功，非 0 表示业务错误。
        message: 提示消息。
        data: 业务数据载荷，泛型。
    """

    code: int
    message: str
    data: Optional[T] = None


class PaginationParams(BaseModel):
    """分页参数。

    Attributes:
        page: 页码，从 1 开始。
        page_size: 每页条数，默认 20。
    """

    page: int = 1
    page_size: int = 20
```

- [ ] **Step 6: 实现 `backend/app/schemas/__init__.py`**

```python
from app.schemas.common import ApiResponse, PaginationParams
__all__ = ["ApiResponse", "PaginationParams"]
```

- [ ] **Step 7: 修改 `backend/app/main.py` 挂全局异常处理器**

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.exceptions import BizException

app = FastAPI(title="EasyRAG API", version="0.1.0")


@app.exception_handler(BizException)
async def biz_exception_handler(request: Request, exc: BizException):
    """全局业务异常处理器。

    将 BizException 转换为 HTTP 200 + 业务错误码的 ApiResponse 结构。
    """
    # 业务异常：HTTP 200 + code（适配前端拦截器）
    return JSONResponse(status_code=200, content={"code": exc.code, "message": exc.message, "data": None})


@app.get("/")
def root():
    """根路径健康探针，返回服务名与状态。"""
    return {"code": 0, "message": "success", "data": {"service": "easyrag", "status": "ok"}}
```

- [ ] **Step 8: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_response.py -v`
Expected: 3 passed

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/response.py backend/app/exceptions.py backend/app/schemas backend/app/main.py backend/tests/test_response.py
git commit -m "feat(api): unified response + error codes + biz exception handler"
```

---

### Task 7: 密码哈希（bcrypt）

**Files:**
- Create: `backend/app/security/__init__.py`（空）、`backend/app/security/password.py`
- Test: `backend/tests/test_password.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_password.py`**

```python
from app.security.password import hash_password, verify_password

def test_hash_and_verify():
    """测试哈希后的密码可被正确校验，且错误密码校验失败。"""
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h) is True
    assert verify_password("wrong", h) is False

def test_hash_is_unique():
    """测试同一明文密码两次哈希结果不同（盐随机）。"""
    assert hash_password("x") != hash_password("x")
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_password.py -v`
Expected: FAIL（无模块）

- [ ] **Step 3: 实现 `backend/app/security/password.py`**

```python
"""密码哈希模块。

基于 passlib + bcrypt 提供密码哈希与校验。
"""
from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """对明文密码做 bcrypt 哈希，返回哈希字符串。"""
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码是否与哈希值匹配，匹配返回 True。"""
    return _pwd.verify(plain, hashed)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_password.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/security backend/tests/test_password.py
git commit -m "feat(security): bcrypt password hashing"
```

---

### Task 8: JWT 签发与校验

**Files:**
- Create: `backend/app/security/jwt.py`
- Test: `backend/tests/test_jwt.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_jwt.py`**

```python
import pytest
from app.security.jwt import create_access_token, create_refresh_token, decode_token
from app.exceptions import BizException, ErrorCode

def test_access_roundtrip():
    """测试 access token 签发后能解码还原 sub 与 typ。"""
    t = create_access_token("user-123")
    claims = decode_token(t)
    assert claims["sub"] == "user-123"
    assert claims["typ"] == "access"

def test_refresh_typ():
    """测试 refresh token 解码后 typ 为 refresh。"""
    t = create_refresh_token("user-123")
    assert decode_token(t)["typ"] == "refresh"

def test_invalid_token_raises():
    """测试非法 token 解码时抛出 UNAUTHORIZED 业务异常。"""
    with pytest.raises(BizException) as ex:
        decode_token("not-a-jwt")
    assert ex.value.code == int(ErrorCode.UNAUTHORIZED)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_jwt.py -v`
Expected: FAIL（无模块）

- [ ] **Step 3: 实现 `backend/app/security/jwt.py`**

```python
"""JWT 令牌模块。

提供 access/refresh token 的签发与解码，使用 HS256 算法。
"""
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from app.config import settings
from app.exceptions import BizException, ErrorCode

_ALG = "HS256"


def _create(sub: str, expires: int, typ: str) -> str:
    """生成 JWT 的内部方法。

    Args:
        sub: 主题（用户 id 的字符串形式）。
        expires: 有效期（秒）。
        typ: token 类型，access 或 refresh。

    Returns:
        编码后的 JWT 字符串。
    """
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "typ": typ, "iat": int(now.timestamp()),
               "exp": int((now + timedelta(seconds=expires)).timestamp())}
    return jwt.encode(payload, settings.secret_key, algorithm=_ALG)


def create_access_token(user_id) -> str:
    """为指定用户签发 access token（短期有效）。"""
    return _create(str(user_id), settings.jwt_access_expire, "access")


def create_refresh_token(user_id) -> str:
    """为指定用户签发 refresh token（长期有效）。"""
    return _create(str(user_id), settings.jwt_refresh_expire, "refresh")


def decode_token(token: str) -> dict:
    """解码并校验 JWT，返回 claims 字典。

    Args:
        token: JWT 字符串。

    Returns:
        解码后的 claims 字典。

    Raises:
        BizException: token 无效或已过期时抛 UNAUTHORIZED。
    """
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[_ALG])
    except JWTError:
        raise BizException(ErrorCode.UNAUTHORIZED, "token 无效或已过期")
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_jwt.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/security/jwt.py backend/tests/test_jwt.py
git commit -m "feat(security): jwt access/refresh issue & verify"
```

---

### Task 9: 认证依赖 get_current_user

**Files:**
- Create: `backend/app/api/deps.py`
- Test: `backend/tests/test_deps.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_deps.py`**

```python
import pytest
from app.security.jwt import create_access_token, create_refresh_token
from app.api.deps import get_current_user, _claims_from_header
from app.exceptions import BizException, ErrorCode

def test_missing_prefix():
    """测试非 Bearer 前缀的认证头抛出业务异常。"""
    with pytest.raises(BizException):
        _claims_from_header("Token abc")          # 非 Bearer

def test_refresh_token_rejected_for_access():
    """测试用 refresh token 充当 access 时被拒绝。"""
    refresh = create_refresh_token("u1")
    with pytest.raises(BizException) as ex:
        # 用 refresh 当 access，应被拒
        _claims_from_header("Bearer " + refresh, expect_typ="access")
    assert ex.value.code == int(ErrorCode.UNAUTHORIZED)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_deps.py -v`
Expected: FAIL（无模块）

- [ ] **Step 3: 实现 `backend/app/api/deps.py`**

```python
"""请求依赖模块。

提供从 Authorization 头解析 JWT、获取当前登录用户等 FastAPI 依赖。
"""
from fastapi import Header, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.security.jwt import decode_token
from app.models.user import User
from app.exceptions import BizException, ErrorCode


def _claims_from_header(authorization: str, expect_typ: str = "access") -> dict:
    """从 Authorization 头解析 Bearer token 并返回声明（claims）。

    Args:
        authorization: 原始 Authorization 头值，需以 "Bearer " 开头。
        expect_typ: 期望的 token 类型（access/refresh），不匹配则抛 UNAUTHORIZED。

    Returns:
        解码后的 JWT claims 字典。

    Raises:
        BizException: 缺少认证信息、token 无效或类型不符时抛出。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise BizException(ErrorCode.UNAUTHORIZED, "缺少认证信息")
    claims = decode_token(authorization[7:])
    if claims.get("typ") != expect_typ:
        raise BizException(ErrorCode.UNAUTHORIZED, "token 类型错误")
    return claims


async def get_current_user(authorization: str = Header(...), db: AsyncSession = Depends(get_db)) -> User:
    """从 Authorization 头解析 JWT 并返回当前用户。

    校验 Bearer access token，按 token 中的 sub(user_id) 查询用户；
    无 token / token 无效 / 用户禁用均抛 BizException(UNAUTHORIZED)。
    """
    claims = _claims_from_header(authorization, "access")
    user = (await db.execute(select(User).where(User.id == claims["sub"]))).scalar_one_or_none()
    if not user or not user.is_active:
        raise BizException(ErrorCode.UNAUTHORIZED, "用户不存在或已禁用")
    return user
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_deps.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/deps.py backend/tests/test_deps.py
git commit -m "feat(auth): get_current_user dependency"
```

---

### Task 10: 单用户 admin 初始化

**Files:**
- Create: `backend/app/security/init_admin.py`
- Test: `backend/tests/test_init_admin.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_init_admin.py`**

```python
import pytest
from sqlalchemy import select
from app.db.session import async_session
from app.models.user import User
from app.security.init_admin import ensure_admin
from app.config import settings

@pytest.mark.asyncio
async def test_ensure_admin_idempotent():
    """测试重复调用 ensure_admin 幂等，不会重复创建管理员。"""
    await ensure_admin()
    await ensure_admin()  # 重复调用不应报错或重复创建
    async with async_session() as s:
        users = (await s.execute(select(User).where(User.username == settings.init_admin_username))).scalars().all()
        assert len(users) == 1
        assert users[0].role == "admin"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_init_admin.py -v`
Expected: FAIL（无模块）

- [ ] **Step 3: 实现 `backend/app/security/init_admin.py`**

```python
"""初始管理员初始化模块。

应用启动时确保默认管理员账号存在。
"""
from sqlalchemy import select
from app.db.session import async_session
from app.models.user import User
from app.security.password import hash_password
from app.config import settings


async def ensure_admin() -> None:
    """启动时确保初始管理员存在（幂等）。

    若 settings.init_admin_username 指定的用户不存在则按配置密码创建，
    已存在则直接返回。
    """
    async with async_session() as s:
        exists = (await s.execute(select(User).where(User.username == settings.init_admin_username))).scalar_one_or_none()
        if exists:
            return
        s.add(User(
            username=settings.init_admin_username,
            hashed_password=hash_password(settings.init_admin_password),
            display_name="Administrator",
            role="admin",
        ))
        await s.commit()
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_init_admin.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/security/init_admin.py backend/tests/test_init_admin.py
git commit -m "feat(auth): idempotent admin bootstrap"
```

---

### Task 11: auth 路由（/login /refresh /user-info）

**Files:**
- Create: `backend/app/schemas/auth.py`、`backend/app/api/v2/auth.py`
- Modify: `backend/app/main.py`（挂 router + startup 初始化 admin）
- Test: `backend/tests/test_auth_api.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_auth_api.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.security.init_admin import ensure_admin
from app.config import settings

@pytest.fixture(scope="module", autouse=True)
async def _admin():
    """模块级 fixture：确保测试前管理员账号已初始化。"""
    await ensure_admin()

@pytest.mark.asyncio
async def test_login_success_and_userinfo():
    """测试正确账密登录成功，并能用 access token 获取用户信息。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v2/auth/login", json={"username": settings.init_admin_username, "password": settings.init_admin_password})
        body = r.json()
        assert r.status_code == 200
        assert body["code"] == 0
        token = body["data"]["access_token"]
        assert body["data"]["refresh_token"]
        assert body["data"]["user"]["username"] == settings.init_admin_username
        # user-info
        r2 = await c.get("/api/v2/auth/user-info", headers={"Authorization": f"Bearer {token}"})
        assert r2.json()["code"] == 0

@pytest.mark.asyncio
async def test_login_wrong_password():
    """测试错误密码登录返回 LOGIN_FAILED(40103)。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v2/auth/login", json={"username": settings.init_admin_username, "password": "wrong"})
        assert r.json()["code"] == 40103

@pytest.mark.asyncio
async def test_refresh_flow():
    """测试用 refresh token 换取新的 access token。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        login = await c.post("/api/v2/auth/login", json={"username": settings.init_admin_username, "password": settings.init_admin_password})
        rt = login.json()["data"]["refresh_token"]
        r = await c.post("/api/v2/auth/refresh", json={"refresh_token": rt})
        assert r.json()["code"] == 0
        assert r.json()["data"]["access_token"]

@pytest.mark.asyncio
async def test_userinfo_without_token():
    """测试未携带 token 访问 user-info 返回 UNAUTHORIZED(40101)。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/v2/auth/user-info")
        assert r.json()["code"] == 40101
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_auth_api.py -v`
Expected: FAIL（无路由）

- [ ] **Step 3: 实现 `backend/app/schemas/auth.py`**

```python
"""认证相关 schema 模块。

定义登录、刷新、用户信息等请求/响应数据模型。
"""
from pydantic import BaseModel


class LoginParams(BaseModel):
    """登录请求参数。

    Attributes:
        username: 用户名。
        password: 明文密码。
    """

    username: str
    password: str


class UserInfo(BaseModel):
    """用户信息（用于响应）。

    Attributes:
        id: 用户 id（字符串形式 UUID）。
        username: 用户名。
        display_name: 显示名，可空。
        role: 角色。
    """

    id: str
    username: str
    display_name: str | None = None
    role: str


class LoginResult(BaseModel):
    """登录成功响应载荷。

    Attributes:
        access_token: 访问令牌。
        refresh_token: 刷新令牌。
        expires_in: access token 有效期（秒）。
        user: 用户信息。
    """

    access_token: str
    refresh_token: str
    expires_in: int
    user: UserInfo


class RefreshParams(BaseModel):
    """刷新 token 请求参数。

    Attributes:
        refresh_token: 刷新令牌。
    """

    refresh_token: str


class RefreshResult(BaseModel):
    """刷新 token 响应载荷。

    Attributes:
        access_token: 新签发的访问令牌。
        expires_in: access token 有效期（秒）。
    """

    access_token: str
    expires_in: int
```

- [ ] **Step 4: 实现 `backend/app/api/v2/auth.py`**

```python
"""认证路由模块。

提供登录、刷新 token、获取当前用户信息等接口。
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import _claims_from_header, get_current_user
from app.api.response import ok
from app.db.session import get_db
from app.models.user import User
from app.security.password import verify_password
from app.security.jwt import create_access_token, create_refresh_token
from app.schemas.auth import LoginParams, LoginResult, RefreshParams, RefreshResult, UserInfo
from app.exceptions import BizException, ErrorCode
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(params: LoginParams, db: AsyncSession = Depends(get_db)):
    """用户登录。

    按用户名查询用户并校验密码，成功后签发 access/refresh token；
    用户不存在或密码错误均抛 LOGIN_FAILED。
    """
    user = (await db.execute(select(User).where(User.username == params.username))).scalar_one_or_none()
    if not user or not verify_password(params.password, user.hashed_password):
        raise BizException(ErrorCode.LOGIN_FAILED, "用户名或密码错误")
    return ok(LoginResult(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.jwt_access_expire,
        user=UserInfo(id=str(user.id), username=user.username, display_name=user.display_name, role=user.role),
    ).model_dump())


@router.post("/refresh")
async def refresh(params: RefreshParams):
    """用 refresh token 换取新的 access token。

    校验 refresh token 有效性与类型后，按其 sub(user_id) 重新签发 access token。
    """
    claims = _claims_from_header("Bearer " + params.refresh_token, expect_typ="refresh")
    return ok(RefreshResult(access_token=create_access_token(claims["sub"]), expires_in=settings.jwt_access_expire).model_dump())


@router.get("/user-info")
async def user_info(me: User = Depends(get_current_user)):
    """获取当前登录用户信息。"""
    return ok(UserInfo(id=str(me.id), username=me.username, display_name=me.display_name, role=me.role).model_dump())
```

- [ ] **Step 5: 修改 `backend/app/main.py`（挂路由 + startup）**

```python
"""FastAPI 应用入口模块。

负责创建应用、注册中间件与路由、配置异常处理器与生命周期。
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.exceptions import BizException
from app.security.init_admin import ensure_admin
from app.api.v2 import auth, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时确保初始管理员存在，yield 后执行关闭逻辑。"""
    await ensure_admin()         # 启动初始化 admin
    yield


app = FastAPI(title="EasyRAG API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.exception_handler(BizException)
async def biz_exception_handler(request: Request, exc: BizException):
    """全局业务异常处理器。

    将 BizException 转换为 HTTP 200 + 业务错误码的 ApiResponse 结构。
    """
    return JSONResponse(status_code=200, content={"code": exc.code, "message": exc.message, "data": None})


app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(health.router)   # /health 无前缀


@app.get("/")
def root():
    """根路径健康探针，返回服务名与状态。"""
    return {"code": 0, "message": "success", "data": {"service": "easyrag", "status": "ok"}}
```

- [ ] **Step 6: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_auth_api.py -v`
Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/api/v2/auth.py backend/app/main.py backend/tests/test_auth_api.py
git commit -m "feat(auth): /login /refresh /user-info routes + cors + lifespan admin init"
```

---

### Task 12: 健康检查 /health

**Files:**
- Create: `backend/app/api/v2/health.py`
- Test: `backend/tests/test_health.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_health.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_health_ok():
    """测试 /health 接口返回数据库连通正常的健康状态。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/health")
        body = r.json()
        assert r.status_code == 200
        assert body["code"] == 0
        assert body["data"]["db"] == "ok"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: FAIL（Task 11 已 include health.router 但模块未创建 → ImportError）

- [ ] **Step 3: 实现 `backend/app/api/v2/health.py`**

```python
"""健康检查路由模块。"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.response import ok
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """健康检查接口。

    执行 ``SELECT 1`` 探测数据库连通性，正常返回 status=ok，异常返回 degraded。
    """
    try:
        (await db.execute(text("SELECT 1"))).scalar()
        return ok({"status": "ok", "db": "ok"})
    except Exception as e:
        return ok({"status": "degraded", "db": str(e)})
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v2/health.py backend/tests/test_health.py
git commit -m "feat(health): /health endpoint with db check"
```

---

### Task 13: structlog 结构化日志 + request_id 中间件

**Files:**
- Create: `backend/app/logging.py`
- Modify: `backend/app/main.py`（注册中间件 + setup_logging）
- Test: `backend/tests/test_logging.py`

- [ ] **Step 1: 写失败测试 `backend/tests/test_logging.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_response_has_request_id():
    """测试响应头自动携带 x-request-id。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/health")
        assert "x-request-id" in {k.lower() for k in r.headers}

@pytest.mark.asyncio
async def test_request_id_echoed_when_provided():
    """测试请求携带 X-Request-ID 时响应原样回写该 id。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/health", headers={"X-Request-ID": "abc-123"})
        assert r.headers["x-request-id"] == "abc-123"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && pytest tests/test_logging.py -v`
Expected: FAIL（无中间件，响应无 x-request-id）

- [ ] **Step 3: 实现 `backend/app/logging.py`**

```python
"""日志配置模块。

基于 structlog 配置结构化 JSON 日志，并提供请求 id 生成工具。
"""
import logging, uuid
import structlog
from app.config import settings


def setup_logging() -> None:
    """初始化全局日志配置。

    同步配置标准 logging 等级，并为 structlog 启用 JSON 渲染、时间戳、
    日志等级以及 contextvars 合并等处理器。
    """
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level.upper(), logging.INFO)),
        cache_logger_on_first_use=True,
    )


def new_request_id() -> str:
    """生成一个新的请求 id（uuid4 的 hex 字符串）。"""
    return uuid.uuid4().hex
```

- [ ] **Step 4: 修改 `backend/app/main.py` 注册中间件**

在 `app/main.py` 顶部 import 之后、`app` 定义之前添加：

```python
import structlog
from app.logging import setup_logging, new_request_id

setup_logging()
_log = structlog.get_logger()
```

在 `app` 创建后、路由挂载前添加中间件：

```python
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """请求 id 中间件。

    从 ``X-Request-ID`` 头读取或生成新的请求 id，绑定到 structlog contextvars，
    并在响应头回写该 id，便于全链路追踪。
    """
    rid = request.headers.get("X-Request-ID") or new_request_id()
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=rid, path=request.url.path)
    _log.info("request.start")
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    _log.info("request.end", status_code=response.status_code)
    return response
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `cd backend && pytest tests/test_logging.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/logging.py backend/app/main.py backend/tests/test_logging.py
git commit -m "feat(logging): structlog json + request_id middleware"
```

---

### Task 14: 端到端冒烟（全量测试 + docker 启动验证）

**Files:**
- Modify: `backend/tests/conftest.py`（补 admin fixture 自动初始化）
- 无新增测试，运行全量

- [ ] **Step 1: 补 conftest 自动初始化 admin（保证测试库有登录账号）**

修改 `backend/tests/conftest.py`，在末尾追加：

```python
import asyncio
import pytest


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_admin():
    """session 级 fixture：测试开始前确保管理员账号已初始化。"""
    from app.security.init_admin import ensure_admin
    asyncio.get_event_loop().run_until_complete(ensure_admin())
    yield
```

- [ ] **Step 2: 运行全量单元/集成测试**

Run: `cd backend && pytest -v`
Expected: 全绿（test_config/test_response/test_password/test_jwt/test_deps/test_init_admin/test_auth_api/test_health/test_logging/test_db_session/test_user_model 全 passed）。

- [ ] **Step 3: Docker 全栈启动验证**

Run:
```bash
cd deploy && docker compose up -d --build
sleep 10
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/api/v2/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}'
```
Expected:
- `/health` 返回 `{"code":0,...,"data":{"status":"ok","db":"ok"}}`
- `/login` 返回含 `access_token`、`refresh_token`、`user.username=="admin"` 的响应。

- [ ] **Step 4: 用 token 验证 user-info**

Run:
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v2/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")
curl -s http://localhost:8000/api/v2/auth/user-info -H "Authorization: Bearer $TOKEN"
```
Expected: `{"code":0,...,"data":{"username":"admin","role":"admin",...}}`

- [ ] **Step 5: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: e2e smoke for phase1 infrastructure (auth + health + docker)"
```

---

## Phase1 基础设施 完成标志

执行完本计划后，具备：
- ✅ `backend/` 工程，`pip install -e ".[dev]"` 可装，`pytest` 全绿
- ✅ Docker Compose（pgvector + redis + backend）一键起
- ✅ `/api/v2/auth/login`、`/refresh`、`/user-info`、`/health` 可用，统一 `{code,message,data}`
- ✅ 启动自动初始化 admin（默认 `admin/admin123`）
- ✅ JWT 认证 + 刷新、CORS、structlog 日志、request_id 中间件
- ✅ Alembic 迁移就绪（users 表），后续模块直接 `alembic revision --autogenerate`

**下一步**：进入 Plan 2（settings + provider + langchain_factory）—— 让 settings 页可配模型，为 chat/agent/workflow 提供 LLM 能力。

---

*— 计划结束 —*
