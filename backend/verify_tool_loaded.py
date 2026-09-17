import asyncio
from app.models.agent import Agent
from app.core.agent.tool_registry_lazy import build_tools
from sqlalchemy import select
from app.db.session import async_session


async def verify():
    agent_id = "545d7c33-0a98-4af6-afc3-f73b0f282efb"

    async with async_session() as session:
        result = await session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()

        if agent:
            print(f"Agent: {agent.name}")
            print(f"Skills: {agent.skills}")

            # Build tools
            tools = await build_tools(agent)
            print(f"\nTotal tools: {len(tools)}")

            for idx, tool in enumerate(tools):
                print(f"\nTool {idx + 1}:")
                print(f"  Name: {tool.name}")
                print(f"  Description: {tool.description[:200] if tool.description else 'None'}")

                # Check if it's a skill tool
                if tool.name.startswith("skill_"):
                    print(f"  [SKILL TOOL]")

                # Try to get tool schema
                if hasattr(tool, 'args_schema') and tool.args_schema:
                    print(f"  Args: {tool.args_schema.model_fields.keys()}")


asyncio.run(verify())
