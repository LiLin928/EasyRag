"""直接测试技能脚本执行。"""
import asyncio
import json


# 脚本内容（从数据库中复制）
script_content = """
import re

def main(inputs):
    text = inputs.get('text', inputs.get('query', ''))
    pattern = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"
    numbers = re.findall(pattern, text)
    numbers = [float(n) for n in numbers]

    if not numbers:
        return {"error": "No numbers found"}

    total = sum(numbers) + 100

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


async def test():
    from app.core.skills.script_executor import execute_skill_script

    result = await execute_skill_script(
        script_name="test_calculator",
        script_content=script_content,
        inputs={"text": "1+200", "query": "1+200"},
        timeout=30,
        memory_mb=256,
    )

    print(f"Result: {json.dumps(result, indent=2)}")

    if result["success"]:
        output = result["output"]
        print(f"\nNumbers: {output['numbers']}")
        print(f"Sum: {sum(output['numbers'])}")
        print(f"Total (with +100): {output['total']}")
        print(f"Result: {output['result']}")

        if output['total'] == 301:
            print("\n[SUCCESS] Script executed correctly, returned 301!")
        else:
            print(f"\n[FAILED] Expected 301, got {output['total']}")
    else:
        print(f"\n[ERROR] {result['error']}")


asyncio.run(test())