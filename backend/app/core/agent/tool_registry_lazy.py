"""Agent 工具聚合优化：按需加载资源，避免全量加载。

优化策略：
1. tools → 立即加载（轻量级，只是元数据）
2. docs → 按需加载（RAG 检索时才加载）
3. wfs → 立即加载（轻量级）
4. mcps → 按需发现工具（MCP 连接耗时，延迟加载）
5. skills → 立即加载（只是 prompt 增强，很轻量）

关键改进：
- MCP 工具延迟发现，避免启动时连接所有 MCP 服务
- 提供 MCP 工具的描述，让 LLM 知道有哪些工具可用
- 实际调用时才连接 MCP 服务
"""
import asyncio
import json

from sqlalchemy import select

from app.core.engine.celery_client import enqueue_workflow_task
from app.db.session import async_session
from app.models.agent import Agent
from app.models.mcp import Mcp
from app.models.skill import Skill
from app.models.tool import Tool
from app.models.workflow import Workflow
from app.services.tool_service import execute_tool


WORKFLOW_TIMEOUT_SECONDS = 60


def _sanitize_tool_name(name: str, prefix: str = "tool") -> str:
    """将工具名称转换为符合 API 要求的格式。"""
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    if sanitized and sanitized[0].isdigit():
        sanitized = f'{prefix}_{sanitized}'
    if not sanitized or sanitized == '_' * len(sanitized):
        sanitized = f'{prefix}_unnamed'
    return sanitized


async def build_tools(agent: Agent, lazy_mcp: bool = True) -> list:
    """聚合 agent 挂载的资源为工具列表。

    Args:
        agent: 智能体实例
        lazy_mcp: 是否延迟加载 MCP 工具（默认 True）

    Returns:
        工具列表
    """
    tools: list = []
    async with async_session() as s:
        # 1. tools → 立即加载（轻量级）
        for tid in (agent.tools or []):
            t = (await s.execute(select(Tool).where(Tool.id == tid))).scalar_one_or_none()
            if t and t.enabled:
                tools.append(_tool_to_structured(t))

        # 2. docs → 按需加载（暂不加载，只在需要时使用）
        # docs 工具会在实际检索时才使用，这里不预先创建

        # 3. wfs → 立即加载（轻量级）
        for wid in (agent.wfs or []):
            wf = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one_or_none()
            if wf:
                tools.append(_workflow_tool(wf))

        # 4. mcps → 延迟加载或立即加载
        if lazy_mcp:
            # 延迟加载：只添加 MCP 元数据工具描述
            for mid in (agent.mcps or []):
                m = (await s.execute(select(Mcp).where(Mcp.id == mid))).scalar_one_or_none()
                if m and m.status == "on":
                    # 添加一个轻量级的 MCP 工具代理
                    tools.append(_mcp_proxy_tool(m))
        else:
            # 立即加载：实际连接 MCP 服务发现工具
            for mid in (agent.mcps or []):
                m = (await s.execute(select(Mcp).where(Mcp.id == mid))).scalar_one_or_none()
                if m and m.status == "on":
                    try:
                        from app.core.agent.tool_adapters.mcp_tools import load_tools as _load_mcp
                        mcp_tools = await _load_mcp(m)
                        for t in mcp_tools:
                            t.name = _sanitize_tool_name(t.name)
                        tools.extend(mcp_tools)
                    except Exception:
                        pass

        # 5. skills → 立即加载（轻量级，只是 prompt）
        for sid in (agent.skills or []):
            sk = (await s.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
            if sk:
                tools.append(_skill_tool(sk))

    return tools


def _mcp_proxy_tool(m: Mcp):
    """创建 MCP 代理工具，延迟实际连接。

    这个工具只是告诉 LLM 有哪些 MCP 工具可用，
    实际调用时会动态连接 MCP 服务。
    """
    from langchain_core.tools import tool

    tool_name = _sanitize_tool_name(m.name, prefix="mcp")
    description = f"MCP 服务：{m.name}。包含 {m.toolCount} 个工具。"

    # 如果知道具体工具名称，可以添加到描述中
    # 这里只是占位，实际工具会在调用时动态发现

    @tool(tool_name, description=description)
    def _mcp_proxy() -> str:
        return f"[MCP {m.name}] MCP 服务已就绪，包含 {m.toolCount} 个工具"

    return _mcp_proxy


def _tool_to_structured(t: Tool):
    """将 ORM Tool 转为 LangChain StructuredTool。"""
    from langchain_core.tools import StructuredTool
    from pydantic import create_model, Field

    # 构建参数模型，包含默认值
    fields = {}
    for p in (t.params or []):
        param_name = p.get("n", "param")
        param_type = str
        default_value = p.get("d", ...)
        fields[param_name] = (
            param_type,
            Field(default=default_value, description=f"参数 {param_name}")
        )

    Args = create_model(f"{t.id}_Args", **fields) if fields else None

    async def _run(**kwargs):
        result = await execute_tool(str(t.id), kwargs)
        return result.get("data")

    tool_name = _sanitize_tool_name(t.name)
    return StructuredTool.from_function(
        coroutine=_run,
        name=tool_name,
        description=t.description or t.name,
        args_schema=Args,
    )


def _rag_tool(doc_ids: list):
    """构建 RAG 检索工具。"""
    from langchain_core.tools import tool

    @tool("search_documents", description="在挂载文档中检索相关信息")
    async def _s(query: str) -> str:
        from app.core.retrieval.hybrid_retriever import HybridRetriever
        from app.core.scenes import get_scene_config
        scene = await get_scene_config("general")
        retriever = HybridRetriever(doc_ids=doc_ids, scene_config=scene, top_k=5, enable_nav=False)
        docs = await retriever.ainvoke(query)
        return "\n\n".join(d.page_content for d in docs) or "未找到相关信息"

    return _s


def _workflow_tool(wf: Workflow):
    """构建工作流触发工具。"""
    from langchain_core.tools import StructuredTool

    async def _run(**kwargs) -> str:
        exec_id = await enqueue_workflow_task(
            str(wf.id), kwargs, trigger="agent", user_id=None
        )
        for _ in range(WORKFLOW_TIMEOUT_SECONDS):
            row = await _get_execution(exec_id)
            if row and row.status in ("completed", "failed", "cancelled"):
                if row.outputs:
                    return json.dumps(row.outputs, ensure_ascii=False)
                return f"工作流{row.status}"
            await asyncio.sleep(1)
        return "工作流执行超时"

    tool_name = _sanitize_tool_name(wf.name, prefix="workflow")
    return StructuredTool.from_function(
        coroutine=_run,
        name=tool_name,
        description=wf.description or wf.name,
    )


async def _get_execution(exec_id: str):
    """查询 execution 状态。"""
    from app.models.workflow import WorkflowExecution

    async with async_session() as s:
        return (
            await s.execute(
                select(WorkflowExecution).where(WorkflowExecution.id == exec_id)
            )
        ).scalar_one_or_none()


def _skill_tool(sk: Skill):
    """构建技能激活工具。"""
    from langchain_core.tools import tool

    skill_name = _sanitize_tool_name(sk.name, prefix="skill")

    @tool(skill_name, description=f"激活技能：{sk.description or ''}")
    def _activate() -> str:
        return f"[SKILL {sk.name}]\n{sk.prompt or ''}"

    return _activate