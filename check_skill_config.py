"""检查技能脚本配置"""
import asyncio
import sys
import json
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from sqlalchemy import select
from app.db.session import async_session
from app.models.skill import Skill
from app.models.agent import Agent


async def check_skill_config():
    """检查技能和智能体配置"""

    async with async_session() as s:
        # 检查智能体配置
        agent = (await s.execute(
            select(Agent).where(Agent.id == "545d7c33-0a98-4af6-afc3-f73b0f282efb")
        )).scalar_one_or_none()

        if not agent:
            print("智能体不存在")
            return

        print("=" * 60)
        print("智能体配置")
        print("=" * 60)
        print(f"名称：{agent.name}")
        print(f"技能ID列表：{agent.skills}")

        # 检查技能详情
        if agent.skills:
            for skill_id in agent.skills:
                skill = (await s.execute(
                    select(Skill).where(Skill.id == skill_id)
                )).scalar_one_or_none()

                if skill:
                    print(f"\n{'='*60}")
                    print(f"技能：{skill.name}")
                    print("=" * 60)
                    print(f"ID：{skill.id}")
                    print(f"描述：{skill.description}")
                    print(f"触发条件：{skill.trigger}")
                    print(f"\nPrompt：\n{skill.prompt}")
                    print(f"\n脚本数量：{len(skill.scripts or [])}")

                    if skill.scripts:
                        print("\n脚本详情：")
                        for idx, script in enumerate(skill.scripts):
                            print(f"\n--- 脚本 {idx + 1}: {script.get('name', 'unnamed')} ---")
                            print(script.get('content', ''))
                else:
                    print(f"\n❌ 技能 {skill_id} 不存在")


if __name__ == "__main__":
    asyncio.run(check_skill_config())