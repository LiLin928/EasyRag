"""PostgreSQL queue client tests.

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
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine.pg_queue import PGJobQueue


class TestPGJobQueueEnqueue:
    """Test enqueue method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.mark.asyncio
    async def test_enqueue_creates_execution_and_job(self, mock_session):
        """enqueue_with_session should create WorkflowExecution and job_queue record."""
        workflow_id = uuid.uuid4()
        user_id = uuid.uuid4()
        inputs = {"key": "value"}
        trigger = "manual"
        
        mock_result = MagicMock()
        mock_result.scalar.return_value = uuid.uuid4()
        mock_session.execute.return_value = mock_result
        
        result = await PGJobQueue.enqueue_with_session(
            session=mock_session,
            workflow_id=workflow_id,
            inputs=inputs,
            trigger=trigger,
            user_id=user_id,
            priority=0
        )
        
        assert isinstance(result, str)
        mock_session.execute.assert_called()
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_enqueue_returns_execution_id(self, mock_session):
        """enqueue_with_session should return execution_id."""
        workflow_id = uuid.uuid4()
        user_id = uuid.uuid4()
        expected_execution_id = str(uuid.uuid4())
        
        mock_result = MagicMock()
        mock_result.scalar.return_value = expected_execution_id
        mock_session.execute.return_value = mock_result
        
        result = await PGJobQueue.enqueue_with_session(
            session=mock_session,
            workflow_id=workflow_id,
            inputs={},
            trigger="api",
            user_id=user_id
        )
        
        assert result == expected_execution_id


class TestPGJobQueueDequeue:
    """Test dequeue method (using SELECT ... FOR UPDATE SKIP LOCKED)."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.mark.asyncio
    async def test_dequeue_returns_pending_job(self, mock_session):
        """dequeue should return pending job."""
        worker_id = "worker-1"
        execution_id = uuid.uuid4()
        
        mock_row = MagicMock()
        mock_row.execution_id = execution_id
        mock_row.workflow_id = uuid.uuid4()
        mock_row.priority = 0
        
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result
        
        result = await PGJobQueue.dequeue(mock_session, worker_id)
        
        assert result is not None
        assert result["execution_id"] == str(execution_id)

    @pytest.mark.asyncio
    async def test_dequeue_returns_none_when_empty(self, mock_session):
        """When queue is empty, dequeue should return None."""
        worker_id = "worker-1"
        
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result
        
        result = await PGJobQueue.dequeue(mock_session, worker_id)
        
        assert result is None


class TestPGJobQueueComplete:
    """Test complete method."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.mark.asyncio
    async def test_complete_updates_job_status(self, mock_session):
        """complete should update job_queue status to completed."""
        execution_id = str(uuid.uuid4())
        
        await PGJobQueue.complete(
            mock_session,
            execution_id=execution_id,
            status="completed"
        )
        
        mock_session.execute.assert_called()
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_complete_with_error_message(self, mock_session):
        """complete should record error on failure."""
        execution_id = str(uuid.uuid4())
        error_msg = "Something went wrong"
        
        await PGJobQueue.complete(
            mock_session,
            execution_id=execution_id,
            status="failed",
            error=error_msg
        )
        
        mock_session.execute.assert_called()
        mock_session.commit.assert_called()


class TestPGJobQueueCancel:
    """Test cancel and is_cancelled methods."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.mark.asyncio
    async def test_cancel_returns_true_on_success(self, mock_session):
        """cancel should return True on success."""
        execution_id = str(uuid.uuid4())
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result
        
        result = await PGJobQueue.cancel(mock_session, execution_id)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_returns_false_when_not_found(self, mock_session):
        """When job not found, cancel should return False."""
        execution_id = str(uuid.uuid4())
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result
        
        result = await PGJobQueue.cancel(mock_session, execution_id)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_true_when_cancelled(self, mock_session):
        """When status is cancelled, is_cancelled returns True."""
        execution_id = str(uuid.uuid4())
        mock_result = MagicMock()
        mock_result.scalar.return_value = "cancelled"
        mock_session.execute.return_value = mock_result
        
        result = await PGJobQueue.is_cancelled(mock_session, execution_id)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_is_cancelled_returns_false_when_not_cancelled(self, mock_session):
        """When status is not cancelled, is_cancelled returns False."""
        execution_id = str(uuid.uuid4())
        mock_result = MagicMock()
        mock_result.scalar.return_value = "running"
        mock_session.execute.return_value = mock_result
        
        result = await PGJobQueue.is_cancelled(mock_session, execution_id)
        
        assert result is False


class TestPGJobQueueRequeuePaused:
    """Test _requeue_paused method (used for resume)."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.mark.asyncio
    async def test_requeue_paused_updates_status_to_pending(self, mock_session):
        """_requeue_paused should update job status to pending."""
        execution_id = str(uuid.uuid4())
        
        await PGJobQueue._requeue_paused(mock_session, execution_id)
        
        mock_session.execute.assert_called()
        mock_session.commit.assert_called()
