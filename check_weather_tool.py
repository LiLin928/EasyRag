import asyncio
from app.models.tool import Tool
from sqlalchemy import select
from app.db.session import async_session


async def check():
    tool_id = "6b92349d-99a7-47f4-91d4-7006e37716b6"

    async with async_session() as session:
        result = await session.execute(
            select(Tool).where(Tool.id == tool_id)
        )
        tool = result.scalar_one_or_none()

        if tool:
            print(f"Tool Name: {tool.name}")
            print(f"Tool Description: {tool.description}")
            print(f"Tool Type: {tool.type}")
            print(f"Tool Config: {tool.config}")
            print(f"\nTool Params:")
            for param in (tool.params or []):
                print(f"  - {param.get('n')}: {param.get('d', 'no description')}")


asyncio.run(check())
