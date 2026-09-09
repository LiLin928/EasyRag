"""工具服务：从 DB 加载工具定义并委托执行器。

execute_tool 是 Plan 7 tool 节点和 Plan 9 agent tool_registry 的共享入口。
"""
from sqlalchemy import select

from app.core.tools.executor import execute
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.tool import Tool


async def execute_tool(tool_id: str, args: dict) -> dict:
    """按 ID 加载工具并执行，返回 {success, data, error, duration}。"""
    async with async_session() as s:
        t = (await s.execute(select(Tool).where(Tool.id == tool_id))).scalar_one_or_none()
    if not t:
        raise BizException(ErrorCode.NOT_FOUND, "工具不存在")
    if not t.enabled:
        raise BizException(ErrorCode.FORBIDDEN, "工具未启用")
    return await execute(t, args or {})


async def get_tool(tool_id: str) -> Tool | None:
    """加载工具 ORM（供 tool_registry 复用）。"""
    async with async_session() as s:
        return (await s.execute(select(Tool).where(Tool.id == tool_id))).scalar_one_or_none()
 
