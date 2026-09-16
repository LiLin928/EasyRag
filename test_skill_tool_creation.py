"""检查技能脚本是否被正确加载和执行"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.core.agent.skill_tool_executor import create_skill_tool_with_scripts
from sqlalchemy import select
from app.db.session import async_session
from app.models.skill import Skill


async def test_skill_tool_creation():
    """测试技能工具创建"""

    skill_id = "2e35ee7a-5504-475a-8fa4-b568f0e760d1"

    async with async_session() as s:
        skill = (await s.execute(
            select(Skill).where(Skill.id == skill_id)
        )).scalar_one_or_none()

        if not skill:
            print("技能不存在")
            return

        print(f"技能名称：{skill.name}")
        print(f"脚本数量：{len(skill.scripts or [])}")

        if skill.scripts:
            for idx, script in enumerate(skill.scripts):
                print(f"\n--- 脚本 {idx + 1} ---")
                print(f"名称：{script.get('name', 'unnamed')}")
                content = script.get('content', '')
                print(f"内容长度：{len(content)} 字符")
                print(f"前 200 字符：{content[:200]}")

        # 创建技能工具
        print("\n" + "=" * 60)
        print("创建技能工具")
        print("=" * 60)

        tool = create_skill_tool_with_scripts(skill)
        print(f"工具名称：{tool.name}")
        print(f"工具描述：{tool.description}")

        # 测试执行
        print("\n" + "=" * 60)
        print("测试执行技能工具")
        print("=" * 60)

        try:
            result = await tool.ainvoke({"query": "计算 1+100"})
            # 过滤非 ASCII 字符
            result_ascii = ''.join(c if ord(c) < 128 else '?' for c in str(result))
            print(f"\n工具返回:\n{result_ascii}")
        except Exception as e:
            print(f"\n执行失败: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_skill_tool_creation())