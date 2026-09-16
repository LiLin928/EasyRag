"""Sandbox provider - OpenSandbox 集成"""
import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from app.providers.sandbox.opensandbox_client import get_opensandbox_client


@dataclass
class SandboxResult:
    """沙箱执行结果"""
    ok: bool
    output: Any
    error: Optional[str] = None


async def run_in_sandbox(
    code: str,
    inputs: dict,
    timeout: int = 30,
    memory_mb: int = 256,
) -> SandboxResult:
    """在 OpenSandbox 中执行 Python 代码

    Args:
        code: Python 代码字符串
        inputs: 输入参数（会注入为变量）
        timeout: 执行超时（秒）
        memory_mb: 内存限制（MB）

    Returns:
        SandboxResult: 执行结果
    """
    client = get_opensandbox_client()

    # 构造执行命令
    # 将 inputs 序列化为 JSON，通过环境变量或命令行传递
    import json
    inputs_json = json.dumps(inputs)

    # 创建沙箱
    sandbox = await client.create_sandbox(
        image="python:3.11-slim",
        command=[
            "python", "-c",
            f"""
import json
import sys

# 注入输入参数
inputs = json.loads('{inputs_json}')
globals().update(inputs)

# 执行用户代码
try:
    result = None
    exec({repr(code)}, {{'__builtins__': __builtins__, 'result': result}})
    if 'result' in dir():
        print(json.dumps({{'success': True, 'output': result}}))
    else:
        print(json.dumps({{'success': True, 'output': None}}))
except Exception as e:
    print(json.dumps({{'success': False, 'error': str(e)}}))
"""
        ],
        env={"PYTHONUNBUFFERED": "1"},
        memory_mb=memory_mb,
        timeout_seconds=timeout,
    )

    # 等待执行完成
    info = await client.wait_for_completion(sandbox.sandbox_id, timeout=timeout)

    # 获取日志
    logs = await client.get_logs(sandbox.sandbox_id)

    # 解析输出
    try:
        import json
        result_data = json.loads(logs.stdout)
        return SandboxResult(
            ok=result_data.get("success", False),
            output=result_data.get("output"),
            error=result_data.get("error")
        )
    except Exception as e:
        return SandboxResult(
            ok=False,
            output=None,
            error=f"解析输出失败: {str(e)}\n\nstdout: {logs.stdout}\nstderr: {logs.stderr}"
        )
    finally:
        # 清理沙箱
        try:
            await client.delete_sandbox(sandbox.sandbox_id)
        except Exception:
            pass