"""工具接口测试。"""
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


@pytest.fixture
def mock_tool():
    """创建模拟工具对象。"""
    tool = MagicMock()
    tool.id = uuid.uuid4()
    tool.name = "测试HTTP工具"
    tool.type = "HTTP"
    tool.description = "测试用工具"
    tool.sig = "test_func(arg1: str) -> dict"
    tool.enabled = True
    tool.params = []
    tool.auth = {"mode": "none", "key": ""}
    tool.config = {"url": "https://httpbin.org/get", "method": "GET", "timeout": 30}
    tool.created_at = None
    return tool


@pytest.mark.asyncio
async def test_tool_test_endpoint_unauthorized(client: AsyncClient):
    """测试未认证访问工具测试接口。"""
    response = await client.post(
        "/api/v2/tools/test-id/test",
        json={"args": {"test": "value"}}
    )
    # 业务异常返回 HTTP 200 + 错误码
    assert response.status_code == 200
    data = response.json()
    # 错误码应该在 40100-40199 范围（认证错误）
    assert data["code"] >= 40100 and data["code"] < 40200
    assert "message" in data


@pytest.mark.asyncio
async def test_tool_test_endpoint_http_tool(client: AsyncClient, auth_headers: dict, mock_tool):
    """测试HTTP工具测试接口。"""
    # 创建模拟的数据库会话
    mock_session = AsyncMock()

    # 模拟工具查询结果
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_tool
    mock_session.execute.return_value = mock_result

    # 创建模拟的 async_session 上下文管理器
    class MockAsyncSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            pass

    # 模拟 httpx.AsyncClient
    mock_http_response = MagicMock()
    mock_http_response.status_code = 200
    mock_http_response.json.return_value = {"success": True, "data": "test"}
    mock_http_response.text = '{"success": true}'

    mock_async_client = AsyncMock()
    mock_async_client.__aenter__.return_value.request = AsyncMock(return_value=mock_http_response)

    # 使用 patch 替换依赖
    with patch('app.api.v2.tools.async_session', return_value=MockAsyncSessionContext()), \
         patch('app.core.tools.executor.httpx.AsyncClient', return_value=mock_async_client), \
         patch('app.services.tool_service.async_session', return_value=MockAsyncSessionContext()):
        response = await client.post(
            f"/api/v2/tools/{mock_tool.id}/test",
            json={"args": {"test": "value"}},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data
        assert "success" in data["data"]
        assert "duration" in data["data"]


@pytest.mark.asyncio
async def test_tool_test_endpoint_tool_not_found(client: AsyncClient, auth_headers: dict):
    """测试工具不存在的情况。"""
    # 创建模拟的数据库会话
    mock_session = AsyncMock()

    # 模拟工具查询结果为 None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    # 创建模拟的 async_session 上下文管理器
    class MockAsyncSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            pass

    # 使用 patch 替换依赖
    with patch('app.api.v2.tools.async_session', return_value=MockAsyncSessionContext()), \
         patch('app.services.tool_service.async_session', return_value=MockAsyncSessionContext()):
        response = await client.post(
            "/api/v2/tools/non-existent-id/test",
            json={"args": {"test": "value"}},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # 应该返回错误码（40400+ 表示不存在）
        assert data["code"] >= 40400
        assert "message" in data


@pytest.mark.asyncio
async def test_tool_test_endpoint_disabled_tool(client: AsyncClient, auth_headers: dict):
    """测试工具被禁用的情况。"""
    # 创建被禁用的工具
    disabled_tool = MagicMock()
    disabled_tool.id = uuid.uuid4()
    disabled_tool.name = "禁用工具"
    disabled_tool.type = "HTTP"
    disabled_tool.enabled = False

    # 创建模拟的数据库会话
    mock_session = AsyncMock()

    # 模拟工具查询结果
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = disabled_tool
    mock_session.execute.return_value = mock_result

    # 创建模拟的 async_session 上下文管理器
    class MockAsyncSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            pass

    # 使用 patch 替换依赖
    with patch('app.api.v2.tools.async_session', return_value=MockAsyncSessionContext()), \
         patch('app.services.tool_service.async_session', return_value=MockAsyncSessionContext()):
        response = await client.post(
            f"/api/v2/tools/{disabled_tool.id}/test",
            json={"args": {"test": "value"}},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # 应该返回错误码（40300+ 表示禁止访问）
        assert data["code"] >= 40300
        assert "message" in data


@pytest.mark.asyncio
async def test_tool_test_endpoint_python_tool(client: AsyncClient, auth_headers: dict):
    """测试Python工具测试接口。"""
    # 创建Python工具
    python_tool = MagicMock()
    python_tool.id = uuid.uuid4()
    python_tool.name = "测试Python工具"
    python_tool.type = "Python"
    python_tool.description = "测试Python工具"
    python_tool.enabled = True
    python_tool.config = {"code": "result = args.get('test', 'default')"}

    # 创建模拟的数据库会话
    mock_session = AsyncMock()

    # 模拟工具查询结果
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = python_tool
    mock_session.execute.return_value = mock_result

    # 创建模拟的 async_session 上下文管理器
    class MockAsyncSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            pass

    # 使用 patch 替换依赖
    with patch('app.api.v2.tools.async_session', return_value=MockAsyncSessionContext()), \
         patch('app.services.tool_service.async_session', return_value=MockAsyncSessionContext()):
        response = await client.post(
            f"/api/v2/tools/{python_tool.id}/test",
            json={"args": {"test": "value"}},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "data" in data
        assert "success" in data["data"]


@pytest.mark.asyncio
async def test_tool_test_endpoint_builtin_tool(client: AsyncClient, auth_headers: dict):
    """测试内置工具测试接口。"""
    # 创建内置工具
    builtin_tool = MagicMock()
    builtin_tool.id = uuid.uuid4()
    builtin_tool.name = "测试内置工具"
    builtin_tool.type = "内置"
    builtin_tool.enabled = True

    # 创建模拟的数据库会话
    mock_session = AsyncMock()

    # 模拟工具查询结果
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = builtin_tool
    mock_session.execute.return_value = mock_result

    # 创建模拟的 async_session 上下文管理器
    class MockAsyncSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            pass

    # 使用 patch 替换依赖
    with patch('app.api.v2.tools.async_session', return_value=MockAsyncSessionContext()), \
         patch('app.services.tool_service.async_session', return_value=MockAsyncSessionContext()):
        response = await client.post(
            f"/api/v2/tools/{builtin_tool.id}/test",
            json={"args": {"test": "value"}},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # 内置工具未注册时会返回错误，但接口调用成功
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_tool_test_response_format(client: AsyncClient, auth_headers: dict, mock_tool):
    """测试工具测试接口响应格式。"""
    # 创建模拟的数据库会话
    mock_session = AsyncMock()

    # 模拟工具查询结果
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_tool
    mock_session.execute.return_value = mock_result

    # 创建模拟的 async_session 上下文管理器
    class MockAsyncSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            pass

    # 模拟 httpx.AsyncClient
    mock_http_response = MagicMock()
    mock_http_response.status_code = 200
    mock_http_response.json.return_value = {"test": "data"}
    mock_http_response.text = '{"test": "data"}'

    mock_async_client = AsyncMock()
    mock_async_client.__aenter__.return_value.request = AsyncMock(return_value=mock_http_response)

    # 使用 patch 替换依赖
    with patch('app.api.v2.tools.async_session', return_value=MockAsyncSessionContext()), \
         patch('app.core.tools.executor.httpx.AsyncClient', return_value=mock_async_client), \
         patch('app.services.tool_service.async_session', return_value=MockAsyncSessionContext()):
        response = await client.post(
            f"/api/v2/tools/{mock_tool.id}/test",
            json={"args": {"test": "value"}},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # 验证响应格式
        assert "code" in data
        assert "message" in data
        assert "data" in data

        # 验证成功状态
        assert data["code"] == 0
        assert data["message"] == "success"

        # 验证返回数据格式
        result = data["data"]
        assert "success" in result
        assert "duration" in result
        assert isinstance(result["success"], bool)
        assert isinstance(result["duration"], (int, float))


@pytest.mark.asyncio
async def test_tool_test_with_auth_bearer(client: AsyncClient, auth_headers: dict):
    """测试带Bearer认证的HTTP工具。"""
    # 创建带认证的工具
    auth_tool = MagicMock()
    auth_tool.id = uuid.uuid4()
    auth_tool.name = "Bearer工具"
    auth_tool.type = "HTTP"
    auth_tool.enabled = True
    auth_tool.config = {"url": "https://api.example.com/test", "method": "GET"}
    auth_tool.auth = {"mode": "bearer", "key": "encrypted_token"}

    # 创建模拟的数据库会话
    mock_session = AsyncMock()

    # 模拟工具查询结果
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = auth_tool
    mock_session.execute.return_value = mock_result

    # 创建模拟的 async_session 上下文管理器
    class MockAsyncSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            pass

    # 模拟 httpx.AsyncClient
    mock_http_response = MagicMock()
    mock_http_response.status_code = 200
    mock_http_response.json.return_value = {"authenticated": True}
    mock_http_response.text = '{"authenticated": true}'

    mock_async_client = AsyncMock()
    mock_async_client.__aenter__.return_value.request = AsyncMock(return_value=mock_http_response)

    # 使用 patch 替换依赖
    with patch('app.api.v2.tools.async_session', return_value=MockAsyncSessionContext()), \
         patch('app.core.tools.executor.httpx.AsyncClient', return_value=mock_async_client), \
         patch('app.services.tool_service.async_session', return_value=MockAsyncSessionContext()), \
         patch('app.core.tools.executor.decrypt', return_value='decrypted_token'):
        response = await client.post(
            f"/api/v2/tools/{auth_tool.id}/test",
            json={"args": {}},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0