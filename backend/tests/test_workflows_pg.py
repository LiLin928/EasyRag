"""Tests for workflows API with PostgreSQL queue integration."""
import pytest
import uuid
from datetime import datetime
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_execute_workflow_enqueues_to_pg(client, db_session, auth_headers):
    """Test that workflow execution enqueues to PostgreSQL queue."""
    # Create a test workflow first
    from app.models.workflow import Workflow
    
    workflow_id = uuid.uuid4()
    wf = Workflow(
        id=workflow_id,
        user_id=uuid.uuid4(),
        name="Test Workflow",
        description="Test",
        status="published",
        definition={
            "nodes": [
                {"id": "node1", "type": "start", "data": {"label": "Start"}}
            ],
            "edges": []
        },
        current_version=1
    )
    db_session.add(wf)
    await db_session.commit()
    
    # Mock PGJobQueue.enqueue
    with patch("app.core.engine.pg_queue.PGJobQueue.enqueue", new_callable=AsyncMock) as mock_enqueue:
        mock_enqueue.return_value = str(uuid.uuid4())
        
        response = await client.post(
            f"/api/v2/workflows/{workflow_id}/execute",
            json={"inputs": {"test": "value"}},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "executionId" in data
        assert data["status"] == "running"
        
        # Verify enqueue was called with correct params
        mock_enqueue.assert_called_once()
        call_args = mock_enqueue.call_args
        assert call_args[1]["workflow_id"] == workflow_id
        assert call_args[1]["inputs"] == {"test": "value"}
        assert call_args[1]["trigger"] == "manual"


@pytest.mark.asyncio
async def test_execute_empty_workflow_returns_error(client, auth_headers):
    """Test that executing empty workflow returns error."""
    from app.models.workflow import Workflow
    import uuid
    
    workflow_id = uuid.uuid4()
    
    response = await client.post(
        f"/api/v2/workflows/{workflow_id}/execute",
        json={"inputs": {}},
        headers=auth_headers
    )
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_execute_workflow_response_format(client, db_session, auth_headers):
    """Test that execute response format is {executionId, status}."""
    import uuid
    from app.models.workflow import Workflow
    from unittest.mock import patch, AsyncMock
    
    workflow_id = uuid.uuid4()
    wf = Workflow(
        id=workflow_id,
        user_id=uuid.uuid4(),
        name="Test Workflow",
        description="Test",
        status="published",
        definition={
            "nodes": [
                {"id": "node1", "type": "start", "data": {"label": "Start"}}
            ],
            "edges": []
        },
        current_version=1
    )
    db_session.add(wf)
    await db_session.commit()
    
    execution_id = str(uuid.uuid4())
    
    with patch("app.core.engine.pg_queue.PGJobQueue.enqueue", new_callable=AsyncMock) as mock_enqueue:
        mock_enqueue.return_value = execution_id
        
        response = await client.post(
            f"/api/v2/workflows/{workflow_id}/execute",
            json={"inputs": {}},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify exact response format
        assert set(data.keys()) == {"executionId", "status"}
        assert data["executionId"] == execution_id
        assert data["status"] == "running"
