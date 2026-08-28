"""用户管理 API 测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.exceptions import BizException, ErrorCode


def _fake_session_cm(fake_session):
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=fake_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.mark.asyncio
async def test_create_user(monkeypatch):
    """admin 创建新用户。"""
    from app.api.v2.users import create_user
    from app.schemas.user import UserCreate

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=None)
    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    fake_session.add = MagicMock()
    fake_session.commit = AsyncMock()
    fake_session.refresh = AsyncMock()
    monkeypatch.setattr("app.api.v2.users.async_session", lambda: _fake_session_cm(fake_session))

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
    monkeypatch.setattr("app.api.v2.users.async_session", lambda: _fake_session_cm(fake_session))

    me = MagicMock()
    me.role = "admin"

    body = UserCreate(username="admin", password="abc12345")
    with pytest.raises(BizException) as exc:
        await create_user(body, me=me)
    assert exc.value.code == ErrorCode.PARAM_ERROR


@pytest.mark.asyncio
async def test_create_user_weak_password(monkeypatch):
    """弱密码被拒绝。"""
    from app.api.v2.users import create_user
    from app.schemas.user import UserCreate

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=None)
    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    monkeypatch.setattr("app.api.v2.users.async_session", lambda: _fake_session_cm(fake_session))

    me = MagicMock()
    me.role = "admin"

    body = UserCreate(username="weakuser", password="123")
    with pytest.raises(BizException) as exc:
        await create_user(body, me=me)
    assert exc.value.code == ErrorCode.PARAM_ERROR


@pytest.mark.asyncio
async def test_delete_self_forbidden():
    """不能删除自己。"""
    from app.api.v2.users import delete_user

    me = MagicMock()
    me.id = "u-1"
    me.role = "admin"

    with pytest.raises(BizException) as exc:
        await delete_user("u-1", me=me)
    assert exc.value.code == ErrorCode.FORBIDDEN


@pytest.mark.asyncio
async def test_delete_last_admin_forbidden(monkeypatch):
    """不能删除最后一个 admin。"""
    from app.api.v2.users import delete_user

    fake_admin = MagicMock()
    fake_admin.id = "u-2"
    fake_admin.role = "admin"

    fake_load_result = MagicMock()
    fake_load_result.scalar_one_or_none = MagicMock(return_value=fake_admin)
    fake_count_result = MagicMock()
    fake_count_result.scalar = MagicMock(return_value=1)
    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(side_effect=[fake_load_result, fake_count_result])
    fake_session.delete = AsyncMock()
    fake_session.commit = AsyncMock()
    monkeypatch.setattr("app.api.v2.users.async_session", lambda: _fake_session_cm(fake_session))

    me = MagicMock()
    me.id = "u-1"
    me.role = "admin"

    with pytest.raises(BizException) as exc:
        await delete_user("u-2", me=me)
    assert exc.value.code == ErrorCode.FORBIDDEN


@pytest.mark.asyncio
async def test_list_users(monkeypatch):
    """admin 列出用户。"""
    from app.api.v2.users import list_users

    fake_user = MagicMock()
    fake_user.id = "u-1"
    fake_user.username = "admin"
    fake_user.display_name = "Admin"
    fake_user.email = None
    fake_user.role = "admin"
    fake_user.is_active = True
    fake_user.created_at = MagicMock()
    fake_user.created_at.isoformat = MagicMock(return_value="2026-01-01T00:00:00")

    fake_result = MagicMock()
    fake_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[fake_user])))
    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    monkeypatch.setattr("app.api.v2.users.async_session", lambda: _fake_session_cm(fake_session))

    me = MagicMock()
    me.role = "admin"

    result = await list_users(me=me)
    assert "admin" in str(result)
