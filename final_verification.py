"""
最终验证：完整技能脚本执行测试

这个测试验证：
1. OpenSandbox 沙箱创建和执行
2. 技能脚本正确执行
3. "最后多加100"测试逻辑正确
"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.core.skills.script_executor import execute_skill_script


async def final_verification():
    """最终验证"""

    print("=" * 80)
    print("最终验证：技能脚本执行")
    print("=" * 80)

    # 技能脚本
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

    # 测试用例
    test_cases = [
        {
            "name": "测试1: 计算 1+100",
            "input": "计算 1+100",
            "expected_numbers": [1.0, 100.0],
            "expected_total": 201.0,
        },
        {
            "name": "测试2: 计算 123+456",
            "input": "计算 123+456",
            "expected_numbers": [123.0, 456.0],
            "expected_total": 679.0,  # 123+456+100
        },
    ]

    all_passed = True

    for test in test_cases:
        print(f"\n{test['name']}")
        print("-" * 80)

        result = await execute_skill_script(
            script_name="test.py",
            script_content=script,
            inputs={"text": test['input'], "query": test['input']},
            timeout=60,
            memory_mb=256,
        )

        print(f"输入: {test['input']}")
        print(f"成功: {result['success']}")

        if result['success'] and result['output']:
            output = result['output']
            print(f"数字: {output.get('numbers')}")
            print(f"总和: {output.get('total')}")
            print(f"结果: {output.get('result')}")

            # 验证结果
            if output.get('numbers') == test['expected_numbers']:
                print("✓ 数字提取正确")
            else:
                print(f"✗ 数字提取错误，期望 {test['expected_numbers']}")
                all_passed = False

            if output.get('total') == test['expected_total']:
                print("✓ 计算结果正确")
            else:
                print(f"✗ 计算结果错误，期望 {test['expected_total']}")
                all_passed = False
        else:
            print(f"✗ 执行失败: {result['error']}")
            all_passed = False

    # 总结
    print("\n" + "=" * 80)
    print("最终验证结果")
    print("=" * 80)

    if all_passed:
        print("\n✅ 所有测试通过")
        print("\n验证内容:")
        print("  1. OpenSandbox 沙箱创建和执行 ✓")
        print("  2. 技能脚本正确执行 ✓")
        print("  3. '最后多加100'测试逻辑正确 ✓")
        print("\n技能脚本执行功能完全正常！")
        return True
    else:
        print("\n❌ 部分测试失败")
        return False


if __name__ == "__main__":
    result = asyncio.run(final_verification())
    sys.exit(0 if result else 1)