"""测试沙箱环境中的模块导入"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.providers.sandbox import run_in_sandbox


async def test_sandbox_imports():
    """测试沙箱环境中的模块导入"""

    # 测试1: 简单的导入测试
    print("=" * 60)
    print("测试1: 简单的导入测试")
    print("=" * 60)

    code1 = """
import json
result = {"test": "ok"}
"""
    result1 = await run_in_sandbox(code1, {}, timeout=10)
    print(f"结果: {result1}")

    # 测试2: 不导入，直接使用
    print("\n" + "=" * 60)
    print("测试2: 直接使用 json（不导入）")
    print("=" * 60)

    code2 = """
result = {"test": "ok"}
"""
    result2 = await run_in_sandbox(code2, {}, timeout=10)
    print(f"结果: {result2}")

    # 测试3: 使用全局提供的 json
    print("\n" + "=" * 60)
    print("测试3: 使用全局提供的 json")
    print("=" * 60)

    code3 = """
result = json.dumps({"test": "ok"})
"""
    result3 = await run_in_sandbox(code3, {}, timeout=10)
    print(f"结果: {result3}")


if __name__ == "__main__":
    asyncio.run(test_sandbox_imports())