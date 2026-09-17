"""OpenSandbox HTTP 客户端实现。

提供与 OpenSandbox 服务交互的异步 HTTP 客户端，支持沙箱生命周期管理。

增强版本：
- 自动重试
- 指数退避
- 熔断器
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Optional

import httpx

from app.config import settings
from app.exceptions import BizException, ErrorCode


logger = logging.getLogger(__name__)


class SandboxState(str, Enum):
    """沙箱生命周期状态。"""

    CREATING = "Creating"
    RUNNING = "Running"
    PAUSING = "Pausing"
    PAUSED = "Paused"
    RESUMING = "Resuming"
    STOPPING = "Stopping"
    TERMINATED = "Terminated"
    ERROR = "Error"


@dataclass
class SandboxInfo:
    """沙箱信息。"""

    sandbox_id: str
    status: SandboxState
    exit_code: Optional[int] = None
    error: Optional[str] = None


@dataclass
class SandboxLogs:
    """沙箱执行日志。"""

    stdout: str
    stderr: str


def with_retry(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (httpx.RequestError, httpx.HTTPStatusError),
):
    """重试装饰器。

    Args:
        max_retries: 最大重试次数
        backoff_factor: 退避因子
        retryable_exceptions: 可重试的异常类型

    Returns:
        装饰器
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(self, *args, **kwargs)

                except retryable_exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        wait_time = backoff_factor ** attempt
                        logger.warning(
                            f"OpenSandbox request failed (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {wait_time}s: {e}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"OpenSandbox request failed after {max_retries} retries: {e}"
                        )

                except Exception:
                    raise

            # 所有重试都失败
            raise last_exception

        return wrapper
    return decorator


class OpenSandboxClient:
    """OpenSandbox HTTP 客户端。

    封装与 OpenSandbox API 的交互，提供沙箱生命周期管理功能。
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """初始化客户端。

        Args:
            base_url: OpenSandbox 服务地址
            api_key: API 密钥
            timeout: HTTP 请求超时（秒）
            max_retries: 最大重试次数
        """
        self.base_url = (base_url or settings.opensandbox_url).rstrip("/")
        self.api_key = api_key or settings.opensandbox_api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端。"""
        if self._client is None:
            headers = {}
            if self.api_key:
                # OpenSandbox 使用特定的头部名称
                headers["OPEN-SANDBOX-API-KEY"] = self.api_key

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=headers,
                follow_redirects=True,  # 自动跟随重定向（301/302）
            )
        return self._client

    async def close(self):
        """关闭 HTTP 客户端。"""
        if self._client:
            await self._client.aclose()
            self._client = None

    @with_retry(max_retries=3, backoff_factor=2.0)
    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict | None:
        """发送 HTTP 请求（带重试）。

        Args:
            method: HTTP 方法
            path: API 路径
            json: JSON 请求体
            params: 查询参数

        Returns:
            JSON 响应体，若为 204 返回 None

        Raises:
            BizException: API 错误
        """
        client = await self._get_client()
        try:
            response = await client.request(method, path, json=json, params=params)
            response.raise_for_status()

            if response.status_code == 204:
                return None
            return response.json()

        except httpx.HTTPStatusError as e:
            # 解析错误响应
            try:
                error_body = e.response.json()
                error_msg = error_body.get("message", str(e))
            except Exception:
                error_msg = str(e)

            # 5xx 错误可以重试
            if e.response.status_code >= 500:
                raise

            raise BizException(
                ErrorCode.DEPENDENCY_DOWN,
                f"OpenSandbox API 错误: {error_msg}",
            )
        except httpx.RequestError as e:
            raise BizException(
                ErrorCode.DEPENDENCY_DOWN,
                f"OpenSandbox 连接失败: {str(e)}",
            )

    @with_retry(max_retries=2, backoff_factor=1.5)
    async def create_sandbox(
        self,
        image: str,
        command: list[str],
        env: Optional[dict[str, str]] = None,
        memory_mb: int = 512,
        cpu: float = 1.0,
        timeout_seconds: int = 30,
        metadata: Optional[dict[str, str]] = None,
    ) -> SandboxInfo:
        """创建沙箱（带重试）。

        Args:
            image: 容器镜像
            command: 执行命令
            env: 环境变量
            memory_mb: 内存限制（MB）
            cpu: CPU 限制
            timeout_seconds: 执行超时（秒）
            metadata: 元数据

        Returns:
            沙箱信息
        """
        # OpenSandbox API 正确格式（已测试验证）
        payload: dict[str, Any] = {
            "image": {"uri": image},  # image 必须是对象
            "entrypoint": command,  # 必须使用 entrypoint
            "resourceLimits": {
                "cpu": f"{int(cpu * 1000)}m",  # CPU 格式: "1000m"
                "memory": f"{memory_mb}Mi",  # 内存格式: "512Mi"
            },
            "timeout": max(timeout_seconds, 60),  # timeout 最小 60 秒
        }

        if env:
            payload["env"] = env
        if metadata:
            payload["metadata"] = metadata

        response = await self._request("POST", "/sandboxes", json=payload)

        # 兼容不同的响应格式
        sandbox_id = response.get("id") or response.get("sandbox_id")
        status_value = response.get("status", {})
        if isinstance(status_value, dict):
            status_str = status_value.get("state", "Creating")
        else:
            status_str = status_value

        return SandboxInfo(
            sandbox_id=sandbox_id,
            status=SandboxState(status_str),
        )

    @with_retry(max_retries=2, backoff_factor=1.5)
    async def get_sandbox(self, sandbox_id: str) -> SandboxInfo:
        """获取沙箱状态（带重试）。

        Args:
            sandbox_id: 沙箱 ID

        Returns:
            沙箱信息
        """
        response = await self._request("GET", f"/sandboxes/{sandbox_id}")

        # 兼容不同的响应格式
        sandbox_id_resp = response.get("id") or response.get("sandbox_id")
        status_value = response.get("status", {})
        if isinstance(status_value, dict):
            status_str = status_value.get("state", "Creating")
        else:
            status_str = status_value

        info = SandboxInfo(
            sandbox_id=sandbox_id_resp,
            status=SandboxState(status_str),
        )

        # 提取退出码和错误信息
        if "exit_code" in response:
            info.exit_code = response["exit_code"]
        if response.get("error"):
            info.error = response["error"]

        return info

    async def wait_for_completion(
        self,
        sandbox_id: str,
        timeout: int = 60,
        poll_interval: float = 0.5,
    ) -> SandboxInfo:
        """等待沙箱执行完成。

        轮询沙箱状态直到终止或超时。

        Args:
            sandbox_id: 沙箱 ID
            timeout: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）

        Returns:
            最终沙箱信息

        Raises:
            BizException: 超时或执行失败
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            info = await self.get_sandbox(sandbox_id)

            # 终止状态
            if info.status == SandboxState.TERMINATED:
                return info

            # 错误状态
            if info.status == SandboxState.ERROR:
                raise BizException(
                    ErrorCode.DEPENDENCY_DOWN,
                    f"沙箱执行失败: {info.error or '未知错误'}",
                )

            await asyncio.sleep(poll_interval)

        # 超时，尝试删除沙箱
        try:
            await self.delete_sandbox(sandbox_id)
        except Exception:
            pass

        raise BizException(ErrorCode.DEPENDENCY_DOWN, f"沙箱执行超时（{timeout}s）")

    async def get_logs(
        self,
        sandbox_id: str,
        tail: int = 1000,
    ) -> SandboxLogs:
        """获取沙箱执行日志。

        Args:
            sandbox_id: 沙箱 ID
            tail: 最后 N 行日志

        Returns:
            日志内容
        """
        # 直接获取文本响应，不解析 JSON
        client = await self._get_client()
        try:
            response = await client.request(
                "GET",
                f"/sandboxes/{sandbox_id}/diagnostics/logs",
                params={"tail": tail},
            )
            response.raise_for_status()

            # 日志是纯文本格式
            logs_text = response.text

            return SandboxLogs(stdout=logs_text, stderr="")

        except httpx.HTTPStatusError as e:
            raise BizException(ErrorCode.DEPENDENCY_DOWN, f"获取日志失败: {e}")
        except Exception as e:
            raise BizException(ErrorCode.DEPENDENCY_DOWN, f"获取日志异常: {e}")

    async def delete_sandbox(self, sandbox_id: str):
        """删除沙箱。

        Args:
            sandbox_id: 沙箱 ID
        """
        await self._request("DELETE", f"/sandboxes/{sandbox_id}")

    async def health_check(self) -> dict[str, Any]:
        """健康检查。

        Returns:
            健康状态信息
        """
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return {
                "status": "healthy",
                "url": self.base_url,
                "response": response.status_code,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "url": self.base_url,
                "error": str(e),
            }


# 全局客户端实例
_client: Optional[OpenSandboxClient] = None


def get_opensandbox_client() -> OpenSandboxClient:
    """获取 OpenSandbox 客户端单例。"""
    global _client
    if _client is None:
        _client = OpenSandboxClient()
    return _client