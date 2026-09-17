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
            # 延迟加载：在首次调用时才连接 MCP 服务
            for mid in (agent.mcps or []):
                m = (await s.execute(select(Mcp).where(Mcp.id == mid))).scalar_one_or_none()
                if m and m.status == "on":
                    # 创建延迟加载的代理工具
                    tools.append(_mcp_lazy_tool(m))
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


def _mcp_lazy_tool(m: Mcp):
    """创建延迟加载的 MCP 工具。

    在被调用时才真正连接 MCP 服务并执行工具调用。
    支持任意参数格式，智能路由到合适的工具。

    Args:
        m: MCP 配置实例

    Returns:
        LangChain StructuredTool
    """
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    # 工具名称（合法化）
    tool_name = _sanitize_tool_name(m.name, prefix="mcp")

    # 工具描述
    description = (
        f"MCP 服务：{m.name}。"
        f"提供 {m.tool_count} 个工具的访问。"
        f"调用时传递查询参数（如 query）即可自动选择合适的工具。"
    )

    # 灵活的参数模型
    class LazyMCPInput(BaseModel):
        """支持多种参数格式的输入模型。"""
        query: str = Field(
            default="",
            description="搜索查询或其他文本参数"
        )
        url: str = Field(
            default="",
            description="URL 参数（用于获取网页内容）"
        )
        tool_name: str = Field(
            default="",
            description="指定要调用的 MCP 工具名称（可选）"
        )

        model_config = {"extra": "allow"}  # 允许额外参数

    async def _execute_lazy_mcp(**kwargs) -> str:
        """延迟加载并执行 MCP 工具。

        工作流程：
        1. 连接到 MCP 服务
        2. 发现可用工具
        3. 智能选择合适的工具
        4. 执行工具调用
        5. 返回结果
        """
        import logging
        import asyncio
        logger = logging.getLogger(__name__)
        logger.info(f"[MCP Lazy] 开始执行懒加载工具，参数: {kwargs}")

        try:
            # 步骤 1：连接到 MCP 服务
            from app.core.agent.tool_adapters.mcp_tools import load_tools as _load_mcp

            # 延迟加载 MCP 工具
            logger.info(f"[MCP Lazy] 步骤1: 连接 MCP 服务: {m.name}")
            mcp_tools = await _load_mcp(m)
            logger.info(f"[MCP Lazy] 步骤2: 发现 {len(mcp_tools)} 个工具")
            for t in mcp_tools:
                logger.info(f"  - {t.name}")

            if not mcp_tools:
                error_msg = f"[MCP {m.name}] 错误：未找到可用的工具。请检查 MCP 服务是否正常运行。"
                logger.error(error_msg)
                return error_msg

            # 步骤 2：智能路由 - 选择合适的工具
            target_tool = None
            requested_tool_name = kwargs.get('tool_name', '').lower()

            # 优先级 1：明确指定的工具名
            if requested_tool_name:
                for tool in mcp_tools:
                    if requested_tool_name in tool.name.lower():
                        target_tool = tool
                        logger.info(f"[MCP Lazy] 根据指定工具名选择: {tool.name}")
                        break

            # 优先级 2：根据参数类型推断
            if not target_tool:
                # 查询参数 → 搜索工具
                if kwargs.get('query'):
                    for tool in mcp_tools:
                        if 'search' in tool.name.lower():
                            target_tool = tool
                            logger.info(f"[MCP Lazy] 根据参数推断选择搜索工具: {tool.name}")
                            break

                # URL 参数 → 获取工具
                if kwargs.get('url'):
                    for tool in mcp_tools:
                        if 'fetch' in tool.name.lower() or 'get' in tool.name.lower():
                            target_tool = tool
                            logger.info(f"[MCP Lazy] 根据参数推断选择获取工具: {tool.name}")
                            break

            # 优先级 3：使用第一个可用工具
            if not target_tool:
                target_tool = mcp_tools[0]
                logger.info(f"[MCP Lazy] 使用第一个工具: {target_tool.name}")

            # 步骤 3：过滤参数
            # 移除内部参数（tool_name）和空值
            tool_kwargs = {
                k: v for k, v in kwargs.items()
                if k != 'tool_name' and v
            }
            logger.info(f"[MCP Lazy] 步骤3: 过滤后参数: {tool_kwargs}")

            # 步骤 4：执行工具调用（带超时保护）
            logger.info(f"[MCP Lazy] 步骤4: 调用工具 {target_tool.name}...")

            # 设置超时时间（60秒）
            TIMEOUT_SECONDS = 60

            try:
                result = await asyncio.wait_for(
                    target_tool.ainvoke(tool_kwargs),
                    timeout=TIMEOUT_SECONDS
                )
                logger.info(f"[MCP Lazy] 步骤5: 工具返回成功，结果长度: {len(str(result))}")
                return str(result)

            except asyncio.TimeoutError:
                error_msg = (
                    f"[MCP {m.name}] 工具执行超时（{TIMEOUT_SECONDS}秒）。\n"
                    f"可能是 DuckDuckGo 搜索响应缓慢或被阻塞。\n"
                    f"请稍后重试或使用其他关键词。"
                )
                logger.error(f"[MCP Lazy] 工具执行超时")
                return error_msg

        except Exception as e:
            # 错误处理
            import traceback
            error_msg = str(e)
            stack_trace = traceback.format_exc()

            logger.error(f"[MCP Lazy] 执行失败: {error_msg}")
            logger.error(f"[MCP Lazy] 详细错误:\n{stack_trace}")

            return (
                f"[MCP {m.name}] 执行失败: {error_msg}\n\n"
                f"详细错误:\n{stack_trace}"
            )

    # 创建 StructuredTool
    return StructuredTool.from_function(
        coroutine=_execute_lazy_mcp,
        name=tool_name,
        description=description,
        args_schema=LazyMCPInput,
    )


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
        from app.providers.trace.factory import get_tracing_callbacks
        scene = await get_scene_config("general")
        retriever = HybridRetriever(doc_ids=doc_ids, scene_config=scene, top_k=5, enable_nav=False)
        # 注入 tracing callbacks
        callbacks = get_tracing_callbacks()
        config = {"callbacks": callbacks} if callbacks else {}
        docs = await retriever.ainvoke(query, config=config)
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
    """构建技能激活工具（带脚本执行）。"""
    from app.core.agent.skill_tool_executor import create_skill_tool_with_scripts

    # 使用带脚本执行的技能工具
    return create_skill_tool_with_scripts(sk)