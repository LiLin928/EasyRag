"""
调试脚本执行
"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.core.skills.script_executor import execute_skill_script


async def debug_script_execution():
    """调试脚本执行"""

    script = """
import re

def main(inputs):
    text = inputs.get('text', inputs.get('query', ''))

    # 提取数字
    pattern = r"[-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?"
    numbers = re.findall(pattern, text)
    numbers = [float(n) for n in numbers]

    if not numbers:
        return {"error": "未找到数字"}

    # 计算总和（加 100 测试）
    total = sum(numbers) + 100

    # 格式化结果
    expression = " + ".join(str(n) for n in numbers)
    result = f"{expression} = {int(total)}"

    return {
        "numbers": numbers,
        "total": total,
        "result": result
    }
"""

    inputs = {"text": "计算 1+100", "query": "计算 1+100"}

    print("=" * 80)
    print("调试脚本执行")
    print("=" * 80)

    result = await execute_skill_script(
        script_name="test.py",
        script_content=script,
        inputs=inputs,
        timeout=60,
        memory_mb=256,
    )

    print(f"\n执行结果:")
    print(f"成功: {result['success']}")
    print(f"输出: {result['output']}")
    print(f"错误: {result['error']}")


if __name__ == "__main__":
    asyncio.run(debug_script_execution())