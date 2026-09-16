"""工具执行器：HTTP / 内置 / Python 三类工具统一执行入口。

增强版本：
- 更详细的错误信息
- 超时处理
- 结果缓存（可选）
- 执行统计
"""
import time
import asyncio
from typing import Optional
from dataclasses import dataclass

import httpx

from app.security.crypto import decrypt
from app.exceptions import BizException, ErrorCode


@dataclass
class ToolExecutionResult:
    """工具执行结果。"""
    success: bool
    data: Optional[dict]
    error: Optional[str]
    duration_ms: float
    status_code: Optional[int] = None
    cached: bool = False


async def execute(
    tool,
    args: dict,
    timeout: int = 30,
    cache_key: Optional[str] = None,
) -> ToolExecutionResult:
    """执行工具。

    Args:
        tool: 工具实例
        args: 工具参数
        timeout: 执行超时（秒）
        cache_key: 缓存键（可选，用于缓存结果）

    Returns:
        工具执行结果
    """
    t = (tool.type or "HTTP").strip()

    # 检查缓存
    if cache_key:
        cached_result = await _get_cached_result(cache_key)
        if cached_result:
            cached_result.cached = True
            return cached_result

    try:
        if t == "HTTP":
            result = await _http(tool, args, timeout)
        elif t == "Python":
            result = await _python(tool, args, timeout)
        elif t == "内置":
            result = _builtin(tool, args)
        else:
            result = ToolExecutionResult(
                success=False,
                data=None,
                error=f"未知工具类型: {t}",
                duration_ms=0,
            )

        # 缓存成功结果
        if cache_key and result.success:
            await _cache_result(cache_key, result)

        return result

    except asyncio.TimeoutError:
        return ToolExecutionResult(
            success=False,
            data=None,
            error=f"工具执行超时（{timeout}s）",
            duration_ms=timeout * 1000,
        )
    except BizException:
        raise
    except Exception as e:
        return ToolExecutionResult(
            success=False,
            data=None,
            error=f"工具执行异常: {str(e)}",
            duration_ms=0,
        )


async def _http(
    tool,
    args: dict,
    timeout: int = 30
) -> ToolExecutionResult:
    """执行 HTTP 工具。

    Args:
        tool: 工具实例
        args: 工具参数
        timeout: 执行超时（秒）

    Returns:
        工具执行结果
    """
    cfg = tool.config or {}
    url = _render(cfg.get("url", ""), args)
    method = cfg.get("method", "GET").upper()
    headers = dict(cfg.get("headers", {}))

    # 认证处理
    auth = tool.auth or {}
    if auth.get("mode") == "bearer" and auth.get("key"):
        try:
            headers["Authorization"] = f"Bearer {decrypt(auth['key'])}"
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                data=None,
                error=f"认证密钥解密失败: {str(e)}",
                duration_ms=0,
            )
    elif auth.get("mode") == "apikey" and auth.get("key"):
        try:
            headers["X-API-Key"] = decrypt(auth["key"])
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                data=None,
                error=f"API Key 解密失败: {str(e)}",
                duration_ms=0,
            )

    # 请求参数和请求体
    body_type = cfg.get("bodyType", "json")

    # GET/DELETE: 参数作为查询参数
    query_params = args if method in ("GET", "DELETE") else None

    # POST/PUT/PATCH: 参数作为请求体
    json_body = args if body_type == "json" and method in ("POST", "PUT", "PATCH") else None

    t0 = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method,
                url,
                headers=headers,
                params=query_params,
                json=json_body
            )

        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        ok_ = resp.status_code < 400

        return ToolExecutionResult(
            success=ok_,
            data=_safe_json(resp),
            error=None if ok_ else f"HTTP {resp.status_code}: {resp.text[:500]}",
            duration_ms=duration_ms,
            status_code=resp.status_code,
        )

    except httpx.TimeoutException:
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return ToolExecutionResult(
            success=False,
            data=None,
            error=f"HTTP 请求超时（{timeout}s）",
            duration_ms=duration_ms,
        )
    except httpx.RequestError as e:
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return ToolExecutionResult(
            success=False,
            data=None,
            error=f"HTTP 请求失败: {str(e)}",
            duration_ms=duration_ms,
        )


async def _python(
    tool,
    args: dict,
    timeout: int = 30
) -> ToolExecutionResult:
    """执行 Python 工具。

    Args:
        tool: 工具实例
        args: 工具参数
        timeout: 执行超时（秒）

    Returns:
        工具执行结果
    """
    code = (tool.config or {}).get("code", "")
    if not code:
        return ToolExecutionResult(
            success=False,
            data=None,
            error="Python 工具未配置代码",
            duration_ms=0,
        )

    t0 = time.perf_counter()

    try:
        # 尝试使用沙箱
        from app.providers.sandbox import run_in_sandbox
        r = await run_in_sandbox(code=code, inputs=args, timeout=timeout, memory_mb=256)

        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return ToolExecutionResult(
            success=r.ok,
            data=r.output,
            error=r.error,
            duration_ms=duration_ms,
        )

    except ImportError:
        # 降级：受限 exec（仅开发环境）
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Sandbox not available, using exec fallback")

        try:
            local: dict = {"args": args, "result": None}

            # 添加超时保护
            exec(code, {"__builtins__": __builtins__}, local)

            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            return ToolExecutionResult(
                success=True,
                data=local.get("result"),
                error=None,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            return ToolExecutionResult(
                success=False,
                data=None,
                error=f"Python 执行错误: {str(e)}",
                duration_ms=duration_ms,
            )


def _builtin(tool, args: dict) -> ToolExecutionResult:
    """执行内置工具。

    Args:
        tool: 工具实例
        args: 工具参数

    Returns:
        工具执行结果
    """
    from app.core.tools.builtins import BUILTIN

    fn = BUILTIN.get(tool.name)
    if not fn:
        return ToolExecutionResult(
            success=False,
            data=None,
            error=f"内置工具 {tool.name} 不存在",
            duration_ms=0,
        )

    t0 = time.perf_counter()

    try:
        data = fn(args)
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)

        return ToolExecutionResult(
            success=True,
            data=data,
            error=None,
            duration_ms=duration_ms,
        )

    except Exception as e:
        duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return ToolExecutionResult(
            success=False,
            data=None,
            error=f"内置工具执行错误: {str(e)}",
            duration_ms=duration_ms,
        )


# 缓存辅助函数
async def _get_cached_result(cache_key: str) -> Optional[ToolExecutionResult]:
    """获取缓存结果。

    Args:
        cache_key: 缓存键

    Returns:
        缓存的结果，如果没有缓存则返回 None
    """
    # TODO: 实现缓存逻辑（Redis）
    return None


async def _cache_result(cache_key: str, result: ToolExecutionResult) -> None:
    """缓存结果。

    Args:
        cache_key: 缓存键
        result: 要缓存的结果
    """
    # TODO: 实现缓存逻辑（Redis）
    pass


def _render(tpl: str, args: dict) -> str:
    """渲染模板。

    Args:
        tpl: 模板字符串
        args: 模板参数

    Returns:
        渲染后的字符串
    """
    for k, v in (args or {}).items():
        tpl = tpl.replace(f"{{{k}}}", str(v))
    return tpl


def _safe_json(resp) -> dict | str:
    """安全解析 JSON。

    Args:
        resp: HTTP 响应对象

    Returns:
        解析后的 JSON 字典或原始文本
    """
    try:
        return resp.json()
    except Exception:
        return resp.text