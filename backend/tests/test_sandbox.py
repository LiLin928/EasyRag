\"\"\"测试代码沙箱服务。\"\"\"
import pytest
from app.core.tools.sandbox import CodeSandbox, SandboxConfig, SandboxLanguage, execute_code


@pytest.fixture
async def sandbox():
    config = SandboxConfig(timeout_seconds=10, memory_limit_mb=128)
    sb = CodeSandbox(config)
    yield sb
    await sb.close()


class TestSandboxConfig:
    def test_default_config(self):
        config = SandboxConfig()
        assert config.memory_limit_mb == 512
        assert config.cpu_limit == 1.0
        assert config.timeout_seconds == 30
        assert config.network_disabled is True

    def test_custom_config(self):
        config = SandboxConfig(memory_limit_mb=256, timeout_seconds=60)
        assert config.memory_limit_mb == 256
        assert config.timeout_seconds == 60


class TestCodeSandbox:
    async def test_execute_python_hello(self, sandbox):
        code = \"print('Hello, World!')\"
        result = await sandbox.execute(SandboxLanguage.PYTHON, code)
        assert result.success is True
        assert result.exit_code == 0
        assert \"Hello, World!\" in result.stdout

    async def test_execute_python_with_input(self, sandbox):
        code = \"import json; data=json.load(open('input.json')); print(data['name'])\"
        result = await sandbox.execute(SandboxLanguage.PYTHON, code, inputs={\"name\": \"Alice\"})
        assert result.success is True
        assert \"Alice\" in result.stdout

    async def test_execute_nodejs_hello(self, sandbox):
        code = \"console.log('Hello from Node!');\"
        result = await sandbox.execute(SandboxLanguage.NODEJS, code)
        assert result.success is True
        assert result.exit_code == 0
        assert \"Hello from Node!\" in result.stdout

    async def test_execute_error_code(self, sandbox):
        code = \"raise ValueError('Test error')\"
        result = await sandbox.execute(SandboxLanguage.PYTHON, code)
        assert result.success is False
        assert result.exit_code != 0
        assert \"ValueError\" in result.stderr

    async def test_dangerous_code_blocked(self, sandbox):
        code = \"import os; os.system('ls')\"
        with pytest.raises(Exception) as exc:
            await sandbox.execute(SandboxLanguage.PYTHON, code)
        assert \"Dangerous\" in str(exc.value)

    async def test_code_size_limit(self, sandbox):
        code = \"x\" * 100001
        with pytest.raises(Exception) as exc:
            await sandbox.execute(SandboxLanguage.PYTHON, code)
        assert \"100KB\" in str(exc.value)

    async def test_timeout(self):
        config = SandboxConfig(timeout_seconds=1)
        sandbox = CodeSandbox(config)
        code = \"import time; time.sleep(10)\"
        result = await sandbox.execute(SandboxLanguage.PYTHON, code)
        assert result.success is False
        assert \"timeout\" in result.error.lower()
        await sandbox.close()


class TestExecuteCodeHelper:
    async def test_execute_code_helper(self):
        result = await execute_code(\"python\", \"print('test')\", timeout=5)
        assert result.success is True
        assert \"test\" in result.stdout
