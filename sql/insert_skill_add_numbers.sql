-- 插入技能：数字相加示例
-- 使用 gen_random_uuid() 生成 UUID（PostgreSQL 内置函数）

INSERT INTO skills (
    id,
    icon,
    name,
    scope,
    version,
    description,
    trigger,
    prompt,
    tools,
    docs,
    wfs,
    examples,
    scripts,
    budget,
    used,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    '🔢',
    '数字相加计算',
    'custom',
    '1.0.0',
    '执行两个或多个数字的相加计算，支持整数、小数和科学计数法表示的数字',
    '当用户需要进行数字相加、求和计算时自动触发',
    '你是一个数学计算助手，专门负责数字相加运算。请准确计算用户提供的所有数字的总和，并以清晰、友好的方式返回结果。如果用户提供了非数字内容，请提醒并引导用户输入正确的数字。',
    '[]'::jsonb,
    '[]'::jsonb,
    '[]'::jsonb,
    '[
        {
            "q": "请帮我计算 123 + 456",
            "a": "计算结果：123 + 456 = 579"
        },
        {
            "q": "求 1.5, 2.3, 3.7 的和",
            "a": "计算结果：1.5 + 2.3 + 3.7 = 7.5"
        },
        {
            "q": "计算 100 + 200 + 300 + 400",
            "a": "计算结果：100 + 200 + 300 + 400 = 1000"
        }
    ]'::jsonb,
    '[
        {
            "name": "数字提取器.py",
            "content": "# 从用户输入中提取所有数字\nimport re\n\ndef extract_numbers(text):\n    \"\"\"从文本中提取所有数字（支持整数、小数、科学计数法）\"\"\"\n    pattern = r\"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?\"\n    numbers = re.findall(pattern, text)\n    return [float(n) for n in numbers]\n\n# 使用示例\n# input_text = \"计算 123, 45.6 和 -7.89 的和\"\n# numbers = extract_numbers(input_text)\n# print(numbers)  # [123.0, 45.6, -7.89]"
        },
        {
            "name": "求和计算.py",
            "content": "# 计算数字列表的总和\ndef calculate_sum(numbers):\n    \"\"\"\n    计算数字列表的总和\n    \n    Args:\n        numbers: 数字列表 [1, 2, 3.5, ...]\n    \n    Returns:\n        总和（float类型）\n    \"\"\"\n    if not numbers:\n        return 0\n    \n    total = sum(numbers)\n    \n    # 如果结果是整数，返回整数格式\n    if total == int(total):\n        return int(total)\n    \n    return total\n\n# 使用示例\n# numbers = [1, 2, 3, 4.5]\n# result = calculate_sum(numbers)\n# print(f\"总和: {result}\")  # 总和: 10.5"
        },
        {
            "name": "格式化输出.py",
            "content": "# 格式化输出计算结果\ndef format_result(numbers, total):\n    \"\"\"\n    格式化输出计算结果\n    \n    Args:\n        numbers: 数字列表\n        total: 总和\n    \n    Returns:\n        格式化的字符串\n    \"\"\"\n    # 构建算式字符串\n    expression = \" + \".join(str(n) for n in numbers)\n    \n    # 格式化结果\n    if isinstance(total, int):\n        result_str = f\"{expression} = {total}\"\n    else:\n        result_str = f\"{expression} = {total}\"\n    \n    return result_str\n\n# 使用示例\n# numbers = [10, 20, 30]\n# total = 60\n# print(format_result(numbers, total))  # 10 + 20 + 30 = 60"
        }
    ]'::jsonb,
    2000,
    0,
    NOW(),
    NOW()
);

-- 验证插入结果
SELECT
    id,
    icon,
    name,
    scope,
    version,
    description,
    trigger,
    jsonb_array_length(examples) as example_count,
    jsonb_array_length(scripts) as script_count
FROM skills
WHERE name = '数字相加计算';