"""Agent 工具聚合：将五类挂载资源聚合为 LangChain BaseTool 列表。

1. tools → StructuredTool（HTTP/Python 经 execute_tool 执行）
2. docs → RAG 检索工具（复用 HybridRetriever）
3. wfs → 工作流触发工具
4. mcps → MCP server 发现的工具（经 langchain-mcp-adapters）
5. skills → 技能激活工具（注入 prompt 前缀）
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
    """将工具名称转换为符合 API 要求的格式。

    只允许字母、数字、下划线、连字符。
    不能以数字开头。

    Args:
        name: 原始工具名称
        prefix: 如果名称不合法时使用的前缀

    Returns:
        合法的工具名称
    """
    import re

    # 移除非法字符，替换为下划线
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)

    # 如果以数字开头，添加前缀
    if sanitized and sanitized[0].isdigit():
        sanitized = f'{prefix}_{sanitized}'

    # 如果为空或只有下划线，使用默认名称
    if not sanitized or sanitized == '_' * len(sanitized):
        sanitized = f'{prefix}_unnamed'

    return sanitized


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
                    mcp_tools = await _load_mcp(m)
                    # 转换MCP工具名称为合法格式
                    for t in mcp_tools:
                        t.name = _sanitize_tool_name(t.name)
                    tools.extend(mcp_tools)
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
    from pydantic import create_model, Field

    # 构建参数模型，包含默认值
    fields = {}
    for p in (t.params or []):
        param_name = p.get("n", "param")
        param_type = str  # 简化为字符串类型
        default_value = p.get("d", ...)  # 使用默认值，如果没有则为必填

        # 使用 Field 设置默认值和描述
        fields[param_name] = (
            param_type,
            Field(default=default_value, description=f"参数 {param_name}")
        )

    Args = create_model(f"{t.id}_Args", **fields) if fields else None

    async def _run(**kwargs):
        result = await execute_tool(str(t.id), kwargs)
        return result.get("data")

    # 转换工具名称为合法格式
    tool_name = _sanitize_tool_name(t.name)

    return StructuredTool.from_function(
        coroutine=_run,
        name=tool_name,  # 使用转换后的合法名称
        description=t.description or t.name,  # 描述可以包含中文
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

    # 转换工作流名称为合法格式
    tool_name = _sanitize_tool_name(wf.name, prefix="workflow")

    return StructuredTool.from_function(
        coroutine=_run,
        name=tool_name,
        description=wf.description or wf.name,
    )


async def _get_execution(exec_id: str):
    """查询 execution 状态（供轮询使用）。"""
    from app.models.workflow import WorkflowExecution

    async with async_session() as s:
        return (
            await s.execute(
                select(WorkflowExecution).where(WorkflowExecution.id == exec_id)
            )
        ).scalar_one_or_none()


def _skill_tool(sk: Skill):
    """构建技能激活工具，返回技能 prompt 前缀。"""
    from langchain_core.tools import tool

    # 转换技能名称为合法格式
    skill_name = _sanitize_tool_name(sk.name, prefix="skill")

    @tool(skill_name, description=f"激活技能：{sk.description or ''}")
    def _activate() -> str:
        return f"[SKILL {sk.name}]\n{sk.prompt or ''}"

    return _activate
 
