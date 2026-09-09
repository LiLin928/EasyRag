"""代码沙箱服务 - OpenSandbox 远程执行环境。

重构为使用 OpenSandbox HTTP API，替代自建 Docker 隔离实现。
保持原有接口不变，内部实现切换为远程服务调用。
"""
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.config import settings
from app.exceptions import BizException, ErrorCode
from app.providers.sandbox.opensandbox_client import (
    OpenSandboxClient,
    get_opensandbox_client,
)


class SandboxLanguage(Enum):
    """支持的编程语言。"""

    PYTHON = "python"
    NODEJS = "nodejs"


@dataclass
class SandboxConfig:
    """沙箱配置。"""

    memory_limit_mb: int = 512
    cpu_limit: float = 1.0
    timeout_seconds: int = 30
    max_output_size: int = 1048576
    network_disabled: bool = True


@dataclass
class SandboxResult:
    """执行结果。"""

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    error: Optional[str] = None


# 语言镜像映射
LANGUAGE_IMAGES = {
    SandboxLanguage.PYTHON: "python:3.10-alpine",
    SandboxLanguage.NODEJS: "node:18-alpine",
}

LANGUAGE_COMMANDS = {
    SandboxLanguage.PYTHON: ["python", "/code/main.py"],
    SandboxLanguage.NODEJS: ["node", "/code/main.js"],
}


class CodeSandbox:
    """代码沙箱 - 基于 OpenSandbox 实现。

    通过 OpenSandbox 远程服务执行代码，提供安全的隔离环境。
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        """初始化沙箱。

        Args:
            config: 沙箱配置
        """
        self.config = config or SandboxConfig()
        self._client: Optional[OpenSandboxClient] = None

    async def _get_client(self) -> OpenSandboxClient:
        """获取 OpenSandbox 客户端。"""
        if self._client is None:
            self._client = get_opensandbox_client()
        return self._client

    async def close(self):
        """关闭客户端连接。"""
        # 全局客户端不关闭，复用连接
        pass

    async def health_check(self) -> dict:
        """健康检查。

        Returns:
            健康状态信息
        """
        try:
            client = await self._get_client()
            return await client.health_check()
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def execute(
        self,
        language: SandboxLanguage | str,
        code: str,
        inputs: Optional[dict] = None,
        config: Optional[SandboxConfig] = None,
    ) -> SandboxResult:
        """执行代码。

        Args:
            language: 编程语言
            code: 代码内容
            inputs: 输入数据
            config: 执行配置

        Returns:
            执行结果
        """
        exec_config = config or self.config

        # 语言转换
        if isinstance(language, str):
            try:
                language = SandboxLanguage(language.lower())
            except ValueError:
                raise BizException(
                    ErrorCode.PARAM_ERROR,
                    f"不支持的语言: {language}",
                )

        # 代码大小限制
        if len(code) > 100000:
            raise BizException(
                ErrorCode.PARAM_ERROR,
                "代码大小超过 100KB 限制",
            )

        # 危险代码检测（简单检测，主要依赖 OpenSandbox 的隔离）
        dangerous_patterns = [
            "__import__",
            "eval(",
            "exec(",
            "os.system",
            "subprocess.",
            "require('child_process')",
        ]
        for pattern in dangerous_patterns:
            if pattern in code:
                raise BizException(
                    ErrorCode.PARAM_ERROR,
                    f"检测到危险操作: {pattern}",
                )

        start_time = time.time()

        try:
            client = await self._get_client()

            # 准备环境变量
            env = {
                "SANDBOX_CODE": code,
            }
            if inputs:
                env["SANDBOX_INPUT"] = json.dumps(inputs)

            # 根据语言选择镜像和执行方式
            if language == SandboxLanguage.PYTHON:
                image = LANGUAGE_IMAGES[language]
                # 使用 shell 命令创建代码文件并执行
                # 注意：代码通过环境变量传递，避免复杂的字符串转义
                command = [
                    "sh", "-c",
                    f'''mkdir -p /code && \
echo "$SANDBOX_CODE" > /code/main.py && \
if [ -n "$SANDBOX_INPUT" ]; then echo "$SANDBOX_INPUT" > /code/input.json; fi && \
python /code/main.py'''
                ]
            elif language == SandboxLanguage.NODEJS:
                image = LANGUAGE_IMAGES[language]
                command = [
                    "sh", "-c",
                    f'''mkdir -p /code && \
echo "$SANDBOX_CODE" > /code/main.js && \
if [ -n "$SANDBOX_INPUT" ]; then echo "$SANDBOX_INPUT" > /code/input.json; fi && \
node /code/main.js'''
                ]
            else:
                raise BizException(
                    ErrorCode.PARAM_ERROR,
                    f"不支持的语言: {language}",
                )

            # 创建沙箱
            sandbox_info = await client.create_sandbox(
                image=image,
                command=command,
                env=env,
                memory_mb=exec_config.memory_limit_mb,
                cpu=exec_config.cpu_limit,
                timeout_seconds=exec_config.timeout_seconds,
            )

            # 等待执行完成
            final_info = await client.wait_for_completion(
                sandbox_info.sandbox_id,
                timeout=exec_config.timeout_seconds + 10,  # 额外 10s 缓冲
            )

            # 获取日志
            logs = await client.get_logs(sandbox_info.sandbox_id)

            # 清理沙箱
            try:
                await client.delete_sandbox(sandbox_info.sandbox_id)
            except Exception:
                pass

            execution_time_ms = (time.time() - start_time) * 1000

            # 截断输出
            stdout = logs.stdout
            stderr = logs.stderr
            if len(stdout) > exec_config.max_output_size:
                stdout = stdout[: exec_config.max_output_size] + "\n[输出已截断]"
            if len(stderr) > exec_config.max_output_size:
                stderr = stderr[: exec_config.max_output_size] + "\n[输出已截断]"

            return SandboxResult(
                success=final_info.exit_code == 0,
                stdout=stdout,
                stderr=stderr,
                exit_code=final_info.exit_code if final_info.exit_code is not None else -1,
                execution_time_ms=execution_time_ms,
                error=None if final_info.exit_code == 0 else stderr[:1000],
            )

        except BizException:
            raise
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return SandboxResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                execution_time_ms=execution_time_ms,
                error=str(e),
            )

    async def health_check(self) -> dict:
        """健康检查。

        Returns:
            健康状态信息
        """
        try:
            client = await self._get_client()
            return await client.health_check()
        except Exception as e:
            return {"status": "error", "error": str(e)}


# 全局实例
_sandbox_instance: Optional[CodeSandbox] = None


def get_sandbox(config: Optional[SandboxConfig] = None) -> CodeSandbox:
    """获取沙箱实例。

    Args:
        config: 沙箱配置

    Returns:
        沙箱实例
    """
    global _sandbox_instance
    if _sandbox_instance is None or config is not None:
        _sandbox_instance = CodeSandbox(config)
    return _sandbox_instance


async def execute_code(
    language: str,
    code: str,
    inputs: Optional[dict] = None,
    timeout: int = 30,
    memory_limit_mb: int = 512,
) -> SandboxResult:
    """执行代码（便捷函数）。

    Args:
        language: 编程语言（python/nodejs）
        code: 代码内容
        inputs: 输入数据
        timeout: 超时秒数
        memory_limit_mb: 内存限制（MB）

    Returns:
        执行结果
    """
    config = SandboxConfig(
        timeout_seconds=timeout,
        memory_limit_mb=memory_limit_mb,
    )
    sandbox = get_sandbox(config)
    return await sandbox.execute(language, code, inputs, config)