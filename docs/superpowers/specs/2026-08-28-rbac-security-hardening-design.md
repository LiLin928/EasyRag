# 子项目 A：RBAC + 安全加固 — 设计文档

> **日期**：2026-08-28
> **模块**：角色权限控制 / 用户管理 / 审计日志 / 速率限制 / 文件校验
> **状态**：已批准
> **关联文档**：
> - `docs/backend-plans/后端设计方案-Phase2-3详细设计.md` §10.1（多用户与 RBAC）、§10.5（安全加固）
> - `docs/superpowers/specs/2026-08-28-phase3-async-scalability-design.md`（Phase 3 子项目 C）

---

## 一、背景与范围

### 1.1 当前状态

- **认证**：JWT access(2h)+refresh(7d) 全链路可用，所有 API 路由已挂 `get_current_user`。
- **角色字段**：`User.role` 字段已存在（VARCHAR(20)，默认 "admin"），但从未用于权限控制。
- **数据隔离**：KB/文档/工作流/对话已有 `user_id` 并在查询中过滤；但 tools/mcps/skills/agents/settings 无 `user_id`，全局共享，无权限分级。
- **安全**：无速率限制、无审计日志、无文件 magic number 校验、无密码复杂度策略。

### 1.2 本文档范围

- **RBAC 角色权限** — admin/editor/viewer 三角色，`require_roles` 依赖工厂
- **用户管理 API** — admin 可 CRUD 用户
- **审计日志** — 关键操作落库 + 查询
- **速率限制** — slowapi 中间件（登录/对话/上传）
- **文件校验** — 上传 magic number 校验
- **密码策略** — 最少 8 位，含字母+数字

### 1.3 不包含

- HTTPS（Nginx 运维层）
- 病毒扫描（可选，后续迭代）
- 项目级资源共享 + project_members 表（后续迭代）

---

## 二、角色体系

| 角色 | 权限说明 |
|------|----------|
| `admin` | 全部操作 + 用户管理 + 系统配置（settings/tools/mcps/skills/agents CUD） |
| `editor` | 创建/编辑/删除自有资源（KB/文档/工作流/对话），只读共享资源，可对话/检索/执行 |
| `viewer` | 全只读 + 可对话/检索/执行，不能创建/修改/删除任何资源 |

现有 `User.role` 字段不变（VARCHAR(20)），值域从 `"admin"` 扩展为 `"admin" / "editor" / "viewer"`。

### 权限矩阵

| 操作类别 | admin | editor | viewer |
|----------|-------|--------|--------|
| 用户管理 CRUD | 允许 | 禁止 | 禁止 |
| 系统配置 CUD（settings/tools/mcps/skills/agents） | 允许 | 禁止 | 禁止 |
| 共享资源读取 | 允许 | 允许 | 允许 |
| 自有资源 CRUD（KB/文档/工作流/对话） | 允许 | 允许（仅自己的） | 只读（仅自己的） |
| 对话/检索/执行 | 允许 | 允许 | 允许 |

---

## 三、require_roles 依赖工厂

```python
# app/api/deps.py

def require_roles(*roles: str):
    """角色守卫依赖工厂：校验当前用户角色是否在允许列表内。"""
    async def _check(me: User = Depends(get_current_user)):
        if me.role not in roles:
            raise BizException(ErrorCode.FORBIDDEN, "无权限执行此操作")
        return me
    return _check
```

使用方式：

```python
@router.post("/users")
async def create_user(body: UserCreate, me=Depends(require_roles("admin"))):
    ...
```

---

## 四、用户管理 API

### 4.1 端点

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /users | admin | 列出用户（分页） |
| POST | /users | admin | 创建用户 |
| PATCH | /users/{uid} | admin 或本人 | 更新用户（admin 可改 role/is_active，本人可改 display_name/password） |
| DELETE | /users/{uid} | admin | 删除用户（不能删自己 / 最后一个 admin） |

### 4.2 Schema

```python
class UserCreate(BaseModel):
    username: str
    password: str  # >= 8 chars, letters + digits
    display_name: str | None = None
    email: str | None = None
    role: str = "viewer"  # admin / editor / viewer

class UserUpdate(BaseModel):
    display_name: str | None = None
    password: str | None = None
    email: str | None = None
    role: str | None = None       # admin only
    is_active: bool | None = None  # admin only

class UserOut(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    email: str | None = None
    role: str
    is_active: bool
    created_at: str
```

### 4.3 安全约束

- 创建用户时校验密码复杂度（`validate_password`）
- 不能删除自己
- 不能删除最后一个 admin（防止锁死）
- 不能禁用自己
- 非 admin 修改 `role` / `is_active` 字段时忽略或拒绝

---

## 五、审计日志

### 5.1 数据模型

```python
class AuditLog(Base, UUIDPk, TimestampMixin):
    __tablename__ = "audit_logs"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    username: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(50))
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
```

### 5.2 写入接口

```python
# app/services/audit_service.py
async def log_audit(user_id, username, action, resource_type, resource_id=None, detail=None, ip=None):
    """写入一条审计日志。"""
    ...
```

调用点：用户管理 CUD、系统配置 CUD、文档上传/删除、对话。

### 5.3 查询端点

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /audit-logs | admin | 分页查询审计日志（可按 user/action/resource_type 过滤） |

---

## 六、速率限制

使用 `slowapi` 库，基于 Redis 存储（复用现有 Redis）。

| 端点 | 限制 | 维度 |
|------|------|------|
| POST /auth/login | 5/minute | IP |
| POST /chat | 20/minute | user |
| POST /documents/upload | 10/minute | user |

```python
# app/core/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)
```

---

## 七、文件 magic number 校验

```python
# app/core/file_validator.py

MAGIC_SIGNATURES = {
    "%PDF": "application/pdf",
    "PK\x03\x04": "application/zip",  # docx/xlsx
}

def validate_file_magic(content: bytes, expected_types: set[str]) -> str:
    """检查文件头 magic number，返回检测到的 MIME 类型。"""
    ...
```

集成到 `documents.py` 上传端点，拒绝伪装扩展名的文件。

---

## 八、密码策略

```python
# app/security/password.py

def validate_password(plain: str) -> None:
    """校验密码复杂度：>= 8 字符，含字母+数字。不通过抛 BizException。"""
    if len(plain) < 8:
        raise BizException(ErrorCode.PARAM_ERROR, "密码至少 8 位")
    if not any(c.isalpha() for c in plain) or not any(c.isdigit() for c in plain):
        raise BizException(ErrorCode.PARAM_ERROR, "密码需包含字母和数字")
```

---

## 九、测试策略

| 层级 | 测试内容 | 策略 |
|------|---------|------|
| require_roles 单元测试 | 角色 allowed/denied | mock User，验证 BizException(FORBIDDEN) |
| 用户管理 API 测试 | CRUD + 安全约束（删自己/最后 admin） | mock DB session |
| 审计日志测试 | 写入 + 查询 | mock DB session |
| 速率限制测试 | 超限返回 429 | mock slowapi |
| 文件校验测试 | magic number 正确/错误 | 纯函数测试 |
| 密码策略测试 | 合法/非法密码 | 纯函数测试 |

---

## 十、文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `api/deps.py` | 修改 | 增加 `require_roles` 依赖工厂 |
| `security/password.py` | 修改 | 增加 `validate_password` |
| `schemas/user.py` | 新增 | UserCreate / UserUpdate / UserOut |
| `models/audit_log.py` | 新增 | 审计日志 ORM |
| `services/user_service.py` | 新增 | 用户 CRUD 业务逻辑 |
| `services/audit_service.py` | 新增 | 审计日志写入/查询 |
| `api/v2/users.py` | 新增 | 用户管理路由 |
| `api/v2/audit.py` | 新增 | 审计日志查询路由 |
| `core/rate_limit.py` | 新增 | slowapi 限流配置 |
| `core/file_validator.py` | 新增 | magic number 校验 |
| `app/main.py` | 修改 | 注册 users/audit 路由 + slowapi 中间件 |
| `pyproject.toml` | 修改 | 增加 slowapi 依赖 |
| 现有 API 路由（tools/mcps/skills/agents/settings） | 修改 | CUD 操作加 require_roles("admin") |
| `tests/test_*.py` | 新增 | 各模块 TDD 测试 |

---

## 十一、约束

- **前端契约不变** — `/auth/login` 仍返回 `roles: [role]`，`/auth/user-info` 同理
- **现有路由签名不变** — 只在依赖参数中替换或叠加 `require_roles`
- **role 值域** — `"admin"` / `"editor"` / `"viewer"`，init_admin 仍创建 `role="admin"`
- **审计日志非阻塞** — `log_audit` 内部 catch 异常，不影响主流程

---

## 文档版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| V1.0 | 2026-08-28 | 子项目 A 设计方案：RBAC + 安全加固 |

---

*— 文档结束 —*
