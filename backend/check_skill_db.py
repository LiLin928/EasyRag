"""直接查询数据库中的技能脚本。"""
import asyncio
import json
from sqlalchemy import select, text
from app.db.session import async_session
from app.models.skill import Skill


async def check_skill_scripts():
    skill_id = "2e35ee7a-5504-475a-8fa4-b568f0e760d1"

    async with async_session() as session:
        # 查询技能
        result = await session.execute(
            select(Skill).where(Skill.id == skill_id)
        )
        skill = result.scalar_one_or_none()

        if skill:
            print(f"Skill Name: {skill.name}")
            print(f"Skill Description: {skill.description}")
            print(f"Skill Prompt: {skill.prompt}")
            print(f"\nScripts: {len(skill.scripts or [])}")

            for idx, script in enumerate(skill.scripts or []):
                print(f"\n=== Script {idx + 1} ===")
                print(f"Name: {script.get('name')}")
                print(f"Content:\n{script.get('content')}")
        else:
            print(f"Skill not found: {skill_id}")


if __name__ == "__main__":
    asyncio.run(check_skill_scripts())