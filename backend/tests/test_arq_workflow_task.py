"""ARQ workflow task unit tests."""
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# pdfplumber is not installed in the test env; mock it in sys.modules
# so that importing app.worker.app (-> parser.dispatcher -> pdf_parser) succeeds.
if "pdfplumber" not in sys.modules:
    sys.modules["pdfplumber"] = MagicMock()


def _make_result(return_value):
    """Create a mock DB execute result returning the given value from scalar_one_or_none."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=return_value)
    return result


def _make_session_cm(execute_side_effects):
    """Create a mock async session context manager with the given execute side effects."""
    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(side_effect=execute_side_effects)
    fake_session.commit = AsyncMock()
    fake_session_cm = AsyncMock()
    fake_session_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session_cm.__aexit__ = AsyncMock(return_value=None)
    return fake_session_cm


@pytest.mark.asyncio
async def test_execute_workflow_task_fresh_run(monkeypatch):
    """No checkpoint -> astream(initial) full execution."""
    fake_execution = MagicMock()
    fake_execution.id = "exec-1"
    fake_execution.workflow_id = "wf-1"
    fake_execution.version = 1
    fake_execution.inputs = {"q": "hello"}
    fake_execution.user_id = "user-1"
    fake_execution.status = "running"

    fake_wf = MagicMock()
    fake_wf.id = "wf-1"
    fake_wf.definition = {"nodes": [{"id": "start", "type": "start"}, {"id": "end", "type": "end"}], "edges": [{"source": "start", "target": "end"}]}
    fake_wf.current_version = 1
    fake_ver = MagicMock()
    fake_ver.definition_snapshot = fake_wf.definition

    results = [
        _make_result(fake_execution),
        _make_result(fake_wf),
        _make_result(fake_ver),
        _make_result(fake_execution),  # _is_cancelled after event 1
        _make_result(fake_execution),  # _is_cancelled after event 2
        _make_result(fake_execution),  # _finish
    ]
    fake_session_cm = _make_session_cm(results)
    monkeypatch.setattr("app.worker.app.async_session", lambda: fake_session_cm)

    fake_graph = AsyncMock()
    fake_snapshot = MagicMock()
    fake_snapshot.next = None
    fake_graph.aget_state = AsyncMock(return_value=fake_snapshot)

    astream_inputs = []

    async def fake_astream(initial, config=None, stream_mode=None):
        astream_inputs.append(initial)
        yield {"start": {"node_outputs": {"start": {"output": "ok"}}, "status": "running"}}
        yield {"end": {"node_outputs": {"end": {"output": "done"}}, "status": "completed"}}

    fake_graph.astream = fake_astream
    fake_builder = MagicMock()
    fake_builder.build = AsyncMock(return_value=fake_graph)
    monkeypatch.setattr("app.worker.app.GraphBuilder", lambda: fake_builder)
    mock_publish = AsyncMock()
    monkeypatch.setattr("app.worker.app.publish", mock_publish)

    from app.worker.app import execute_workflow_task
    await execute_workflow_task(MagicMock(), "exec-1")

    assert astream_inputs[0] is not None
    assert astream_inputs[0]["execution_id"] == "exec-1"
    assert mock_publish.call_count >= 3
    first_call = mock_publish.call_args_list[0]
    assert first_call.args[1] == "execution_start"


@pytest.mark.asyncio
async def test_execute_workflow_task_resume_from_checkpoint(monkeypatch):
    """Has checkpoint -> astream(None) resume."""
    fake_execution = MagicMock()
    fake_execution.id = "exec-2"
    fake_execution.workflow_id = "wf-2"
    fake_execution.version = 1
    fake_execution.inputs = {"q": "resume"}
    fake_execution.user_id = "user-2"
    fake_execution.status = "running"

    fake_wf = MagicMock()
    fake_wf.id = "wf-2"
    fake_wf.definition = {"nodes": [{"id": "n1", "type": "start"}, {"id": "n2", "type": "end"}], "edges": [{"source": "n1", "target": "n2"}]}
    fake_wf.current_version = 1
    fake_ver = MagicMock()
    fake_ver.definition_snapshot = fake_wf.definition

    results = [
        _make_result(fake_execution),
        _make_result(fake_wf),
        _make_result(fake_ver),
        _make_result(fake_execution),  # _is_cancelled
        _make_result(fake_execution),  # _finish
    ]
    fake_session_cm = _make_session_cm(results)
    monkeypatch.setattr("app.worker.app.async_session", lambda: fake_session_cm)

    fake_graph = AsyncMock()
    fake_snapshot = MagicMock()
    fake_snapshot.next = ("n2",)
    fake_graph.aget_state = AsyncMock(return_value=fake_snapshot)

    astream_inputs = []

    async def fake_astream(initial, config=None, stream_mode=None):
        astream_inputs.append(initial)
        yield {"n2": {"node_outputs": {"n2": {"output": "resumed"}}, "status": "completed"}}

    fake_graph.astream = fake_astream
    fake_builder = MagicMock()
    fake_builder.build = AsyncMock(return_value=fake_graph)
    monkeypatch.setattr("app.worker.app.GraphBuilder", lambda: fake_builder)
    monkeypatch.setattr("app.worker.app.publish", AsyncMock())

    from app.worker.app import execute_workflow_task
    await execute_workflow_task(MagicMock(), "exec-2")

    assert astream_inputs[0] is None


@pytest.mark.asyncio
async def test_execute_workflow_task_cancel_detection(monkeypatch):
    """astream loop detects DB status=cancelled -> break + publish execution_cancelled."""
    fake_execution = MagicMock()
    fake_execution.id = "exec-3"
    fake_execution.workflow_id = "wf-3"
    fake_execution.version = 1
    fake_execution.inputs = {}
    fake_execution.user_id = "user-3"
    fake_execution.status = "cancelled"

    fake_wf = MagicMock()
    fake_wf.id = "wf-3"
    fake_wf.definition = {"nodes": [{"id": "s", "type": "start"}, {"id": "e", "type": "end"}], "edges": [{"source": "s", "target": "e"}]}
    fake_wf.current_version = 1
    fake_ver = MagicMock()
    fake_ver.definition_snapshot = fake_wf.definition

    results = [
        _make_result(fake_execution),
        _make_result(fake_wf),
        _make_result(fake_ver),
        _make_result(fake_execution),  # _is_cancelled -> cancelled
        _make_result(fake_execution),  # _finish
    ]
    fake_session_cm = _make_session_cm(results)
    monkeypatch.setattr("app.worker.app.async_session", lambda: fake_session_cm)

    fake_graph = AsyncMock()
    fake_snapshot = MagicMock()
    fake_snapshot.next = None
    fake_graph.aget_state = AsyncMock(return_value=fake_snapshot)

    async def fake_astream(initial, config=None, stream_mode=None):
        yield {"s": {"node_outputs": {"s": {}}, "status": "running"}}

    fake_graph.astream = fake_astream
    fake_builder = MagicMock()
    fake_builder.build = AsyncMock(return_value=fake_graph)
    mock_publish = AsyncMock()
    monkeypatch.setattr("app.worker.app.publish", mock_publish)

    from app.worker.app import execute_workflow_task
    await execute_workflow_task(MagicMock(), "exec-3")

    cancel_calls = [c for c in mock_publish.call_args_list if c.args[1] == "execution_cancelled"]
    assert len(cancel_calls) == 1
