"""Agent 工具聚合：将五类挂载资源聚合为 LangChain BaseTool 列表。

1. tools → StructuredTool（HTTP/Python 经 execute_tool 执行）
2. docs → RAG 检索工具（复用 HybridRetriever）
3. wfs → 工作流触发工具
4. mcps → MCP server 发现的工具（经 langchain-mcp-adapters）
5. skills → 技能激活工具（注入 prompt 前缀）
"""
from sqlalchemy import select

from app.db.session import async_session
from app.models.agent import Agent
from app.models.mcp import Mcp
from app.models.skill import Skill
from app.models.tool import Tool
from app.models.workflow import Workflow
from app.services.tool_service import execute_tool


async def build_tools(agent: Agent) -> list:
    """聚合 agent 挂载的五类资源为 BaseTool 列表。"""
    tools: list = []
    async with async_session() as s:
        # 1. tools
        for tid in (agent.tools or []):
            t = (await s.execute(select(Tool).where(Tool.id == tid))).scalar_one_or_none()
            if t and t.enabled:
                tools.append(_tool_to_structured(t))
        # 2. docs → RAG 工具
        if agent.docs:
            tools.append(_rag_tool(agent.docs))
        # 3. wfs → 工作流工具
        for wid in (agent.wfs or []):
            wf = (await s.execute(select(Workflow).where(Workflow.id == wid))).scalar_one_or_none()
            if wf:
                tools.append(_workflow_tool(wf))
        # 4. mcps → MCP 工具
        for mid in (agent.mcps or []):
            m = (await s.execute(select(Mcp).where(Mcp.id == mid))).scalar_one_or_none()
            if m and m.status == "on":
                try:
                    from app.core.agent.tool_adapters.mcp_tools import load_tools as _load_mcp
                    tools.extend(await _load_mcp(m))
                except Exception:
                    pass
        # 5. skills → 技能激活工具
        for sid in (agent.skills or []):
            sk = (await s.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
            if sk:
                tools.append(_skill_tool(sk))
    return tools


def _tool_to_structured(t: Tool):
    """将 ORM Tool 转为 LangChain StructuredTool。"""
    from langchain_core.tools import StructuredTool
    from pydantic import create_model

    fields = {p["n"]: (str, ...) for p in (t.params or [])}
    Args = create_model(f"{t.id}_Args", **fields) if fields else None

    async def _run(**kwargs):
        result = await execute_tool(str(t.id), kwargs)
        return result.get("data")

    return StructuredTool.from_function(
        coroutine=_run,
        name=t.name,
        description=t.description or t.name,
        args_schema=Args,
    )


def _rag_tool(doc_ids: list):
    """构建 RAG 检索工具，在挂载文档中检索。"""
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

    async def _run(**kwargs):
        from app.core.engine.executor import execute_workflow
        try:
            result = await execute_workflow(str(wf.id), kwargs)
            return result
        except Exception as e:
            return f"工作流 {wf.name} 执行失败: {e}"

    return StructuredTool.from_function(
        coroutine=_run,
        name=f"workflow_{wf.name}",
        description=wf.description or wf.name,
    )


def _skill_tool(sk: Skill):
    """构建技能激活工具，返回技能 prompt 前缀。"""
    from langchain_core.tools import tool

    @tool(sk.name, description=f"激活技能：{sk.description or ''}")
    def _activate() -> str:
        return f"[SKILL {sk.name}]\n{sk.prompt or ''}"

    return _activate
 
