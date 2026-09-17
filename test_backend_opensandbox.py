"""
使用我们修复的后端代码测试 OpenSandbox

这个测试会：
1. 使用正确的 API 格式
2. 测试沙箱创建和代码执行
3. 测试技能脚本
"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.providers.sandbox import run_in_sandbox


async def test_backend_opensandbox():
    """使用后端代码测试"""

    print("=" * 80)
    print("使用后端代码测试 OpenSandbox")
    print("=" * 80)

    # 测试1: 简单代码执行
    print("\n[测试 1] 简单代码执行")
    print("-" * 80)

    code1 = """
result = "Hello from EasyRAG OpenSandbox"
"""

    try:
        result = await run_in_sandbox(
            code=code1,
            inputs={},
            timeout=60,
            memory_mb=256,
        )

        print(f"成功: {result.ok}")
        print(f"输出: {result.output}")
        print(f"错误: {result.error}")

        if result.ok:
            print("\n[OK] 测试 1 通过")
        else:
            print(f"\n[FAIL] 测试 1 失败: {result.error}")
            return False

    except Exception as e:
        print(f"\n[FAIL] 测试 1 异常: {e}")
        return False

    # 测试2: 数学计算（技能脚本）
    print("\n[测试 2] 数学计算脚本")
    print("-" * 80)

    code2 = """
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

    try:
        result = await run_in_sandbox(
            code=code2,
            inputs={"text": "计算 1+100", "query": "计算 1+100"},
            timeout=60,
            memory_mb=256,
        )

        print(f"成功: {result.ok}")
        print(f"输出: {result.output}")

        if result.ok and result.output:
            output = result.output
            if isinstance(output, dict):
                print(f"\n结果详情:")
                print(f"  数字: {output.get('numbers')}")
                print(f"  总和: {output.get('total')}")
                print(f"  算式: {output.get('result')}")

                if output.get('total') == 201:
                    print("\n[OK] 测试 2 通过：正确计算 1+100+100=201")
                    return True
                else:
                    print(f"\n[FAIL] 测试 2 失败：期望 201，得到 {output.get('total')}")
                    return False
        else:
            print(f"\n[FAIL] 测试 2 失败: {result.error}")
            return False

    except Exception as e:
        print(f"\n[FAIL] 测试 2 异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试流程"""
    result = await test_backend_opensandbox()

    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)

    if result:
        print("[成功] OpenSandbox 集成正常工作")
        print("技能脚本可以正确执行")
    else:
        print("[失败] 需要在虚拟机上构建兼容镜像")
        print("参考: BUILD_OPENSANDBOX_IMAGE.md")

    return result


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)