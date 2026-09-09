"""OpenSandbox HTTP 客户端实现。

提供与 OpenSandbox 服务交互的异步 HTTP 客户端，支持沙箱生命周期管理。
"""
import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import httpx

from app.config import settings
from app.exceptions import BizException, ErrorCode


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


class OpenSandboxClient:
    """OpenSandbox HTTP 客户端。

    封装与 OpenSandbox API 的交互，提供沙箱生命周期管理功能。
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
    ):
        """初始化客户端。

        Args:
            base_url: OpenSandbox 服务地址
            api_key: API 密钥
            timeout: HTTP 请求超时（秒）
        """
        self.base_url = (base_url or settings.opensandbox_url).rstrip("/")
        self.api_key = api_key or settings.opensandbox_api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端。"""
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=headers,
            )
        return self._client

    async def close(self):
        """关闭 HTTP 客户端。"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict | None:
        """发送 HTTP 请求。

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

            raise BizException(
                ErrorCode.DEPENDENCY_DOWN,
                f"OpenSandbox API 错误: {error_msg}",
            )
        except httpx.RequestError as e:
            raise BizException(
                ErrorCode.DEPENDENCY_DOWN,
                f"OpenSandbox 连接失败: {str(e)}",
            )

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
        """创建沙箱。

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
        payload: dict[str, Any] = {
            "image": image,
            "command": command,
            "timeout_seconds": timeout_seconds,
        }

        if env:
            payload["env"] = env
        if memory_mb:
            payload["resources"] = {"memory_mb": memory_mb, "cpu": cpu}
        if metadata:
            payload["metadata"] = metadata

        response = await self._request("POST", "/sandboxes", json=payload)

        return SandboxInfo(
            sandbox_id=response["sandbox_id"],
            status=SandboxState(response["status"]),
        )

    async def get_sandbox(self, sandbox_id: str) -> SandboxInfo:
        """获取沙箱状态。

        Args:
            sandbox_id: 沙箱 ID

        Returns:
            沙箱信息
        """
        response = await self._request("GET", f"/sandboxes/{sandbox_id}")

        info = SandboxInfo(
            sandbox_id=response["sandbox_id"],
            status=SandboxState(response["status"]),
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
        response = await self._request(
            "GET",
            f"/sandboxes/{sandbox_id}/diagnostics/logs",
            params={"tail": tail},
        )

        # OpenSandbox 返回日志文本
        logs_text = response if isinstance(response, str) else str(response)

        # 简单解析 stdout/stderr（假设 OpenSandbox 格式）
        # 实际格式可能需要根据 OpenSandbox 文档调整
        return SandboxLogs(stdout=logs_text, stderr="")

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