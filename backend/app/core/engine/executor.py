"""工作流执行入口：build graph → astream → SSE 推送 → 落库。

execute_workflow 是 ARQ task 入口（也可同步调用）。
execute_workflow_sync 供 agent tool_registry 直接调用。
"""
import time
from datetime import datetime

from sqlalchemy import select

from app.config import settings
from app.core.engine.graph_builder import GraphBuilder
from app.core.engine.sse_bus import publish, subscribe, unsubscribe
from app.db.session import async_session
from app.models.workflow import Workflow, WorkflowExecution, WorkflowVersion


async def execute_workflow(
    workflow_id: str,
    inputs: dict | None = None,
    trigger: str = "manual",
    user_id=None,
    debug: bool = False,
) -> dict:
    """执行工作流，返回 {executionId, status, outputs}。"""
    async with async_session() as s:
        wf = (await s.execute(select(Workflow).where(Workflow.id == workflow_id))).scalar_one_or_none()
        if not wf:
            return {"executionId": "", "status": "failed", "error": "工作流不存在"}
        version = wf.current_version
        ver = None
        if version > 0:
            ver = (await s.execute(
                select(WorkflowVersion)
                .where(WorkflowVersion.workflow_id == wf.id)
                .where(WorkflowVersion.version == version)
            )).scalar_one_or_none()
        definition = (ver.definition_snapshot if ver else wf.definition) or {}

        execution = WorkflowExecution(
            workflow_id=wf.id, version=version, user_id=user_id,
            status="running", trigger_type=trigger, inputs=inputs or {},
            started_at=datetime.now(),
        )
        s.add(execution)
        await s.commit()
        await s.refresh(execution)
        exec_id = str(execution.id)

    await publish(exec_id, "execution_start", {"total_nodes": len(definition.get("nodes", []))})

    builder = GraphBuilder()
    try:
        graph = await builder.build(definition, exec_id, debug)
    except Exception as e:
        await _finish(exec_id, "failed", error=str(e))
        await publish(exec_id, "error", {"message": str(e)})
        return {"executionId": exec_id, "status": "failed", "error": str(e)}

    config = {"configurable": {"thread_id": exec_id}}
    initial = {
        "workflow_id": workflow_id, "execution_id": exec_id, "thread_id": exec_id,
        "user_id": str(user_id) if user_id else "", "variables": inputs or {},
        "node_outputs": {}, "status": "running", "started_at": time.time(),
        "node_timings": {}, "debug_mode": debug, "loop_stack": [],
    }

    t0 = time.perf_counter()
    try:
        async for ev in graph.astream(initial, config=config, stream_mode="updates"):
            for nid, update in ev.items():
                if nid in ("__start__", "__end__"):
                    continue
                await publish(exec_id, "node_start", {"nodeId": nid})
                await publish(exec_id, "node_complete", {
                    "nodeId": nid,
                    "output": str(update.get("node_outputs", {}).get(nid, {}))[:500],
                })
                if update.get("status") == "paused":
                    await _finish(exec_id, "paused")
                    await publish(exec_id, "execution_paused", {"nodeId": nid})
                    return {"executionId": exec_id, "status": "paused"}
        duration = round((time.perf_counter() - t0) * 1000, 1)
        await _finish(exec_id, "completed", duration_ms=duration)
        await publish(exec_id, "execution_complete", {"success": True, "duration_ms": duration})
        return {"executionId": exec_id, "status": "completed", "duration_ms": duration}
    except Exception as e:
        duration = round((time.perf_counter() - t0) * 1000, 1)
        await _finish(exec_id, "failed", error=str(e), duration_ms=duration)
        await publish(exec_id, "error", {"message": str(e)})
        return {"executionId": exec_id, "status": "failed", "error": str(e)}


async def execute_workflow_sync(workflow_id: str, inputs: dict) -> str:
    """供 agent tool_registry 直接调用（阻塞等待完成）。"""
    result = await execute_workflow(workflow_id, inputs, trigger="agent")
    return result.get("outputs", "") or result.get("status", "")


async def _finish(exec_id: str, status: str, error: str | None = None, duration_ms: float | None = None):
    """更新执行记录状态。"""
    async with async_session() as s:
        ex = (await s.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == exec_id)
        )).scalar_one_or_none()
        if ex:
            ex.status = status
            ex.error = error
            ex.duration_ms = duration_ms
            ex.completed_at = datetime.now() if status in ("completed", "failed", "cancelled") else None
            await s.commit()
 
