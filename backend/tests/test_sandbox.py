"""测试代码沙箱服务 - OpenSandbox 实现。

包含：
1. 单元测试（mock OpenSandbox API）
2. 集成测试（真实调用虚拟机，可选）
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.tools.sandbox import (
    CodeSandbox,
    SandboxConfig,
    SandboxLanguage,
    SandboxResult,
    execute_code,
)
from app.providers.sandbox.opensandbox_client import (
    OpenSandboxClient,
    SandboxInfo,
    SandboxLogs,
    SandboxState,
)


# ==================== Fixtures ====================


@pytest.fixture
def mock_opensandbox_client():
    """Mock OpenSandbox 客户端。"""
    with patch("app.core.tools.sandbox.get_opensandbox_client") as mock_get:
        client = AsyncMock(spec=OpenSandboxClient)
        mock_get.return_value = client
        yield client


@pytest.fixture
def sandbox():
    """沙箱实例。"""
    config = SandboxConfig(timeout_seconds=10, memory_limit_mb=128)
    return CodeSandbox(config)


# ==================== 配置测试 ====================


class TestSandboxConfig:
    """沙箱配置测试。"""

    def test_default_config(self):
        """默认配置。"""
        config = SandboxConfig()
        assert config.memory_limit_mb == 512
        assert config.cpu_limit == 1.0
        assert config.timeout_seconds == 30
        assert config.network_disabled is True

    def test_custom_config(self):
        """自定义配置。"""
        config = SandboxConfig(memory_limit_mb=256, timeout_seconds=60)
        assert config.memory_limit_mb == 256
        assert config.timeout_seconds == 60


# ==================== Mock 单元测试 ====================


class TestCodeSandboxMock:
    """使用 Mock 的单元测试。"""

    async def test_execute_python_hello(self, sandbox, mock_opensandbox_client):
        """执行 Python Hello World。"""
        # Mock 返回值
        mock_opensandbox_client.create_sandbox.return_value = SandboxInfo(
            sandbox_id="test-sb-123",
            status=SandboxState.CREATING,
        )
        mock_opensandbox_client.wait_for_completion.return_value = SandboxInfo(
            sandbox_id="test-sb-123",
            status=SandboxState.TERMINATED,
            exit_code=0,
        )
        mock_opensandbox_client.get_logs.return_value = SandboxLogs(
            stdout="Hello, World!\n",
            stderr="",
        )
        mock_opensandbox_client.delete_sandbox.return_value = None

        # 执行
        code = "print('Hello, World!')"
        result = await sandbox.execute(SandboxLanguage.PYTHON, code)

        # 验证
        assert result.success is True
        assert result.exit_code == 0
        assert "Hello, World!" in result.stdout

        # 验证调用
        mock_opensandbox_client.create_sandbox.assert_called_once()
        mock_opensandbox_client.wait_for_completion.assert_called_once()
        mock_opensandbox_client.get_logs.assert_called_once()
        mock_opensandbox_client.delete_sandbox.assert_called_once()

    async def test_execute_python_with_input(self, sandbox, mock_opensandbox_client):
        """执行带输入数据的 Python 代码。"""
        mock_opensandbox_client.create_sandbox.return_value = SandboxInfo(
            sandbox_id="test-sb-456",
            status=SandboxState.CREATING,
        )
        mock_opensandbox_client.wait_for_completion.return_value = SandboxInfo(
            sandbox_id="test-sb-456",
            status=SandboxState.TERMINATED,
            exit_code=0,
        )
        mock_opensandbox_client.get_logs.return_value = SandboxLogs(
            stdout="Alice\n",
            stderr="",
        )

        code = "import json; data=json.load(open('input.json')); print(data['name'])"
        result = await sandbox.execute(
            SandboxLanguage.PYTHON,
            code,
            inputs={"name": "Alice"},
        )

        assert result.success is True
        assert "Alice" in result.stdout

    async def test_execute_nodejs_hello(self, sandbox, mock_opensandbox_client):
        """执行 Node.js 代码。"""
        mock_opensandbox_client.create_sandbox.return_value = SandboxInfo(
            sandbox_id="test-sb-789",
            status=SandboxState.CREATING,
        )
        mock_opensandbox_client.wait_for_completion.return_value = SandboxInfo(
            sandbox_id="test-sb-789",
            status=SandboxState.TERMINATED,
            exit_code=0,
        )
        mock_opensandbox_client.get_logs.return_value = SandboxLogs(
            stdout="Hello from Node!\n",
            stderr="",
        )

        code = "console.log('Hello from Node!');"
        result = await sandbox.execute(SandboxLanguage.NODEJS, code)

        assert result.success is True
        assert result.exit_code == 0
        assert "Hello from Node!" in result.stdout

    async def test_execute_error_code(self, sandbox, mock_opensandbox_client):
        """执行错误代码。"""
        mock_opensandbox_client.create_sandbox.return_value = SandboxInfo(
            sandbox_id="test-sb-error",
            status=SandboxState.CREATING,
        )
        mock_opensandbox_client.wait_for_completion.return_value = SandboxInfo(
            sandbox_id="test-sb-error",
            status=SandboxState.TERMINATED,
            exit_code=1,
        )
        mock_opensandbox_client.get_logs.return_value = SandboxLogs(
            stdout="",
            stderr="ValueError: Test error\n",
        )

        code = "raise ValueError('Test error')"
        result = await sandbox.execute(SandboxLanguage.PYTHON, code)

        assert result.success is False
        assert result.exit_code != 0
        assert "ValueError" in result.stderr

    async def test_dangerous_code_blocked(self, sandbox, mock_opensandbox_client):
        """危险代码被阻止。"""
        from app.exceptions import BizException

        code = "import os; os.system('ls')"
        with pytest.raises(BizException) as exc:
            await sandbox.execute(SandboxLanguage.PYTHON, code)
        assert "危险操作" in str(exc.value)

    async def test_code_size_limit(self, sandbox, mock_opensandbox_client):
        """代码大小限制。"""
        from app.exceptions import BizException

        code = "x" * 100001
        with pytest.raises(BizException) as exc:
            await sandbox.execute(SandboxLanguage.PYTHON, code)
        assert "100KB" in str(exc.value)

    async def test_health_check(self, sandbox, mock_opensandbox_client):
        """健康检查。"""
        mock_opensandbox_client.health_check.return_value = {
            "status": "healthy",
            "url": "http://192.168.137.13:8090",
        }

        result = await sandbox.health_check()

        assert result["status"] == "healthy"


# ==================== 集成测试（真实调用）====================


@pytest.mark.skip(reason="需要虚拟机 OpenSandbox 服务运行")
class TestCodeSandboxIntegration:
    """集成测试 - 真实调用虚拟机 OpenSandbox。

    运行条件：
    - 虚拟机 192.168.137.13:8090 OpenSandbox 服务正常运行
    - 手动移除 skip 装饰器
    """

    async def test_real_execute_python(self):
        """真实执行 Python 代码。"""
        code = "print('Hello from OpenSandbox!')"
        result = await execute_code("python", code, timeout=30)

        assert result.success is True
        assert result.exit_code == 0
        assert "Hello from OpenSandbox!" in result.stdout

    async def test_real_execute_with_input(self):
        """真实执行带输入的代码。"""
        code = """
import json
with open('/code/input.json') as f:
    data = json.load(f)
print(f"Hello, {data['name']}!")
"""
        result = await execute_code(
            "python",
            code,
            inputs={"name": "Integration Test"},
            timeout=30,
        )

        assert result.success is True
        assert "Hello, Integration Test!" in result.stdout

    async def test_real_health_check(self):
        """真实健康检查。"""
        sandbox = CodeSandbox()
        result = await sandbox.health_check()

        assert result["status"] == "healthy"


# ==================== 便捷函数测试 ====================


class TestExecuteCodeHelper:
    """execute_code 便捷函数测试。"""

    async def test_execute_code_helper(self, mock_opensandbox_client):
        """测试便捷函数。"""
        mock_opensandbox_client.create_sandbox.return_value = SandboxInfo(
            sandbox_id="test-helper",
            status=SandboxState.CREATING,
        )
        mock_opensandbox_client.wait_for_completion.return_value = SandboxInfo(
            sandbox_id="test-helper",
            status=SandboxState.TERMINATED,
            exit_code=0,
        )
        mock_opensandbox_client.get_logs.return_value = SandboxLogs(
            stdout="test\n",
            stderr="",
        )

        result = await execute_code("python", "print('test')", timeout=5)

        assert result.success is True
        assert "test" in result.stdout

    async def test_execute_code_string_language(self, mock_opensandbox_client):
        """测试字符串语言参数。"""
        mock_opensandbox_client.create_sandbox.return_value = SandboxInfo(
            sandbox_id="test-lang",
            status=SandboxState.CREATING,
        )
        mock_opensandbox_client.wait_for_completion.return_value = SandboxInfo(
            sandbox_id="test-lang",
            status=SandboxState.TERMINATED,
            exit_code=0,
        )
        mock_opensandbox_client.get_logs.return_value = SandboxLogs(
            stdout="ok\n",
            stderr="",
        )

        # 字符串语言参数
        result = await execute_code("nodejs", "console.log('ok');", timeout=5)

        assert result.success is True