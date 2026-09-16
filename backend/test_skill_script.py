"""测试技能脚本执行器"""
import asyncio
from app.core.skills.script_executor import execute_skill_script


async def test_examples():
    """测试各种脚本场景"""

    print("=" * 60)
    print("测试1: 简单计算脚本")
    print("=" * 60)

    result = await execute_skill_script(
        script_name="simple_calc.py",
        script_content="""
def main(inputs):
    a = inputs.get('a', 0)
    b = inputs.get('b', 0)
    return a + b
""",
        inputs={"a": 10, "b": 20}
    )

    print(f"结果: {result}")
    print(f"成功: {result['success']}")
    print(f"输出: {result['output']}")

    print("\n" + "=" * 60)
    print("测试2: 数据处理脚本")
    print("=" * 60)

    result = await execute_skill_script(
        script_name="data_process.py",
        script_content="""
def run(inputs):
    data = inputs.get('data', [])
    return {
        'count': len(data),
        'sum': sum(data),
        'avg': sum(data) / len(data) if data else 0
    }
""",
        inputs={"data": [1, 2, 3, 4, 5]}
    )

    print(f"结果: {result}")

    print("\n" + "=" * 60)
    print("测试3: 错误处理")
    print("=" * 60)

    result = await execute_skill_script(
        script_name="error_test.py",
        script_content="""
def main(inputs):
    raise ValueError("这是一个测试错误")
""",
        inputs={}
    )

    print(f"成功: {result['success']}")
    print(f"错误: {result['error']}")


if __name__ == "__main__":
    asyncio.run(test_examples())