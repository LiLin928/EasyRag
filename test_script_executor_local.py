"""直接测试脚本执行逻辑（不使用沙箱）"""
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.core.skills.script_executor import execute_skill_script


async def test_script_executor():
    """测试脚本执行器"""

    # 测试脚本
    script = """
# 数字相加计算脚本
import re

def main(inputs):
    # 1. 从输入中获取文本
    text = inputs.get('text', inputs.get('query', ''))

    # 2. 提取所有数字
    pattern = r"[-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?"
    numbers = re.findall(pattern, text)
    numbers = [float(n) for n in numbers]

    if not numbers:
        return {"error": "未找到数字"}

    # 3. 计算总和（加 100 测试）
    total = sum(numbers) + 100

    # 4. 格式化结果
    expression = " + ".join(str(n) for n in numbers)
    if total == int(total):
        result = f"{expression} = {int(total)}"
    else:
        result = f"{expression} = {total}"

    return {
        "numbers": numbers,
        "total": total,
        "result": result
    }
"""

    # 测试输入
    inputs = {"text": "计算 1+100", "query": "计算 1+100"}

    print("=" * 60)
    print("测试脚本执行器（本地模式）")
    print("=" * 60)
    print(f"输入: {inputs}")

    # 执行脚本
    result = await execute_skill_script(
        script_name="test.py",
        script_content=script,
        inputs=inputs,
        timeout=10,
    )

    print("\n执行结果:")
    print(f"成功: {result['success']}")
    print(f"输出: {result['output']}")
    print(f"错误: {result['error']}")

    # 验证结果
    if result['success'] and result['output']:
        output = result['output']
        if isinstance(output, dict):
            print("\n解析输出:")
            print(f"  数字: {output.get('numbers')}")
            print(f"  总和: {output.get('total')}")
            print(f"  结果: {output.get('result')}")

            # 检查是否正确
            if output.get('total') == 201:
                print("\n✓ 测试通过：正确计算了 1+100+100=201")
            else:
                print(f"\n✗ 测试失败：期望 201，得到 {output.get('total')}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_script_executor())