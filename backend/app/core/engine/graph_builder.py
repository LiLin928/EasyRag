"""GraphBuilder：workflow definition → LangGraph CompiledStateGraph。

1. 注册节点执行器（type → NodeRouter.create）
2. 注册边（普通 + 条件分支）
3. 入口（START → start node）/ 出口（end node → END）
4. checkpoint + 中断点（debug 暂停所有；human 暂停 human 节点前）
"""
from langgraph.graph import END, START, StateGraph

from app.core.agent.memory import get_checkpointer
from app.core.engine.nodes import basic  # noqa: F401 — 触发注册
from app.core.engine.nodes.base import NodeRouter
from app.core.engine.state import WorkflowState


class GraphBuilder:
    """将 workflow definition 编译为 LangGraph。"""

    async def build(self, definition: dict, execution_id: str, debug: bool = False):
        nodes = definition.get("nodes", [])
        edges = definition.get("edges", [])
        graph = StateGraph(WorkflowState)

        for nd in nodes:
            executor = NodeRouter.create(nd)
            graph.add_node(nd["id"], executor.run)

        for e in edges:
            src = e["source"]
            tgt = e["target"]
            handle = e.get("sourceHandle")
            if handle and handle not in ("output",):
                graph.add_conditional_edges(src, lambda s, h=handle: h, {handle: tgt})
            else:
                graph.add_edge(src, tgt)

        start_id = next((n["id"] for n in nodes if n["type"] == "start"), None)
        if start_id:
            graph.add_edge(START, start_id)

        for n in nodes:
            if n["type"] == "end":
                graph.add_edge(n["id"], END)

        checkpointer = await get_checkpointer()
        interrupt = ["*"] if debug else [
            n["id"] for n in nodes if n["type"] == "human"
        ]
        return graph.compile(checkpointer=checkpointer, interrupt_before=interrupt or None)
