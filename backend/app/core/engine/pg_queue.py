"""PostgreSQL job queue client.

Implements job queue operations using PostgreSQL with SKIP LOCKED
for concurrent worker processing.
"""

from datetime import datetime
from typing import Optional, Dict, Any
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class PGJobQueue:
    """PostgreSQL job queue client."""

    @staticmethod
    async def enqueue(
        session: AsyncSession,
        workflow_id: uuid.UUID,
        inputs: dict,
        trigger: str,
        user_id: uuid.UUID,
        priority: int = 0
    ) -> str:
        """Enqueue a new job.
        
        Args:
            session: Database session
            workflow_id: Workflow ID to execute
            inputs: Workflow inputs
            trigger: Trigger type (manual/api/webhook/chat/agent)
            user_id: User who triggered the execution
            priority: Job priority (higher = processed first)
            
        Returns:
            Execution ID as string
        """
        # Insert WorkflowExecution and get the ID
        result = await session.execute(
            text("""
                INSERT INTO workflow_executions 
                    (workflow_id, inputs, trigger_type, user_id, status, version)
                VALUES 
                    (:wid, :inputs, :trigger, :uid, 'pending', 1)
                RETURNING id
            """),
            {
                "wid": workflow_id,
                "inputs": inputs,
                "trigger": trigger,
                "uid": user_id
            }
        )
        execution_id = result.scalar()
        
        # Insert into job_queue
        await session.execute(
            text("""
                INSERT INTO job_queue 
                    (execution_id, status, priority, created_at)
                VALUES 
                    (:eid, 'pending', :priority, NOW())
            """),
            {
                "eid": execution_id,
                "priority": priority
            }
        )
        
        await session.commit()
        return str(execution_id)

    @staticmethod
    async def dequeue(session: AsyncSession, worker_id: str) -> Optional[Dict[str, Any]]:
        """Dequeue a pending job using SELECT ... FOR UPDATE SKIP LOCKED.
        
        Args:
            session: Database session
            worker_id: Worker ID claiming the job
            
        Returns:
            Job data dict or None if no jobs available
        """
        # Select and lock a pending job
        result = await session.execute(
            text("""
                SELECT jq.execution_id, we.workflow_id, jq.priority
                FROM job_queue jq
                JOIN workflow_executions we ON jq.execution_id = we.id
                WHERE jq.status = 'pending'
                ORDER BY jq.priority DESC, jq.created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            """)
        )
        row = result.fetchone()
        
        if not row:
            await session.rollback()
            return None
        
        # Update job status to running
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
        
        # Update execution status
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
            "priority": row.priority
        }

    @staticmethod
    async def complete(
        session: AsyncSession,
        execution_id: str,
        status: str,
        error: Optional[str] = None
    ) -> None:
        """Mark a job as complete.
        
        Args:
            session: Database session
            execution_id: Execution ID
            status: Final status (completed/failed)
            error: Optional error message
        """
        # Update job_queue
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
        
        # Update workflow_executions
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
        """Cancel a pending or running job.
        
        Args:
            session: Database session
            execution_id: Execution ID
            
        Returns:
            True if cancelled, False if not found
        """
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
        
        # Also update workflow_executions
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
        """Check if a job has been cancelled.
        
        Args:
            session: Database session
            execution_id: Execution ID
            
        Returns:
            True if cancelled, False otherwise
        """
        result = await session.execute(
            text("""
                SELECT status FROM job_queue WHERE execution_id = :eid
            """),
            {"eid": execution_id}
        )
        status = result.scalar()
        return status == 'cancelled'

    @staticmethod
    async def _requeue_paused(session: AsyncSession, execution_id: str) -> None:
        """Requeue a paused job (used for resume).
        
        Args:
            session: Database session
            execution_id: Execution ID
        """
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
