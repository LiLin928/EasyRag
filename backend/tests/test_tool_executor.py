"""工具执行器测试。

测试增强版工具执行器的功能：
- HTTP / Python / 内置三类工具执行
- 超时处理
- 错误处理
- 执行统计
- 缓存功能
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import httpx

from app.core.tools.executor import (
    execute,
    ToolExecutionResult,
    _http,
    _python,
    _builtin,
    _render,
    _safe_json,
)


@pytest.fixture
def mock_http_tool():
    """创建模拟 HTTP 工具对象。"""
    tool = MagicMock()
    tool.id = uuid.uuid4()
    tool.name = "测试HTTP工具"
    tool.type = "HTTP"
    tool.description = "测试用HTTP工具"
    tool.config = {
        "url": "https://httpbin.org/get",
        "method": "GET",
        "timeout": 30,
    }
    tool.auth = {}
    return tool


@pytest.fixture
def mock_python_tool():
    """创建模拟 Python 工具对象。"""
    tool = MagicMock()
    tool.id = uuid.uuid4()
    tool.name = "测试Python工具"
    tool.type = "Python"
    tool.description = "测试用Python工具"
    tool.config = {
        "code": "result = {'processed': args.get('input', 'default')}"
    }
    return tool


@pytest.fixture
def mock_builtin_tool():
    """创建模拟内置工具对象。"""
    tool = MagicMock()
    tool.id = uuid.uuid4()
    tool.name = "test_builtin"
    tool.type = "内置"
    tool.description = "测试用内置工具"
    return tool


# ==================== HTTP 工具测试 ====================

@pytest.mark.asyncio
async def test_http_tool_success(mock_http_tool):
    """测试HTTP工具成功执行。"""
    # 模拟 httpx 响应
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True, "data": "test"}
    mock_response.text = '{"success": true}'

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch('app.core.tools.executor.httpx.AsyncClient', return_value=mock_client):
        result = await execute(mock_http_tool, {"test": "value"}, timeout=30)

    assert isinstance(result, ToolExecutionResult)
    assert result.success is True
    assert result.data == {"success": True, "data": "test"}
    assert result.error is None
    assert result.duration_ms >= 0
    assert result.status_code == 200
    assert result.cached is False


@pytest.mark.asyncio
async def test_http_tool_failure(mock_http_tool):
    """测试HTTP工具失败执行。"""
    # 模拟 httpx 响应（失败）
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"error": "not found"}
    mock_response.text = '{"error": "not found"}'

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch('app.core.tools.executor.httpx.AsyncClient', return_value=mock_client):
        result = await execute(mock_http_tool, {"test": "value"}, timeout=30)

    assert isinstance(result, ToolExecutionResult)
    assert result.success is False
    assert result.status_code == 404
    assert "HTTP 404" in result.error
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_http_tool_timeout(mock_http_tool):
    """测试HTTP工具超时处理。"""
    mock_client = AsyncMock()
    mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch('app.core.tools.executor.httpx.AsyncClient', return_value=mock_client):
        result = await execute(mock_http_tool, {"test": "value"}, timeout=5)

    assert isinstance(result, ToolExecutionResult)
    assert result.success is False
    assert "HTTP 请求超时" in result.error
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_http_tool_request_error(mock_http_tool):
    """测试HTTP工具请求错误处理。"""
    mock_client = AsyncMock()
    mock_client.request = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch('app.core.tools.executor.httpx.AsyncClient', return_value=mock_client):
        result = await execute(mock_http_tool, {"test": "value"}, timeout=30)

    assert isinstance(result, ToolExecutionResult)
    assert result.success is False
    assert "HTTP 请求失败" in result.error
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_http_tool_with_bearer_auth(mock_http_tool):
    """测试HTTP工具Bearer认证。"""
    mock_http_tool.auth = {"mode": "bearer", "key": "encrypted_token"}

    # 模拟 httpx 响应
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"authenticated": True}
    mock_response.text = '{"authenticated": true}'

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch('app.core.tools.executor.httpx.AsyncClient', return_value=mock_client), \
         patch('app.core.tools.executor.decrypt', return_value='decrypted_token'):
        result = await execute(mock_http_tool, {}, timeout=30)

    assert result.success is True
    # 验证请求中包含了认证头
    call_args = mock_client.request.call_args
    assert "Authorization" in call_args[1]["headers"]
    assert call_args[1]["headers"]["Authorization"] == "Bearer decrypted_token"


@pytest.mark.asyncio
async def test_http_tool_with_apikey_auth(mock_http_tool):
    """测试HTTP工具API Key认证。"""
    mock_http_tool.auth = {"mode": "apikey", "key": "encrypted_key"}

    # 模拟 httpx 响应
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"authenticated": True}
    mock_response.text = '{"authenticated": true}'

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch('app.core.tools.executor.httpx.AsyncClient', return_value=mock_client), \
         patch('app.core.tools.executor.decrypt', return_value='decrypted_key'):
        result = await execute(mock_http_tool, {}, timeout=30)

    assert result.success is True
    # 验证请求中包含了API Key头
    call_args = mock_client.request.call_args
    assert "X-API-Key" in call_args[1]["headers"]
    assert call_args[1]["headers"]["X-API-Key"] == "decrypted_key"


@pytest.mark.asyncio
async def test_http_tool_auth_decrypt_failure(mock_http_tool):
    """测试HTTP工具认证密钥解密失败。"""
    mock_http_tool.auth = {"mode": "bearer", "key": "invalid_encrypted_token"}

    result = await execute(mock_http_tool, {}, timeout=30)

    assert isinstance(result, ToolExecutionResult)
    assert result.success is False
    assert "认证密钥解密失败" in result.error


# ==================== Python 工具测试 ====================

@pytest.mark.asyncio
async def test_python_tool_success_no_sandbox(mock_python_tool):
    """测试Python工具成功执行（无沙箱，降级exec）。"""
    result = await execute(mock_python_tool, {"input": "test_value"}, timeout=30)

    assert isinstance(result, ToolExecutionResult)
    assert result.success is True
    assert result.data == {"processed": "test_value"}
    assert result.error is None
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_python_tool_with_sandbox(mock_python_tool):
    """测试Python工具成功执行（有沙箱）。"""
    # 模拟沙箱导入成功和返回
    mock_sandbox_result = MagicMock()
    mock_sandbox_result.ok = True
    mock_sandbox_result.output = {"result": "success"}
    mock_sandbox_result.error = None
    mock_sandbox_result.duration = 50.0

    # 模拟 run_in_sandbox 函数
    mock_run_in_sandbox = AsyncMock(return_value=mock_sandbox_result)

    # 使用 sys.modules 来模拟 app.providers.sandbox 模块
    import sys
    from types import ModuleType

    # 创建一个模拟的 sandbox 模块
    mock_sandbox_module = ModuleType('app.providers.sandbox')
    mock_sandbox_module.run_in_sandbox = mock_run_in_sandbox

    # 临时替换模块
    original_module = sys.modules.get('app.providers.sandbox')
    sys.modules['app.providers.sandbox'] = mock_sandbox_module

    try:
        result = await execute(mock_python_tool, {"input": "test"}, timeout=30)

        assert isinstance(result, ToolExecutionResult)
        assert result.success is True
        assert result.data == {"result": "success"}
        assert result.error is None
    finally:
        # 恢复原始模块
        if original_module:
            sys.modules['app.providers.sandbox'] = original_module
        else:
            del sys.modules['app.providers.sandbox']


@pytest.mark.asyncio
async def test_python_tool_no_code():
    """测试Python工具未配置代码。"""
    tool = MagicMock()
    tool.type = "Python"
    tool.config = {}

    result = await execute(tool, {}, timeout=30)

    assert isinstance(result, ToolExecutionResult)
    assert result.success is False
    assert "Python 工具未配置代码" in result.error


@pytest.mark.asyncio
async def test_python_tool_execution_error():
    """测试Python工具执行错误。"""
    tool = MagicMock()
    tool.type = "Python"
    tool.config = {"code": "result = undefined_variable"}

    result = await execute(tool, {}, timeout=30)

    assert isinstance(result, ToolExecutionResult)
    assert result.success is False
    assert "Python 执行错误" in result.error


# ==================== 内置工具测试 ====================

@pytest.mark.asyncio
async def test_builtin_tool_not_found(mock_builtin_tool):
    """测试内置工具不存在。"""
    result = await execute(mock_builtin_tool, {}, timeout=30)

    assert isinstance(result, ToolExecutionResult)
    assert result.success is False
    assert f"内置工具 {mock_builtin_tool.name} 不存在" in result.error


@pytest.mark.asyncio
async def test_builtin_tool_success():
    """测试内置工具成功执行。"""
    # 注册一个测试内置工具
    from app.core.tools import builtins

    def test_func(args):
        return {"result": args.get("input", "default")}

    builtins.BUILTIN["test_builtin_func"] = test_func

    tool = MagicMock()
    tool.type = "内置"
    tool.name = "test_builtin_func"

    result = await execute(tool, {"input": "test_value"}, timeout=30)

    assert isinstance(result, ToolExecutionResult)
    assert result.success is True
    assert result.data == {"result": "test_value"}
    assert result.duration_ms >= 0

    # 清理
    del builtins.BUILTIN["test_builtin_func"]


@pytest.mark.asyncio
async def test_builtin_tool_execution_error():
    """测试内置工具执行错误。"""
    from app.core.tools import builtins

    def error_func(args):
        raise ValueError("Test error")

    builtins.BUILTIN["error_builtin"] = error_func

    tool = MagicMock()
    tool.type = "内置"
    tool.name = "error_builtin"

    result = await execute(tool, {}, timeout=30)

    assert isinstance(result, ToolExecutionResult)
    assert result.success is False
    assert "内置工具执行错误" in result.error

    # 清理
    del builtins.BUILTIN["error_builtin"]


# ==================== 未知工具类型测试 ====================

@pytest.mark.asyncio
async def test_unknown_tool_type():
    """测试未知工具类型。"""
    tool = MagicMock()
    tool.type = "Unknown"

    result = await execute(tool, {}, timeout=30)

    assert isinstance(result, ToolExecutionResult)
    assert result.success is False
    assert "未知工具类型" in result.error


# ==================== 超时测试 ====================

@pytest.mark.asyncio
async def test_tool_execution_timeout():
    """测试工具执行超时（httpx.TimeoutException）。"""
    tool = MagicMock()
    tool.type = "HTTP"
    tool.config = {"url": "https://example.com", "method": "GET"}
    tool.auth = {}

    # 模拟超时
    mock_client = AsyncMock()
    mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch('app.core.tools.executor.httpx.AsyncClient', return_value=mock_client):
        result = await execute(tool, {}, timeout=1)

    assert isinstance(result, ToolExecutionResult)
    assert result.success is False
    assert "超时" in result.error


# ==================== 缓存测试 ====================

@pytest.mark.asyncio
async def test_tool_execution_with_cache_hit():
    """测试工具执行缓存命中。"""
    tool = MagicMock()
    tool.type = "内置"
    tool.name = "cached_tool"

    from app.core.tools import builtins

    def cached_func(args):
        return {"result": "cached"}

    builtins.BUILTIN["cached_tool"] = cached_func

    # 第一次执行
    result1 = await execute(tool, {}, timeout=30, cache_key="test_cache_key")

    # 第二次执行（应该命中缓存，但由于缓存未实现，仍然执行）
    result2 = await execute(tool, {}, timeout=30, cache_key="test_cache_key")

    # 当前缓存功能未实现，所以两次都是 executed
    assert result1.cached is False
    assert result2.cached is False

    # 清理
    del builtins.BUILTIN["cached_tool"]


# ==================== 辅助函数测试 ====================

def test_render_template():
    """测试模板渲染。"""
    template = "https://api.example.com/users/{user_id}/posts/{post_id}"
    args = {"user_id": "123", "post_id": "456"}

    result = _render(template, args)

    assert result == "https://api.example.com/users/123/posts/456"


def test_render_template_missing_key():
    """测试模板渲染（缺失键）。"""
    template = "https://api.example.com/users/{user_id}/posts/{post_id}"
    args = {"user_id": "123"}

    result = _render(template, args)

    assert result == "https://api.example.com/users/123/posts/{post_id}"


def test_safe_json_valid():
    """测试安全解析JSON（有效）。"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"key": "value"}

    result = _safe_json(mock_response)

    assert result == {"key": "value"}


def test_safe_json_invalid():
    """测试安全解析JSON（无效，返回文本）。"""
    mock_response = MagicMock()
    mock_response.json.side_effect = Exception("Invalid JSON")
    mock_response.text = "plain text"

    result = _safe_json(mock_response)

    assert result == "plain text"


# ==================== 结果数据类测试 ====================

def test_tool_execution_result_dataclass():
    """测试ToolExecutionResult数据类。"""
    result = ToolExecutionResult(
        success=True,
        data={"test": "value"},
        error=None,
        duration_ms=100.5,
        status_code=200,
        cached=False,
    )

    assert result.success is True
    assert result.data == {"test": "value"}
    assert result.error is None
    assert result.duration_ms == 100.5
    assert result.status_code == 200
    assert result.cached is False


def test_tool_execution_result_defaults():
    """测试ToolExecutionResult默认值。"""
    result = ToolExecutionResult(
        success=False,
        data=None,
        error="Test error",
        duration_ms=0,
    )

    assert result.status_code is None
    assert result.cached is False


# ==================== 执行统计测试 ====================

@pytest.mark.asyncio
async def test_execution_statistics():
    """测试执行统计（持续时间）。"""
    tool = MagicMock()
    tool.type = "HTTP"
    tool.config = {"url": "https://example.com", "method": "GET"}
    tool.auth = {}

    # 模拟延迟响应
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_response.text = '{}'

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch('app.core.tools.executor.httpx.AsyncClient', return_value=mock_client):
        result = await execute(tool, {}, timeout=30)

    assert isinstance(result, ToolExecutionResult)
    assert result.duration_ms >= 0
    assert isinstance(result.duration_ms, float)