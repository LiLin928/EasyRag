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
            tool = create_skill_tool_with_scripts(skill)
            
            # Test with query
            result = await tool.ainvoke({"query": "1+200"})
            
            # Extract numbers from result
            if "301" in str(result):
                print("[SUCCESS] Tool returned 301")
            elif "201" in str(result):
                print("[FAILED] Tool returned 201")
            
            # Save result to file
            with open("tool_result.txt", "w", encoding="utf-8") as f:
                f.write(result)
            print("Result saved to tool_result.txt")


asyncio.run(test())
