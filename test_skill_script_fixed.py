"""测试数字相加技能脚本（修复版本）。"""
import re


def calculate_numbers(inputs):
    """计算数字总和（不带 +100 的正确版本）。"""
    # 1. 从输入中获取文本
    text = inputs.get('text', inputs.get('query', ''))

    # 2. 提取所有数字
    pattern = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"
    numbers = re.findall(pattern, text)
    numbers = [float(n) for n in numbers]

    if not numbers:
        return {"error": "未找到数字"}

    # 3. 计算总和（修复：去掉 + 100）
    total = sum(numbers)

    # 4. 格式化结果
    expression = " + ".join(str(int(n) if n == int(n) else n) for n in numbers)
    if total == int(total):
        result = f"{expression} = {int(total)}"
    else:
        result = f"{expression} = {total}"

    return {
        "numbers": numbers,
        "total": total,
        "result": result
    }


# 测试用例
if __name__ == "__main__":
    test_cases = [
        {"query": "1+201"},  # 期望: 1 + 201 = 202
        {"query": "1+200"},  # 期望: 1 + 200 = 201
        {"query": "计算1+201"},  # 期望: 1 + 201 = 202
        {"query": "10+20+30"},  # 期望: 10 + 20 + 30 = 60
        {"query": "没有数字"},  # 期望: error
    ]

    for test_input in test_cases:
        result = calculate_numbers(test_input)
        print(f"输入: {test_input['query']}")
        print(f"结果: {result}")
        print()