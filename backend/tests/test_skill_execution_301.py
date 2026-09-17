"""测试技能执行（验证 301 重定向修复）。"""
import asyncio

import pytest

from app.core.skills.script_executor import execute_skill_script


@pytest.mark.asyncio
async def test_skill_execution_no_301():
    """测试技能脚本执行不会触发 301 错误。"""

    # 简单的计算脚本
    script = """
def main(inputs):
    a = inputs.get('a', 0)
    b = inputs.get('b', 0)
    result = a + b
    return {"result": result, "message": f"计算结果: {a} + {b} = {result}"}
"""

    inputs = {"a": 1, "b": 200}

    try:
        result = await execute_skill_script(
            script_name="test_calculator",
            script_content=script,
            inputs=inputs,
            timeout=30,
            memory_mb=256,
        )

        print(f"[PASS] Script execution result: {result}")

        # Verify execution success
        assert result["success"] is True, f"Execution failed: {result.get('error')}"
        assert result["output"]["result"] == 201, "Incorrect calculation result"
        assert result["error"] is None

        print(f"[PASS] Test passed: 1 + 200 = {result['output']['result']}")

    except Exception as e:
        # 如果错误信息中包含 301，说明重定向处理仍有问题
        error_msg = str(e)
        assert "301" not in error_msg, f"未正确处理 301 重定向: {error_msg}"
        raise


if __name__ == "__main__":
    # 直接运行测试
    asyncio.run(test_skill_execution_no_301())