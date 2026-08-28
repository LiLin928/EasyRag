"""require_roles 依赖工厂 + 密码策略测试。"""
import pytest
from unittest.mock import MagicMock

from app.exceptions import BizException, ErrorCode


def test_validate_password_accepts_strong():
    from app.security.password import validate_password
    validate_password("abc12345")  # should not raise


def test_validate_password_rejects_short():
    from app.security.password import validate_password
    with pytest.raises(BizException) as exc:
        validate_password("ab1")
    assert exc.value.code == ErrorCode.PARAM_ERROR


def test_validate_password_rejects_no_digits():
    from app.security.password import validate_password
    with pytest.raises(BizException):
        validate_password("abcdefgh")


def test_validate_password_rejects_no_letters():
    from app.security.password import validate_password
    with pytest.raises(BizException):
        validate_password("12345678")


@pytest.mark.asyncio
async def test_require_roles_allows():
    """admin 用户通过 require_roles("admin") 守卫。"""
    from app.api.deps import require_roles
    me = MagicMock()
    me.role = "admin"
    guard = require_roles("admin")
    result = await guard(me=me)
    assert result is me


@pytest.mark.asyncio
async def test_require_roles_denies():
    """viewer 用户被 require_roles("admin") 拒绝，抛 FORBIDDEN。"""
    from app.api.deps import require_roles
    me = MagicMock()
    me.role = "viewer"
    guard = require_roles("admin")
    with pytest.raises(BizException) as exc:
        await guard(me=me)
    assert exc.value.code == ErrorCode.FORBIDDEN


@pytest.mark.asyncio
async def test_require_roles_multiple():
    """admin 和 editor 都通过 require_roles("admin", "editor")。"""
    from app.api.deps import require_roles
    for role in ("admin", "editor"):
        me = MagicMock()
        me.role = role
        guard = require_roles("admin", "editor")
        result = await guard(me=me)
        assert result is me
