"""验证技能脚本是否真的被执行。"""
import re


def main(inputs):
    """
    主函数：从输入中提取数字并计算总和（故意加100来验证执行）
    """
    # 1. 从输入中获取文本
    text = inputs.get('text', inputs.get('query', ''))

    # 2. 提取所有数字
    pattern = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"
    numbers = re.findall(pattern, text)
    numbers = [float(n) for n in numbers]

    if not numbers:
        return {"error": "未找到数字"}

    # 3. 计算总和（故意加 100 来验证脚本执行）
    total = sum(numbers) + 100

    # 4. 格式化结果
    expression = " + ".join(str(int(n) if n == int(n) else n) for n in numbers)
    if total == int(total):
        result = f"{expression} = {int(total)}"
    else:
        result = f"{expression} = {total}"

    return {
        "numbers": numbers,
        "sum_of_numbers": sum(numbers),
        "bonus": 100,
        "total": total,
        "result": result,
        "verification": "如果看到这个返回值，说明技能脚本真的被执行了！"
    }


# 测试
if __name__ == "__main__":
    test_cases = [
        {"query": "1+200"},
        {"query": "1+201"},
        {"query": "计算1+200"},
    ]

    for test_input in test_cases:
        result = main(test_input)
        print(f"输入: {test_input['query']}")
        print(f"数字: {result['numbers']}")
        print(f"数字和: {result['sum_of_numbers']}")
        print(f"加100: {result['bonus']}")
        print(f"最终结果: {result['total']}")
        print(f"显示: {result['result']}")
        print(f"验证: {result['verification']}")
        print()