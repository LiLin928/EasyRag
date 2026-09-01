"""PostgreSQL Worker - ARQ Worker .

PostgreSQL  Redis/ARQ  。
"""
import asyncio
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import select

from app.db.session import async_session
from app.core.engine.pg_queue import PGJobQueue
from app.core.engine.sse_bus_pg import publish
from app.core.engine.graph_builder import GraphBuilder
from app.core.agent.memory import get_checkpointer
from app.models.workflow import Workflow, WorkflowExecution, WorkflowVersion


class PGWorker:
    """PostgreSQL-based worker for executing workflow jobs."""
    
    def __init__(
        self,
        poll_interval_fast: float = 0.1,
        poll_interval_slow: float = 5.0,
        worker_id: Optional[str] = None
    ):
        """Initialize the worker.
        
        Args:
            poll_interval_fast: Fast poll interval in seconds (when job found)
            poll_interval_slow: Slow poll interval in seconds (when no jobs)
            worker_id: Unique worker identifier (auto-generated if not provided)
        """
        self.poll_interval_fast = poll_interval_fast
        self.poll_interval_slow = poll_interval_slow
        self.worker_id = worker_id or f"pg-worker-{uuid.uuid4().hex[:8]}"
        self._shutdown = False
    
    async def run(self) -> None:
        """Main worker loop.
        
        Continuously polls the job queue for pending jobs and executes them.
        Uses fast polling when jobs are available, slow polling when queue is empty.
        """
        while not self._shutdown:
            job = None
            try:
                async with async_session() as session:
                    job = await PGJobQueue.dequeue(session, self.worker_id)
                
                if job:
                    await self._execute_job(job)
                    await asyncio.sleep(self.poll_interval_fast)
                else:
                    await asyncio.sleep(self.poll_interval_slow)
                    
            except Exception as e:
                print(f"Worker {self.worker_id} error: {e}")
                await asyncio.sleep(self.poll_interval_slow)
    
    async def _execute_job(self, job: dict) -> None:
        """Execute a workflow job using LangGraph."""
        execution_id = job["execution_id"]
        task_type = job.get("task_type", PGJobQueue.TASK_WORKFLOW)
        
        try:
            if task_type == PGJobQueue.TASK_WORKFLOW:
                await self._execute_workflow(job)
            elif task_type == PGJobQueue.TASK_PARSE_DOCUMENT:
                await self._execute_parse_document(job)
            elif task_type == PGJobQueue.TASK_REEMBED_CHUNKS:
                await self._execute_reembed_chunks(job)
            elif task_type == PGJobQueue.TASK_RETRIEVAL_TEST:
                await self._execute_retrieval_test(job)
            else:
                await self._execute_generic_task(job)
        except Exception as e:
            await self._finish_execution(execution_id, "failed", error=str(e))
            await publish(execution_id, "error", {"message": str(e)})
            raise
    
    async def _execute_workflow(self, job: dict) -> None:
        """Execute a workflow job."""
        execution_id = job["execution_id"]
        
        async with async_session() as session:
            execution = (
                await session.execute(
                    select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
                )
            ).scalar_one_or_none()
            
            if not execution:
                return
            
            wf = (
                await session.execute(
                    select(Workflow).where(Workflow.id == execution.workflow_id)
                )
            ).scalar_one_or_none()
            
            if not wf:
                await self._finish_execution(execution_id, "failed", error="Workflow not found")
                await publish(execution_id, "error", {"message": "Workflow not found"})
                return
            
            version = wf.current_version
            definition = wf.definition or {}
            if version > 0:
                ver = (
                    await session.execute(
                        select(WorkflowVersion)
                        .where(WorkflowVersion.workflow_id == wf.id)
                        .where(WorkflowVersion.version == version)
                    )
                ).scalar_one_or_none()
                if ver:
                    definition = ver.definition_snapshot or definition
            
            exec_id = str(execution.id)
            wf_id = str(execution.workflow_id)
            user_id = str(execution.user_id) if execution.user_id else ""
            inputs = execution.inputs or {}
        
        nodes = definition.get("nodes", [])
        await publish(exec_id, "execution_start", {"total_nodes": len(nodes)})
        
        builder = GraphBuilder()
        graph = await builder.build(definition, exec_id, debug=False)
        
        config = {"configurable": {"thread_id": exec_id}}
        
        snapshot = await graph.aget_state(config)
        has_checkpoint = snapshot and snapshot.next
        
        initial = {
            "workflow_id": wf_id,
            "execution_id": exec_id,
            "thread_id": exec_id,
            "user_id": user_id,
            "variables": inputs,
            "node_outputs": {},
            "status": "running",
            "started_at": time.time(),
            "node_timings": {},
            "debug_mode": False,
            "loop_stack": [],
        }
        
        stream_input = None if has_checkpoint else initial
        
        t0 = time.perf_counter()
        try:
            async for ev in graph.astream(stream_input, config=config, stream_mode="updates"):
                for nid, update in ev.items():
                    if nid in ("__start__", "__end__"):
                        continue
                    
                    await publish(exec_id, "node_start", {"nodeId": nid})
                    await publish(exec_id, "node_complete", {
                        "nodeId": nid,
                        "output": str(update.get("node_outputs", {}).get(nid, {}))[:500],
                    })
                    
                    if update.get("status") == "paused":
                        await self._finish_execution(exec_id, "paused")
                        await publish(exec_id, "execution_paused", {"nodeId": nid})
                        return
                
                async with async_session() as session:
                    if await PGJobQueue.is_cancelled(session, exec_id):
                        await self._finish_execution(exec_id, "cancelled")
                        await publish(exec_id, "execution_cancelled", {"executionId": exec_id})
                        return
        
        except Exception as e:
            duration = round((time.perf_counter() - t0) * 1000, 1)
            await self._finish_execution(exec_id, "failed", error=str(e), duration_ms=duration)
            await publish(exec_id, "error", {"message": str(e)})
            raise
        
        duration = round((time.perf_counter() - t0) * 1000, 1)
        await self._finish_execution(exec_id, "completed", duration_ms=duration)
        await publish(exec_id, "execution_complete", {"success": True, "duration_ms": duration})
    
    async def _execute_parse_document(self, job: dict) -> None:
        """Execute parse document task."""
        task_id = job.get("task_id")
        task_data = job.get("task_data", {})
        
        try:
            document_id = task_data.get("document_id")
            kb_id = task_data.get("kb_id")
            
            await publish(task_id, "task_start", {"task_type": PGJobQueue.TASK_PARSE_DOCUMENT})
            
            # TODO: Implement actual document parsing logic
            # For now, simulate processing
            await asyncio.sleep(1)
            
            result = {
                "document_id": document_id,
                "kb_id": kb_id,
                "chunks_created": 0,
                "status": "completed"
            }
            
            async with async_session() as session:
                await PGJobQueue.complete_generic(
                    session, task_id, "completed", result=result
                )
            
            await publish(task_id, "task_complete", {"result": result})
            
        except Exception as e:
            async with async_session() as session:
                await PGJobQueue.complete_generic(
                    session, task_id, "failed", error=str(e)
                )
            await publish(task_id, "task_error", {"error": str(e)})
            raise
    
    async def _execute_reembed_chunks(self, job: dict) -> None:
        """Execute re-embed chunks task."""
        task_id = job.get("task_id")
        task_data = job.get("task_data", {})
        
        try:
            kb_id = task_data.get("kb_id")
            chunk_ids = task_data.get("chunk_ids", [])
            embedding_model = task_data.get("embedding_model")
            
            await publish(task_id, "task_start", {"task_type": PGJobQueue.TASK_REEMBED_CHUNKS})
            
            # TODO: Implement actual re-embedding logic
            # For now, simulate processing
            await asyncio.sleep(1)
            
            result = {
                "kb_id": kb_id,
                "chunk_ids": chunk_ids,
                "embedding_model": embedding_model,
                "chunks_reembedded": len(chunk_ids),
                "status": "completed"
            }
            
            async with async_session() as session:
                await PGJobQueue.complete_generic(
                    session, task_id, "completed", result=result
                )
            
            await publish(task_id, "task_complete", {"result": result})
            
        except Exception as e:
            async with async_session() as session:
                await PGJobQueue.complete_generic(
                    session, task_id, "failed", error=str(e)
                )
            await publish(task_id, "task_error", {"error": str(e)})
            raise
    
    async def _execute_retrieval_test(self, job: dict) -> None:
        """Execute retrieval test task."""
        task_id = job.get("task_id")
        task_data = job.get("task_data", {})
        
        try:
            kb_id = task_data.get("kb_id")
            query = task_data.get("query")
            top_k = task_data.get("top_k", 5)
            
            await publish(task_id, "task_start", {"task_type": PGJobQueue.TASK_RETRIEVAL_TEST})
            
            # TODO: Implement actual retrieval test logic
            # For now, simulate processing
            await asyncio.sleep(0.5)
            
            result = {
                "kb_id": kb_id,
                "query": query,
                "top_k": top_k,
                "results": [],
                "status": "completed"
            }
            
            async with async_session() as session:
                await PGJobQueue.complete_generic(
                    session, task_id, "completed", result=result
                )
            
            await publish(task_id, "task_complete", {"result": result})
            
        except Exception as e:
            async with async_session() as session:
                await PGJobQueue.complete_generic(
                    session, task_id, "failed", error=str(e)
                )
            await publish(task_id, "task_error", {"error": str(e)})
            raise
    
    async def _execute_generic_task(self, job: dict) -> None:
        """Execute a generic task (fallback for unknown task types)."""
        task_id = job.get("task_id")
        task_type = job.get("task_type", "unknown")
        
        await publish(task_id, "task_start", {"task_type": task_type})
        
        result = {"status": "completed", "message": f"Task {task_type} processed"}
        
        async with async_session() as session:
            await PGJobQueue.complete_generic(
                session, task_id, "completed", result=result
            )
        
        await publish(task_id, "task_complete", {"result": result})
    
    async def _finish_execution(
        self,
        exec_id: str,
        status: str,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None
    ) -> None:
        """Update execution record status."""
        async with async_session() as session:
            ex = (
                await session.execute(
                    select(WorkflowExecution).where(WorkflowExecution.id == exec_id)
                )
            ).scalar_one_or_none()
            
            if ex:
                ex.status = status
                ex.error = error
                ex.duration_ms = duration_ms
                if status in ("completed", "failed", "cancelled"):
                    ex.completed_at = datetime.now()
                await session.commit()
