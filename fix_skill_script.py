"""修复技能脚本中的bug"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from sqlalchemy import select
from app.db.session import async_session
from app.models.skill import Skill

async def fix_skill():
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

        # 修复脚本
        fixed_scripts = [
            {
                "name": "数字提取器.py",
                "content": """# 从用户输入中提取所有数字
import re

def extract_numbers(text):
    \"\"\"从文本中提取所有数字（支持整数、小数、科学计数法）\"\"\"
    pattern = r"[-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?"
    numbers = re.findall(pattern, text)
    return [float(n) for n in numbers]

# 使用示例
# input_text = "计算 123, 45.6 和 -7.89 的和"
# numbers = extract_numbers(input_text)
# print(numbers)  # [123.0, 45.6, -7.89]"""
            },
            {
                "name": "求和计算.py",
                "content": """# 计算数字列表的总和
def calculate_sum(numbers):
    \"\"\"
    计算数字列表的总和

    Args:
        numbers: 数字列表 [1, 2, 3.5, ...]

    Returns:
        总和（float类型）
    \"\"\"
    if not numbers:
        return 0

    total = sum(numbers)  # 修复：移除了错误的 +100

    # 如果结果是整数，返回整数格式
    if total == int(total):
        return int(total)

    return total

# 使用示例
# numbers = [1, 2, 3, 4.5]
# result = calculate_sum(numbers)
# print(f"总和: {result}")  # 总和: 10.5"""
            }
        ]

        skill.scripts = fixed_scripts
        await s.commit()

        print("\n✅ 技能脚本已修复")
        print("修复内容：")
        print("  - 移除了错误的 `sum(numbers+100)`")
        print("  - 改为正确的 `sum(numbers)`")

if __name__ == "__main__":
    asyncio.run(fix_skill())