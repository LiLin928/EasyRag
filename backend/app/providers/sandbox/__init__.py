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

    # 使用 findings.md 推荐的镜像
    image = "python:3.10-alpine"

    # 创建沙箱
    sandbox = await client.create_sandbox(
        image=image,
        command=[
            "python", "-c",
            f"""
import json
import sys

# 注入输入参数
inputs = json.loads('{inputs_json}')

# 执行用户代码（传入全局命名空间）
try:
    # 创建全局命名空间，包含常用模块
    exec_globals = {{
        '__builtins__': __builtins__,
        'json': json,
        're': __import__('re'),
        'math': __import__('math'),
        'datetime': __import__('datetime'),
        'Counter': __import__('collections').Counter,
        'defaultdict': __import__('collections').defaultdict,
        'inputs': inputs,
        'result': None,
    }}

    # 执行代码
    exec({repr(code)}, exec_globals)

    # 提取结果
    result = exec_globals.get('result')
    if result is not None:
        print(json.dumps({{'success': True, 'output': result}}))
    else:
        print(json.dumps({{'success': True, 'output': None}}))
except Exception as e:
    import traceback
    print(json.dumps({{'success': False, 'error': str(e), 'traceback': traceback.format_exc()}}))
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
    # 日志是文本格式，我们的代码会在最后一行打印 JSON 结果
    try:
        import json

        # 从日志中提取 JSON 行
        stdout_text = logs.stdout if isinstance(logs.stdout, str) else str(logs.stdout)
        lines = stdout_text.strip().split('\n')

        # 找到最后一个包含 JSON 的行
        json_line = None
        for line in reversed(lines):
            line = line.strip()
            # 检查是否是 JSON 格式（包含 success 字段）
            if 'success' in line and '{' in line:
                try:
                    # 尝试提取 JSON 部分
                    start = line.index('{')
                    end = line.rindex('}') + 1
                    json_str = line[start:end]
                    # 验证是否是有效 JSON
                    json.loads(json_str)
                    json_line = json_str
                    break
                except:
                    continue

        if json_line:
            result_data = json.loads(json_line)
            return SandboxResult(
                ok=result_data.get("success", False),
                output=result_data.get("output"),
                error=result_data.get("error")
            )
        else:
            # 没有找到 JSON，返回原始输出
            return SandboxResult(
                ok=True,
                output={"raw_output": stdout_text},
                error=None
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