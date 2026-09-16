"""修复技能脚本 - 让脚本可以正确执行

问题：当前脚本只定义了函数，但没有执行逻辑。
修复：添加一个 main() 函数，将所有步骤串联起来。
"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from sqlalchemy import select
from app.db.session import async_session
from app.models.skill import Skill


async def fix_skill_scripts():
    """修复技能脚本，添加执行逻辑"""

    skill_id = "2e35ee7a-5504-475a-8fa4-b568f0e760d1"

    async with async_session() as s:
        skill = (await s.execute(
            select(Skill).where(Skill.id == skill_id)
        )).scalar_one_or_none()

        if not skill:
            print("技能不存在")
            return

        print(f"技能名称：{skill.name}")
        print(f"当前脚本数量：{len(skill.scripts or [])}")

        # 修复脚本：将所有逻辑合并到一个可执行的脚本中
        fixed_scripts = [
            {
                "name": "数字相加计算.py",
                "content": """# 数字相加计算脚本
import re

def main(inputs):
    \"\"\"
    主函数：从输入中提取数字并计算总和

    Args:
        inputs: 包含用户查询的字典 {"text": "...", "query": "..."}

    Returns:
        计算结果字符串
    \"\"\"
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
            }
        ]

        skill.scripts = fixed_scripts
        await s.commit()

        print("\n[OK] 技能脚本已修复")
        print("\n修复内容：")
        print("  1. 将三个分离的脚本合并为一个完整脚本")
        print("  2. 添加 main() 函数作为执行入口")
        print("  3. 保留 +100 的测试逻辑")
        print("\n预期结果：")
        print("  输入: 计算 1+100")
        print("  输出: 1 + 100 = 201")


if __name__ == "__main__":
    asyncio.run(fix_skill_scripts())