"""场景接口测试。"""
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_list_scenes_unauthorized(client: AsyncClient):
    """测试未认证访问场景列表。"""
    response = await client.get("/api/v2/scenes")
    # 业务异常返回 HTTP 200 + 错误码
    assert response.status_code == 200
    data = response.json()
    # 错误码应该在 40100-40199 范围（认证错误）
    assert data["code"] >= 40100 and data["code"] < 40200
    assert "message" in data


@pytest.mark.asyncio
async def test_list_scenes_authorized_with_mock(client: AsyncClient, auth_headers: dict, mock_scenes: list):
    """测试已认证访问场景列表（使用 mock 数据）。"""
    # 创建模拟的数据库会话
    mock_session = AsyncMock()

    # 模拟场景查询结果
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_scenes
    mock_session.execute.return_value = mock_result

    # 创建模拟的 async_session 上下文管理器
    class MockAsyncSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            pass

    # 使用 patch 来替换 async_session
    with patch('app.api.v2.scenes.async_session', return_value=MockAsyncSessionContext()):
        response = await client.get("/api/v2/scenes", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data
        assert isinstance(data["data"], list)

        # 验证数据格式
        if len(data["data"]) > 0:
            scene = data["data"][0]
            assert "id" in scene
            assert "name" in scene
            assert "desc" in scene
            # 验证字段类型
            assert isinstance(scene["id"], str)
            assert isinstance(scene["name"], str)
            assert isinstance(scene["desc"], str)


@pytest.mark.asyncio
async def test_list_scenes_response_format_with_mock(client: AsyncClient, auth_headers: dict, mock_scenes: list):
    """测试场景列表响应格式正确（使用 mock 数据）。"""
    # 创建模拟的数据库会话
    mock_session = AsyncMock()

    # 模拟场景查询结果
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_scenes
    mock_session.execute.return_value = mock_result

    # 创建模拟的 async_session 上下文管理器
    class MockAsyncSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            pass

    # 使用 patch 来替换 async_session
    with patch('app.api.v2.scenes.async_session', return_value=MockAsyncSessionContext()):
        response = await client.get("/api/v2/scenes", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # 验证响应格式
        assert "code" in data
        assert "message" in data
        assert "data" in data

        # 验证成功状态
        assert data["code"] == 0
        assert data["message"] == "success"

        # 验证 data 是列表
        assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_list_scenes_returns_mock_scenes(client: AsyncClient, auth_headers: dict, mock_scenes: list):
    """测试场景列表返回模拟的场景数据。"""
    # 创建模拟的数据库会话
    mock_session = AsyncMock()

    # 模拟场景查询结果
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_scenes
    mock_session.execute.return_value = mock_result

    # 创建模拟的 async_session 上下文管理器
    class MockAsyncSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            pass

    # 使用 patch 来替换 async_session
    with patch('app.api.v2.scenes.async_session', return_value=MockAsyncSessionContext()):
        response = await client.get("/api/v2/scenes", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

        # 应该返回 5 个模拟场景
        assert len(data["data"]) == 5

        # 验证每个场景的字段完整性
        for scene in data["data"]:
            assert "id" in scene
            assert "name" in scene
            assert "desc" in scene
            # id 应该是场景的 code
            assert isinstance(scene["id"], str)
            assert len(scene["id"]) > 0

        # 验证第一个场景的数据
        first_scene = data["data"][0]
        assert first_scene["id"] == "general"
        assert first_scene["name"] == "通用问答"
        assert first_scene["desc"] == "适用于一般性问题和答案"