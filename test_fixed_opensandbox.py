"""测试修复后的 OpenSandbox API"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.providers.sandbox import run_in_sandbox


async def test_fixed_opensandbox():
    """测试修复后的 OpenSandbox API"""

    # 简单的测试脚本
    code = """
result = {"message": "Hello from OpenSandbox!", "number": 42}
"""

    print("=" * 60)
    print("测试修复后的 OpenSandbox API")
    print("=" * 60)

    try:
        result = await run_in_sandbox(
            code=code,
            inputs={},
            timeout=30,
            memory_mb=256,
        )

        print(f"\n执行结果:")
        print(f"成功: {result.ok}")
        print(f"输出: {result.output}")
        print(f"错误: {result.error}")

        if result.ok and result.output:
            print("\n✓ 测试通过：OpenSandbox API 正常工作")
        else:
            print(f"\n✗ 测试失败")

    except Exception as e:
        print(f"\n✗ 异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_fixed_opensandbox())