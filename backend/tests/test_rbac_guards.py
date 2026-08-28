"""验证共享资源 CUD 路由使用 require_roles 守卫。"""
import inspect
from unittest.mock import MagicMock

import pytest

from app.exceptions import BizException, ErrorCode


def _get_guard(route_fn):
    """从路由函数签名中提取 me 参数的守卫函数。"""
    sig = inspect.signature(route_fn)
    dep = sig.parameters["me"].default
    return dep.dependency


@pytest.mark.asyncio
async def test_tools_create_guard_denies_viewer():
    from app.api.v2 import tools
    guard = _get_guard(tools.create)
    viewer = MagicMock()
    viewer.role = "viewer"
    with pytest.raises(BizException) as exc:
        await guard(me=viewer)
    assert exc.value.code == ErrorCode.FORBIDDEN


@pytest.mark.asyncio
async def test_tools_create_guard_allows_admin():
    from app.api.v2 import tools
    guard = _get_guard(tools.create)
    admin = MagicMock()
    admin.role = "admin"
    result = await guard(me=admin)
    assert result is admin


@pytest.mark.asyncio
async def test_tools_update_guard_denies_editor():
    from app.api.v2 import tools
    guard = _get_guard(tools.update)
    editor = MagicMock()
    editor.role = "editor"
    with pytest.raises(BizException):
        await guard(me=editor)


@pytest.mark.asyncio
async def test_tools_delete_guard_denies_viewer():
    from app.api.v2 import tools
    guard = _get_guard(tools.delete)
    viewer = MagicMock()
    viewer.role = "viewer"
    with pytest.raises(BizException):
        await guard(me=viewer)


@pytest.mark.asyncio
async def test_mcps_create_guard_denies_viewer():
    from app.api.v2 import mcps
    guard = _get_guard(mcps.create)
    viewer = MagicMock()
    viewer.role = "viewer"
    with pytest.raises(BizException):
        await guard(me=viewer)


@pytest.mark.asyncio
async def test_skills_create_guard_denies_viewer():
    from app.api.v2 import skills
    guard = _get_guard(skills.create)
    viewer = MagicMock()
    viewer.role = "viewer"
    with pytest.raises(BizException):
        await guard(me=viewer)


@pytest.mark.asyncio
async def test_agents_create_guard_denies_viewer():
    from app.api.v2 import agents
    guard = _get_guard(agents.create)
    viewer = MagicMock()
    viewer.role = "viewer"
    with pytest.raises(BizException):
        await guard(me=viewer)


@pytest.mark.asyncio
async def test_settings_create_model_guard_denies_viewer():
    from app.api.v2 import settings as settings_api
    guard = _get_guard(settings_api.create_or_update_model)
    viewer = MagicMock()
    viewer.role = "viewer"
    with pytest.raises(BizException):
        await guard(me=viewer)


@pytest.mark.asyncio
async def test_settings_delete_model_guard_denies_editor():
    from app.api.v2 import settings as settings_api
    guard = _get_guard(settings_api.delete_model)
    editor = MagicMock()
    editor.role = "editor"
    with pytest.raises(BizException):
        await guard(me=editor)


@pytest.mark.asyncio
async def test_tools_list_still_accessible_to_all():
    """list 操作应保持 get_current_user，任何角色可访问。"""
    from app.api.v2 import tools
    sig = inspect.signature(tools.list_)
    dep = sig.parameters["me"].default
    # get_current_user 不含 require_roles 守卫
    assert dep.dependency.__name__ == "get_current_user"
