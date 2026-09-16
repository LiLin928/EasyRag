"""直接测试脚本逻辑（本地 exec）"""
import json


def test_script_logic():
    """测试脚本逻辑（本地执行）"""

    # 脚本代码
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

    # 输入
    inputs = {"text": "计算 1+100", "query": "计算 1+100"}

    # 创建执行命名空间
    exec_globals = {
        '__builtins__': __builtins__,
        'json': json,
        're': __import__('re'),
        'math': __import__('math'),
        'inputs': inputs,
        'result': None,
    }

    # 执行脚本
    exec(script, exec_globals)

    # 调用 main 函数
    if 'main' in exec_globals:
        result = exec_globals['main'](inputs)
        print("=" * 60)
        print("测试脚本逻辑（本地执行）")
        print("=" * 60)
        print(f"输入: {inputs}")
        print(f"\n执行结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # 验证结果
        if result.get('total') == 201:
            print("\n✓ 测试通过：正确计算了 1+100+100=201")
        else:
            print(f"\n✗ 测试失败：期望 201，得到 {result.get('total')}")
    else:
        print("错误：脚本中没有定义 main 函数")


if __name__ == "__main__":
    test_script_logic()