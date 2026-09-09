"""PostgreSQL Worker tests.

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
from unittest.mock import AsyncMock, MagicMock, patch


class TestPGWorkerInit:
    """Test PGWorker initialization."""

    def test_init_with_default_params(self):
        """Should initialize with default parameters."""
        from app.worker.pg_worker import PGWorker
        
        worker = PGWorker()
        
        assert worker.poll_interval_fast == 0.1
        assert worker.poll_interval_slow == 5.0
        assert worker.worker_id is not None
        assert worker._shutdown is False

    def test_init_with_custom_params(self):
        """Should initialize with custom parameters."""
        from app.worker.pg_worker import PGWorker
        
        worker = PGWorker(
            poll_interval_fast=0.5,
            poll_interval_slow=10.0,
            worker_id="custom-worker-1"
        )
        
        assert worker.poll_interval_fast == 0.5
        assert worker.poll_interval_slow == 10.0
        assert worker.worker_id == "custom-worker-1"

    def test_init_generates_worker_id(self):
        """Should auto-generate worker_id if not provided."""
        from app.worker.pg_worker import PGWorker
        
        worker1 = PGWorker()
        worker2 = PGWorker()
        
        assert worker1.worker_id != worker2.worker_id
        assert worker1.worker_id.startswith("pg-worker-")


class TestPGWorkerFinishExecution:
    """Test _finish_execution method."""

    @pytest.mark.asyncio
    @patch("app.worker.pg_worker.async_session")
    async def test_finish_execution_updates_status(self, mock_session_class):
        """Should update execution status."""
        from app.worker.pg_worker import PGWorker
        
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # Create mock execution object with proper attributes
        mock_execution = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_execution)
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        worker = PGWorker()
        exec_id = str(uuid.uuid4())
        
        await worker._finish_execution(exec_id, "completed", duration_ms=100.5)
        
        mock_session.execute.assert_called()
        mock_session.commit.assert_called()
        assert mock_execution.status == "completed"
        assert mock_execution.duration_ms == 100.5

    @pytest.mark.asyncio
    @patch("app.worker.pg_worker.async_session")
    async def test_finish_execution_with_error(self, mock_session_class):
        """Should record error on failure."""
        from app.worker.pg_worker import PGWorker
        
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)
        
        mock_execution = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_execution)
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        worker = PGWorker()
        exec_id = str(uuid.uuid4())
        error_msg = "Something went wrong"
        
        await worker._finish_execution(exec_id, "failed", error=error_msg, duration_ms=50.0)
        
        mock_session.execute.assert_called()
        mock_session.commit.assert_called()
        assert mock_execution.status == "failed"
        assert mock_execution.error == error_msg


class TestPGWorkerShutdown:
    """Test graceful shutdown."""

    @pytest.mark.asyncio
    @patch("app.worker.pg_worker.async_session")
    @patch("app.worker.pg_worker.PGJobQueue")
    async def test_graceful_shutdown(self, mock_queue, mock_session_class):
        """Should stop polling on shutdown signal."""
        from app.worker.pg_worker import PGWorker
        
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_class.return_value.__aexit__ = AsyncMock(return_value=None)
        
        mock_queue.dequeue = AsyncMock(return_value=None)
        
        worker = PGWorker(poll_interval_fast=0.001, poll_interval_slow=0.001)
        
        # Set shutdown immediately
        worker._shutdown = True
        
        # Should return immediately
        await worker.run()
        
        # Should not have called dequeue or called it only once
        assert mock_queue.dequeue.call_count <= 1
