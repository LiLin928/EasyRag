"""PostgreSQL job queue client.

Implements job queue operations using PostgreSQL with SKIP LOCKED
for concurrent worker processing.
"""

from datetime import datetime
from typing import Optional, Dict, Any
import uuid

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.workflow import Workflow, WorkflowVersion


class PGJobQueue:
    """PostgreSQL job queue client."""
    
    # Task type constants
    TASK_WORKFLOW = 'workflow'
    TASK_PARSE_DOCUMENT = 'parse_document'
    TASK_REEMBED_CHUNKS = 'reembed_chunks'
    TASK_RETRIEVAL_TEST = 'retrieval_test'

    async def enqueue(
        self,
        workflow_id: str,
        inputs: dict,
        trigger: str,
        user_id: Optional[str] = None,
        priority: int = 0
    ) -> str:
        """Enqueue a new job (instance method, manages its own session)."""
        async with async_session() as session:
            wf = (
                await session.execute(select(Workflow).where(Workflow.id == uuid.UUID(workflow_id)))
            ).scalar_one_or_none()
            if not wf:
                raise ValueError(f"Workflow not found: {workflow_id}")

            version = wf.current_version
            if version > 0:
                await session.execute(
                    select(WorkflowVersion)
                    .where(WorkflowVersion.workflow_id == wf.id)
                    .where(WorkflowVersion.version == version)
                )

            return await PGJobQueue._enqueue_with_session(
                session=session,
                workflow_id=wf.id,
                inputs=inputs,
                trigger=trigger,
                user_id=uuid.UUID(user_id) if user_id else None,
                version=version,
                priority=priority
            )

    @staticmethod
    async def _enqueue_with_session(
        session: AsyncSession,
        workflow_id: uuid.UUID,
        inputs: dict,
        trigger: str,
        user_id: Optional[uuid.UUID],
        version: int = 0,
        priority: int = 0
    ) -> str:
        result = await session.execute(
            text("INSERT INTO workflow_executions (workflow_id, inputs, trigger_type, user_id, status, version, started_at) VALUES (:wid, :inputs, :trigger, :uid, 'pending', :version, NOW()) RETURNING id"),
            {"wid": workflow_id, "inputs": inputs, "trigger": trigger, "uid": user_id, "version": version}
        )
        execution_id = result.scalar()
        
        await session.execute(
            text("INSERT INTO job_queue (execution_id, status, priority, created_at, task_type) VALUES (:eid, 'pending', :priority, NOW(), :task_type)"),
            {"eid": execution_id, "priority": priority, "task_type": PGJobQueue.TASK_WORKFLOW}
        )
        
        await session.commit()
        return str(execution_id)

    @staticmethod
    async def enqueue_task(
        session: AsyncSession,
        task_type: str,
        task_data: Dict[str, Any],
        priority: int = 0
    ) -> str:
        result = await session.execute(
            text("INSERT INTO generic_tasks (task_type, task_data, status, created_at) VALUES (:task_type, :task_data, 'pending', NOW()) RETURNING id"),
            {"task_type": task_type, "task_data": task_data}
        )
        task_id = result.scalar()
        
        await session.execute(
            text("INSERT INTO job_queue (task_id, status, priority, created_at, task_type) VALUES (:task_id, 'pending', :priority, NOW(), :task_type)"),
            {"task_id": task_id, "priority": priority, "task_type": task_type}
        )
        
        await session.commit()
        return str(task_id)

    @staticmethod
    async def dequeue_generic(
        session: AsyncSession,
        worker_id: str,
        task_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if task_type:
            query = text("SELECT jq.task_id, jq.priority, jq.task_type, gt.task_data FROM job_queue jq JOIN generic_tasks gt ON jq.task_id = gt.id WHERE jq.status = 'pending' AND jq.task_type = :task_type ORDER BY jq.priority DESC, jq.created_at ASC FOR UPDATE SKIP LOCKED LIMIT 1")
            params = {"task_type": task_type}
        else:
            query = text("SELECT jq.task_id, jq.priority, jq.task_type, gt.task_data FROM job_queue jq JOIN generic_tasks gt ON jq.task_id = gt.id WHERE jq.status = 'pending' AND jq.task_type != :workflow_task_type ORDER BY jq.priority DESC, jq.created_at ASC FOR UPDATE SKIP LOCKED LIMIT 1")
            params = {"workflow_task_type": PGJobQueue.TASK_WORKFLOW}
        
        result = await session.execute(query, params)
        row = result.fetchone()
        
        if not row:
            await session.rollback()
            return None
        
        task_id = row.task_id
        
        await session.execute(
            text("UPDATE job_queue SET status = 'running', worker_id = :wid, started_at = NOW() WHERE task_id = :task_id"),
            {"task_id": task_id, "wid": worker_id}
        )
        
        await session.execute(
            text("UPDATE generic_tasks SET status = 'running', started_at = NOW() WHERE id = :task_id"),
            {"task_id": task_id}
        )
        
        await session.commit()
        
        return {
            "task_id": str(task_id),
            "task_type": row.task_type,
            "task_data": row.task_data,
            "priority": row.priority
        }

    @staticmethod
    async def complete_generic(
        session: AsyncSession,
        task_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> None:
        await session.execute(
            text("UPDATE job_queue SET status = :status, completed_at = NOW(), error_msg = :error WHERE task_id = :task_id"),
            {"task_id": task_id, "status": status, "error": error}
        )
        
        await session.execute(
            text("UPDATE generic_tasks SET status = :status, completed_at = NOW(), result = :result, error = :error WHERE id = :task_id"),
            {"task_id": task_id, "status": status, "result": result, "error": error}
        )
        
        await session.commit()

    @staticmethod
    async def dequeue(session: AsyncSession, worker_id: str) -> Optional[Dict[str, Any]]:
        """Dequeue a pending workflow job using SELECT ... FOR UPDATE SKIP LOCKED."""
        result = await session.execute(
            text("""
                SELECT jq.execution_id, we.workflow_id, jq.priority, jq.task_type
                FROM job_queue jq
                JOIN workflow_executions we ON jq.execution_id = we.id
                WHERE jq.status = 'pending'
                AND jq.task_type = :task_type
                ORDER BY jq.priority DESC, jq.created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            """),
            {"task_type": PGJobQueue.TASK_WORKFLOW}
        )
        row = result.fetchone()
        
        if not row:
            await session.rollback()
            return None
        
        await session.execute(
            text("""
                UPDATE job_queue
                SET status = 'running',
                    worker_id = :wid,
                    started_at = NOW()
                WHERE execution_id = :eid
            """),
            {"eid": row.execution_id, "wid": worker_id}
        )
        
        await session.execute(
            text("""
                UPDATE workflow_executions
                SET status = 'running',
                    started_at = NOW()
                WHERE id = :eid
            """),
            {"eid": row.execution_id}
        )
        
        await session.commit()
        
        return {
            "execution_id": str(row.execution_id),
            "workflow_id": str(row.workflow_id),
            "priority": row.priority,
            "task_type": row.task_type
        }

    @staticmethod
    async def complete(
        session: AsyncSession,
        execution_id: str,
        status: str,
        error: Optional[str] = None
    ) -> None:
        """Mark a job as complete."""
        await session.execute(
            text("""
                UPDATE job_queue
                SET status = :status,
                    completed_at = NOW(),
                    error_msg = :error
                WHERE execution_id = :eid
            """),
            {"eid": execution_id, "status": status, "error": error}
        )
        
        await session.execute(
            text("""
                UPDATE workflow_executions
                SET status = :status,
                    completed_at = NOW(),
                    error = :error
                WHERE id = :eid
            """),
            {"eid": execution_id, "status": status, "error": error}
        )
        
        await session.commit()

    @staticmethod
    async def cancel(session: AsyncSession, execution_id: str) -> bool:
        """Cancel a pending or running job."""
        result = await session.execute(
            text("""
                UPDATE job_queue
                SET status = 'cancelled',
                    completed_at = NOW()
                WHERE execution_id = :eid
                  AND status IN ('pending', 'running')
            """),
            {"eid": execution_id}
        )
        
        if result.rowcount == 0:
            await session.rollback()
            return False
        
        await session.execute(
            text("""
                UPDATE workflow_executions
                SET status = 'cancelled',
                    completed_at = NOW()
                WHERE id = :eid
            """),
            {"eid": execution_id}
        )
        
        await session.commit()
        return True

    @staticmethod
    async def is_cancelled(session: AsyncSession, execution_id: str) -> bool:
        """Check if a job has been cancelled."""
        result = await session.execute(
            text("SELECT status FROM job_queue WHERE execution_id = :eid"),
            {"eid": execution_id}
        )
        status = result.scalar()
        return status == 'cancelled'

    @staticmethod
    async def _requeue_paused(session: AsyncSession, execution_id: str) -> None:
        """Requeue a paused job (used for resume)."""
        await session.execute(
            text("""
                UPDATE job_queue
                SET status = 'pending',
                    worker_id = NULL,
                    started_at = NULL,
                    retry_count = retry_count + 1
                WHERE execution_id = :eid
            """),
            {"eid": execution_id}
        )
        
        await session.execute(
            text("""
                UPDATE workflow_executions
                SET status = 'pending'
                WHERE id = :eid
            """),
            {"eid": execution_id}
        )
        
        await session.commit()
