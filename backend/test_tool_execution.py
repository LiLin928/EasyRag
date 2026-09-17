"""测试技能工具执行逻辑。"""
import asyncio
import json
from app.models.skill import Skill
from app.core.agent.skill_tool_executor import create_skill_tool_with_scripts
from sqlalchemy import select
from app.db.session import async_session


async def test():
    skill_id = "2e35ee7a-5504-475a-8fa4-b568f0e760d1"

    async with async_session() as session:
        result = await session.execute(
            select(Skill).where(Skill.id == skill_id)
        )
        skill = result.scalar_one_or_none()

        if skill:
            print(f"Skill: {skill.name}")
            print(f"Scripts: {len(skill.scripts or [])}")

            # 创建工具
            tool = create_skill_tool_with_scripts(skill)
            print(f"\nTool name: {tool.name}")
            print(f"Tool description: {tool.description}")
            print(f"Tool args schema: {tool.args_schema}")

            # 测试执行
            print(f"\n=== Testing tool execution ===")
            result = await tool.ainvoke({"query": "1+200"})
            print(f"\nResult: {result}")


asyncio.run(test())
