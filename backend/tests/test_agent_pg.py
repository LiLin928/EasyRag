"""Agent workflow tool PostgreSQL queue tests.

TDD flow:
1. Write failing test
2. Run to confirm failure
3. Implement minimal code
4. Run to confirm pass
5. git commit
"""

import uuid
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call

from sqlalchemy.ext.asyncio import AsyncSession


class TestAgentWorkflowTool:
    """Test that Agent workflow tool uses PostgreSQL queue."""

    @pytest.mark.asyncio
    async def test_workflow_tool_uses_pg_queue(self):
        """Agent调用工作流时应使用 PostgreSQL 队列 (PGJobQueue.enqueue).
        
        验证:
        1. enqueue_workflow_task 调用 PGJobQueue.enqueue
        2. 不使用 ARQ (redis)
        """
        workflow_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        inputs = {"key": "value"}
        trigger = "agent"
        
        # Create mock session
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock Workflow query
        mock_wf = MagicMock()
        mock_wf.id = uuid.UUID(workflow_id)
        mock_wf.current_version = 0  # version 0, no version query
        mock_wf.definition = {}
        
        mock_result_wf = MagicMock()
        mock_result_wf.scalar_one_or_none.return_value = mock_wf
        mock_session.execute.return_value = mock_result_wf
        
        # Create async context manager mock
        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session
            async def __aexit__(self, *args):
                return None
        
        mock_session_factory = MagicMock()
        mock_session_factory.return_value = AsyncContextManager()
        
        with patch('app.db.session.async_session', mock_session_factory), \
             patch('app.core.engine.pg_queue.PGJobQueue.enqueue', new_callable=AsyncMock) as mock_enqueue:
            
            # Setup PGJobQueue.enqueue mock
            mock_enqueue.return_value = execution_id
            
            # Import and call enqueue_workflow_task
            from app.core.engine.arq_client import enqueue_workflow_task
            
            result = await enqueue_workflow_task(
                workflow_id=workflow_id,
                inputs=inputs,
                trigger=trigger,
                user_id=None
            )
            
            # Verify PGJobQueue.enqueue was called
            mock_enqueue.assert_called_once()
            call_kwargs = mock_enqueue.call_args.kwargs
            assert str(call_kwargs['workflow_id']) == workflow_id
            assert call_kwargs['inputs'] == inputs
            assert call_kwargs['trigger'] == trigger
            assert call_kwargs['user_id'] is None
            assert call_kwargs['priority'] == 0
            
            # Verify returned execution_id
            assert result == execution_id

    @pytest.mark.asyncio
    async def test_workflow_tool_not_using_redis(self):
        """验证 enqueue_workflow_task 不调用 ARQ (redis).
        
        确保没有调用 arq.create_pool 或 enqueue_job.
        """
        workflow_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        
        mock_session = AsyncMock(spec=AsyncSession)
        mock_wf = MagicMock()
        mock_wf.id = uuid.UUID(workflow_id)
        mock_wf.current_version = 0
        mock_wf.definition = {}
        
        mock_result_wf = MagicMock()
        mock_result_wf.scalar_one_or_none.return_value = mock_wf
        mock_session.execute.return_value = mock_result_wf
        
        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session
            async def __aexit__(self, *args):
                return None
        
        mock_session_factory = MagicMock()
        mock_session_factory.return_value = AsyncContextManager()
        
        with patch('app.db.session.async_session', mock_session_factory), \
             patch('app.core.engine.pg_queue.PGJobQueue.enqueue', new_callable=AsyncMock) as mock_enqueue, \
             patch('arq.create_pool') as mock_arq_pool:
            
            mock_enqueue.return_value = execution_id
            
            from app.core.engine.arq_client import enqueue_workflow_task
            
            await enqueue_workflow_task(
                workflow_id=workflow_id,
                inputs={},
                trigger="agent",
                user_id=None
            )
            
            # ARQ should not be called
            mock_arq_pool.assert_not_called()
            
            # PGJobQueue.enqueue should be called
            mock_enqueue.assert_called_once()
