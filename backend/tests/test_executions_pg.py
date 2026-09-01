"""Tests for executions API with PostgreSQL queue integration."""
import pytest
import uuid
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio


@pytest.mark.asyncio
async def test_stream_uses_sse_bus_pg(client, db_session, auth_headers):
    """Test that stream endpoint uses sse_bus_pg.subscribe."""
    from app.models.workflow import Workflow, WorkflowExecution
    
    # Create test execution
    execution_id = str(uuid.uuid4())
    workflow_id = uuid.uuid4()
    
    wf = Workflow(
        id=workflow_id,
        user_id=uuid.uuid4(),
        name="Test Workflow",
        description="Test",
        status="published",
        definition={"nodes": [], "edges": []},
        current_version=1
    )
    ex = WorkflowExecution(
        id=uuid.UUID(execution_id),
        workflow_id=workflow_id,
        status="running",
        trigger_type="manual",
        started_at=datetime.now()
    )
    
    db_session.add(wf)
    db_session.add(ex)
    await db_session.commit()
    
    # Mock sse_bus_pg.subscribe
    async def mock_subscribe(eid, poll_interval=0.5):
        yield 'data: {"type": "test"}\n\n'
        yield 'data: {"type": "execution_complete"}\n\n'
    
    with patch("app.api.v2.executions.subscribe", side_effect=mock_subscribe):
        response = await client.get(
            f"/api/v2/executions/{execution_id}/stream",
            headers=auth_headers
        )
        
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_resume_uses_pg_queue_requeue(client, db_session, auth_headers):
    """Test that resume endpoint uses pg_queue._requeue_paused."""
    from app.models.workflow import Workflow, WorkflowExecution
    
    execution_id = str(uuid.uuid4())
    workflow_id = uuid.uuid4()
    
    wf = Workflow(
        id=workflow_id,
        user_id=uuid.uuid4(),
        name="Test Workflow",
        description="Test",
        status="published",
        definition={"nodes": [], "edges": []},
        current_version=1
    )
    ex = WorkflowExecution(
        id=uuid.UUID(execution_id),
        workflow_id=workflow_id,
        status="paused",
        trigger_type="manual",
        started_at=datetime.now()
    )
    
    db_session.add(wf)
    db_session.add(ex)
    await db_session.commit()
    
    with patch("app.core.engine.pg_queue.PGJobQueue._requeue_paused", new_callable=AsyncMock) as mock_requeue:
        response = await client.post(
            f"/api/v2/executions/{execution_id}/resume",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify _requeue_paused was called
        mock_requeue.assert_called_once()
        call_args = mock_requeue.call_args
        assert str(call_args[0][0]) == execution_id


@pytest.mark.asyncio
async def test_resume_only_for_paused(client, db_session, auth_headers):
    """Test that resume only works for paused executions."""
    from app.models.workflow import WorkflowExecution
    
    execution_id = str(uuid.uuid4())
    workflow_id = uuid.uuid4()
    
    # Create running execution
    ex = WorkflowExecution(
        id=uuid.UUID(execution_id),
        workflow_id=workflow_id,
        status="running",
        trigger_type="manual",
        started_at=datetime.now()
    )
    
    db_session.add(ex)
    await db_session.commit()
    
    response = await client.post(
        f"/api/v2/executions/{execution_id}/resume",
        headers=auth_headers
    )
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_cancel_updates_pg_queue(client, db_session, auth_headers):
    """Test that cancel endpoint updates both DB and pg_queue."""
    from app.models.workflow import Workflow, WorkflowExecution
    
    execution_id = str(uuid.uuid4())
    workflow_id = uuid.uuid4()
    
    wf = Workflow(
        id=workflow_id,
        user_id=uuid.uuid4(),
        name="Test Workflow",
        description="Test",
        status="published",
        definition={"nodes": [], "edges": []},
        current_version=1
    )
    ex = WorkflowExecution(
        id=uuid.UUID(execution_id),
        workflow_id=workflow_id,
        status="running",
        trigger_type="manual",
        started_at=datetime.now()
    )
    
    db_session.add(wf)
    db_session.add(ex)
    await db_session.commit()
    
    with patch("app.core.engine.pg_queue.PGJobQueue.cancel", new_callable=AsyncMock) as mock_cancel:
        mock_cancel.return_value = True
        
        response = await client.post(
            f"/api/v2/executions/{execution_id}/cancel",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify cancel was called
        mock_cancel.assert_called_once()


@pytest.mark.asyncio
async def test_pg_queue_health_endpoint(client, auth_headers):
    """Test the pg-queue health endpoint."""
    from unittest.mock import patch, MagicMock
    
    # Mock database query results
    mock_status_rows = [
        MagicMock(status="pending", count=5),
        MagicMock(status="running", count=2),
        MagicMock(status="completed", count=10),
    ]
    
    mock_worker_rows = [
        MagicMock(worker_id="worker-1", task_count=2),
    ]
    
    with patch("app.api.v2.health.async_session") as mock_session:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_status_rows
        
        mock_result2 = MagicMock()
        mock_result2.fetchall.return_value = mock_worker_rows
        
        mock_result3 = MagicMock()
        mock_result3.fetchall.return_value = []
        
        mock_session.return_value.__aenter__.return_value.execute = MagicMock(side_effect=[
            mock_result, mock_result2, mock_result3
        ])
        
        response = await client.get(
            "/api/v2/health/pg-queue",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "queue" in data
        assert "workers" in data
        assert "recent_1h" in data
        assert "status" in data
        
        assert data["queue"]["pending"] == 5
        assert data["queue"]["running"] == 2
        assert data["queue"]["completed"] == 10
