# 子项目 A：RBAC + 安全加固 — 实施计划

> **目标**：实现角色权限控制、用户管理、审计日志、速率限制、文件校验
> **技术栈**：FastAPI + SQLAlchemy 2.0 async + slowapi + Redis
> **关联设计**：`docs/superpowers/specs/2026-08-28-rbac-security-hardening-design.md`
> **TDD 模式**：每个 Task 先写失败测试 → 实现 → 测试通过 → commit

---

## Task 1: require_roles 依赖工厂 + 密码策略

**Files:**
- Modify: `app/api/deps.py` — 增加 `require_roles(*roles)` 工厂函数
- Modify: `app/security/password.py` — 增加 `validate_password(plain)`
- Test: `tests/test_require_roles.py`

### Step 1: Write failing test

```python
# tests/test_require_roles.py
"""require_roles 依赖工厂 + 密码策略测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.deps import require_roles
from app.exceptions import BizException, ErrorCode
from app.security.password import validate_password


def test_validate_password_accepts_strong():
    validate_password("abc12345")  # should not raise


def test_validate_password_rejects_short():
    with pytest.raises(BizException) as exc:
        validate_password("ab1")
    assert exc.value.code == ErrorCode.PARAM_ERROR


def test_validate_password_rejects_no_digits():
    with pytest.raises(BizException):
        validate_password("abcdefgh")


def test_validate_password_rejects_no_letters():
    with pytest.raises(BizException):
        validate_password("12345678")


@pytest.mark.asyncio
async def test_require_roles_allows():
    """admin 用户通过 require_roles("admin") 守卫。"""
    me = MagicMock()
    me.role = "admin"
    guard = require_roles("admin")
    result = await guard(me=me)
    assert result is me


@pytest.mark.asyncio
async def test_require_roles_denies():
    """viewer 用户被 require_roles("admin") 拒绝，抛 FORBIDDEN。"""
    me = MagicMock()
    me.role = "viewer"
    guard = require_roles("admin")
    with pytest.raises(BizException) as exc:
        await guard(me=me)
    assert exc.value.code == ErrorCode.FORBIDDEN
```

### Step 2: Run test — expect FAIL (functions not defined)

### Step 3: Implement

```python
# app/api/deps.py — 追加

def require_roles(*roles: str):
    """角色守卫依赖工厂：校验当前用户角色是否在允许列表内。"""
    async def _check(me: User = Depends(get_current_user)):
        if me.role not in roles:
            raise BizException(ErrorCode.FORBIDDEN, "无权限执行此操作")
        return me
    return _check
```

```python
# app/security/password.py — 追加
from app.exceptions import BizException, ErrorCode

def validate_password(plain: str) -> None:
    """校验密码复杂度：>= 8 字符，含字母+数字。"""
    if len(plain) < 8:
        raise BizException(ErrorCode.PARAM_ERROR, "密码至少 8 位")
    if not any(c.isalpha() for c in plain) or not any(c.isdigit() for c in plain):
        raise BizException(ErrorCode.PARAM_ERROR, "密码需包含字母和数字")
```

### Step 4: Run test — expect PASS
### Step 5: Commit

---

## Task 2: 用户管理 API

**Files:**
- New: `app/schemas/user.py` — UserCreate / UserUpdate / UserOut
- New: `app/services/user_service.py` — CRUD 逻辑 + 安全约束
- New: `app/api/v2/users.py` — 路由
- Modify: `app/main.py` — 注册路由
- Test: `tests/test_users_api.py`

### Step 1: Write failing test

```python
# tests/test_users_api.py
"""用户管理 API 测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.exceptions import BizException, ErrorCode


@pytest.mark.asyncio
async def test_create_user(monkeypatch):
    """admin 创建新用户。"""
    from app.api.v2.users import create_user
    from app.schemas.user import UserCreate

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=None)
    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    fake_session.commit = AsyncMock()
    fake_session.refresh = AsyncMock()
    fake_cm = AsyncMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.v2.users.async_session", lambda: fake_cm)

    me = MagicMock()
    me.id = "admin-1"
    me.role = "admin"

    body = UserCreate(username="newuser", password="abc12345", role="viewer")
    result = await create_user(body, me=me)
    assert "newuser" in str(result)


@pytest.mark.asyncio
async def test_create_duplicate_user(monkeypatch):
    """用户名已存在时报错。"""
    from app.api.v2.users import create_user
    from app.schemas.user import UserCreate

    existing = MagicMock()
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=existing)
    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    fake_cm = AsyncMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.api.v2.users.async_session", lambda: fake_cm)

    me = MagicMock()
    me.role = "admin"

    body = UserCreate(username="admin", password="abc12345")
    with pytest.raises(BizException) as exc:
        await create_user(body, me=me)
    assert exc.value.code == ErrorCode.PARAM_ERROR


@pytest.mark.asyncio
async def test_delete_self_forbidden(monkeypatch):
    """不能删除自己。"""
    from app.api.v2.users import delete_user

    me = MagicMock()
    me.id = "u-1"
    me.role = "admin"

    with pytest.raises(BizException) as exc:
        await delete_user("u-1", me=me)
    assert exc.value.code == ErrorCode.FORBIDDEN
```

### Step 2: Run test — expect FAIL
### Step 3: Implement (schemas + service + route)
### Step 4: Run test — expect PASS
### Step 5: Commit

---

## Task 3: 权限守卫应用到现有路由

**Files:**
- Modify: `app/api/v2/tools.py` — CUD 操作改用 `require_roles("admin")`
- Modify: `app/api/v2/mcps.py` — 同上
- Modify: `app/api/v2/skills.py` — 同上
- Modify: `app/api/v2/agents.py` — CUD 操作改用
- Modify: `app/api/v2/settings.py` — model/scene CUD 改用
- Test: `tests/test_rbac_guards.py`

### Step 1: Write failing test

```python
# tests/test_rbac_guards.py
"""验证共享资源 CUD 路由使用 require_roles 守卫。"""
import inspect
from app.api.v2 import tools, mcps, skills, agents, settings as settings_api


def test_tools_create_requires_admin():
    sig = inspect.signature(tools.create)
    dep = sig.parameters["me"].default
    assert "admin" in str(dep)


def test_tools_delete_requires_admin():
    sig = inspect.signature(tools.delete)
    dep = sig.parameters["me"].default
    assert "admin" in str(dep)


def test_mcps_create_requires_admin():
    sig = inspect.signature(mcps.create)
    assert "admin" in str(sig.parameters["me"].default)


def test_skills_create_requires_admin():
    sig = inspect.signature(skills.create)
    assert "admin" in str(sig.parameters["me"].default)


def test_agents_create_requires_admin():
    sig = inspect.signature(agents.create)
    assert "admin" in str(sig.parameters["me"].default)


def test_settings_create_model_requires_admin():
    sig = inspect.signature(settings_api.create_or_update_model)
    assert "admin" in str(sig.parameters["me"].default)
```

### Step 2: Run test — expect FAIL (routes still use get_current_user)
### Step 3: Implement (swap dependencies in each route)
### Step 4: Run test — expect PASS
### Step 5: Commit

---

## Task 4: 审计日志

**Files:**
- New: `app/models/audit_log.py` — AuditLog ORM
- New: `app/services/audit_service.py` — log_audit + query
- New: `app/api/v2/audit.py` — 查询路由
- Modify: `app/main.py` — 注册路由
- Test: `tests/test_audit_log.py`

### Step 1: Write failing test

```python
# tests/test_audit_log.py
"""审计日志写入 + 查询测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_log_audit_writes(monkeypatch):
    """log_audit 写入一条记录。"""
    from app.services.audit_service import log_audit

    fake_session = AsyncMock()
    fake_session.add = MagicMock()
    fake_session.commit = AsyncMock()
    fake_cm = AsyncMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.services.audit_service.async_session", lambda: fake_cm)

    await log_audit("u-1", "admin", "create", "user", "u-2", {"role": "viewer"})
    fake_session.add.assert_called_once()
    fake_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_log_audit_swallows_exceptions(monkeypatch):
    """log_audit 内部异常不影响主流程。"""
    from app.services.audit_service import log_audit

    fake_cm = AsyncMock()
    fake_cm.__aenter__ = AsyncMock(side_effect=Exception("DB down"))
    fake_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.services.audit_service.async_session", lambda: fake_cm)

    # should not raise
    await log_audit("u-1", "admin", "create", "user")
```

### Step 2: Run test — expect FAIL
### Step 3: Implement
### Step 4: Run test — expect PASS
### Step 5: Commit

---

## Task 5: 速率限制

**Files:**
- New: `app/core/rate_limit.py` — slowapi Limiter 配置
- Modify: `app/main.py` — 注册 slowapi 中间件 + 异常处理
- Modify: `pyproject.toml` — 增加 slowapi 依赖
- Modify: `app/api/v2/auth.py` — login 加 `@limiter.limit("5/minute")`
- Test: `tests/test_rate_limit.py`

### Step 1: Write failing test

```python
# tests/test_rate_limit.py
"""速率限制配置测试。"""


def test_limiter_instance():
    from app.core.rate_limit import limiter
    assert limiter is not None
    assert hasattr(limiter, "limit")


def test_limiter_storage_uri():
    from app.core.rate_limit import limiter
    # limiter should be configured with Redis storage
    assert limiter._storage_uri is not None or limiter._storage is not None
```

### Step 2: Run — expect FAIL (module not found)
### Step 3: Implement

```python
# app/core/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)
```

### Step 4: Run — expect PASS
### Step 5: Commit

---

## Task 6: 文件 magic number 校验

**Files:**
- New: `app/core/file_validator.py` — magic number 检测
- Test: `tests/test_file_validator.py`

### Step 1: Write failing test

```python
# tests/test_file_validator.py
"""文件 magic number 校验测试。"""
import pytest
from app.core.file_validator import detect_file_type, validate_file_magic
from app.exceptions import BizException, ErrorCode


def test_detect_pdf():
    assert detect_file_type(b"%PDF-1.7...") == "application/pdf"


def test_detect_zip():
    assert detect_file_type(b"PK\x03\x04...") == "application/zip"


def test_detect_unknown():
    assert detect_file_type(b"\x00\x01\x02") is None


def test_validate_accepts_pdf():
    validate_file_magic(b"%PDF-1.7", {"application/pdf"})  # should not raise


def test_validate_rejects_mismatch():
    with pytest.raises(BizException) as exc:
        validate_file_magic(b"PK\x03\x04", {"application/pdf"})
    assert exc.value.code == ErrorCode.UNSUPPORTED_FILE
```

### Step 2: Run — expect FAIL
### Step 3: Implement

```python
# app/core/file_validator.py
"""文件 magic number 校验。"""
from app.exceptions import BizException, ErrorCode

MAGIC_SIGNATURES = [
    (b"%PDF", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),   # .docx / .xlsx
    (b"\xd0\xcf\x11\xe0", "application/msword"),  # .doc (OLE)
]


def detect_file_type(content: bytes) -> str | None:
    """根据文件头 magic number 检测 MIME 类型。"""
    for magic, mime in MAGIC_SIGNATURES:
        if content.startswith(magic):
            return mime
    return None


def validate_file_magic(content: bytes, allowed: set[str]) -> None:
    """校验文件 magic number是否在允许列表内。"""
    detected = detect_file_type(content)
    if detected not in allowed:
        raise BizException(ErrorCode.UNSUPPORTED_FILE, f"不支持的文件类型: {detected or '未知'}")
```

### Step 4: Run — expect PASS
### Step 5: Commit

---

## Plan 完成标志

- [ ] require_roles + 密码策略 (Task 1)
- [ ] 用户管理 API (Task 2)
- [ ] 权限守卫应用 (Task 3)
- [ ] 审计日志 (Task 4)
- [ ] 速率限制 (Task 5)
- [ ] 文件 magic number 校验 (Task 6)

---

*— 计划结束 —*
