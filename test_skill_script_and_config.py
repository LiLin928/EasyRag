"""测试技能脚本执行和配置保存"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.agent_service import AgentService

async def test_skill_script_execution():
    """测试技能脚本是否正确执行"""
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"
    user_id = "0102ea2f-16cb-4029-b863-3807c213f148"

    tests = [
        "计算 1+100",
        "计算 123+456",
    ]

    svc = AgentService()

    for question in tests:
        print(f"\n{'='*60}")
        print(f"问题：{question}")
        print('='*60)

        has_tool = False
        has_script_result = False

        async for event in svc.chat(agent_id, question, user_id):
            if event.startswith("event: tool_start"):
                has_tool = True
                print("[工具调用] 技能已激活")
            elif event.startswith("event: tool_end"):
                # 检查是否包含脚本执行结果
                if "脚本执行结果" in event or "output" in event:
                    has_script_result = True
                    print("[脚本执行] 检测到脚本执行结果")
            elif event.startswith("event: token"):
                pass

        if has_tool and has_script_result:
            print("\n✅ 测试通过：技能脚本已执行")
        elif has_tool:
            print("\n⚠️  部分通过：技能已激活但脚本未执行")
        else:
            print("\n❌ 测试失败：技能未激活")

async def test_config_persistence():
    """测试配置保存是否完整"""
    import json
    from sqlalchemy import select
    from app.db.session import async_session
    from app.models.agent import Agent

    async with async_session() as s:
        agent = (await s.execute(
            select(Agent).where(Agent.id == "545d7c33-0a98-4af6-afc3-f73b0f282efb")
        )).scalar_one_or_none()

        if not agent:
            print("❌ 智能体不存在")
            return

        print("\n" + "="*60)
        print("智能体配置检查")
        print("="*60)

        config = {
            "name": agent.name,
            "model": agent.model,
            "tools": agent.tools,
            "mcps": agent.mcps,
            "skills": agent.skills,
            "docs": agent.docs,
            "wfs": agent.wfs,
        }

        print(json.dumps(config, indent=2, ensure_ascii=False))

        # 检查数据完整性
        issues = []

        if not agent.tools:
            issues.append("工具列表为空")
        if not agent.mcps:
            issues.append("MCP列表为空")
        if not agent.skills:
            issues.append("技能列表为空")

        if issues:
            print("\n⚠️  配置问题：")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("\n✅ 配置完整")

if __name__ == "__main__":
    print("测试1：技能脚本执行")
    asyncio.run(test_skill_script_execution())

    print("\n\n" + "="*60)
    print("测试2：配置持久化")
    asyncio.run(test_config_persistence())