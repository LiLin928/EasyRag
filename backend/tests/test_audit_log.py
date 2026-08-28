"""审计日志写入 + 查询测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_log_audit_writes(monkeypatch):
    """log_audit 写入一条记录。"""
    from app.services.audit_service import log_audit

    fake_session = AsyncMock()
    fake_session.add = MagicMock()
    fake_session.commit = AsyncMock()
    fake_cm = AsyncMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.services.audit_service.async_session", lambda: fake_cm)

    await log_audit("u-1", "admin", "create", "user", "u-2", {"role": "viewer"})
    fake_session.add.assert_called_once()
    fake_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_log_audit_swallows_exceptions(monkeypatch):
    """log_audit 内部异常不影响主流程。"""
    from app.services.audit_service import log_audit

    fake_cm = AsyncMock()
    fake_cm.__aenter__ = AsyncMock(side_effect=Exception("DB down"))
    fake_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.services.audit_service.async_session", lambda: fake_cm)

    # should not raise
    await log_audit("u-1", "admin", "create", "user")


@pytest.mark.asyncio
async def test_query_audit_logs(monkeypatch):
    """查询审计日志。"""
    from app.services.audit_service import query_audit_logs

    fake_log = MagicMock()
    fake_log.id = "log-1"
    fake_log.user_id = "u-1"
    fake_log.username = "admin"
    fake_log.action = "create"
    fake_log.resource_type = "user"
    fake_log.resource_id = "u-2"
    fake_log.detail = {"role": "viewer"}
    fake_log.ip_address = "127.0.0.1"
    fake_log.created_at = MagicMock()
    fake_log.created_at.isoformat = MagicMock(return_value="2026-01-01T00:00:00")

    fake_result = MagicMock()
    fake_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[fake_log])))
    fake_session = AsyncMock()
    fake_session.execute = AsyncMock(return_value=fake_result)
    fake_cm = AsyncMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("app.services.audit_service.async_session", lambda: fake_cm)

    logs = await query_audit_logs()
    assert len(logs) == 1
    assert logs[0].username == "admin"


@pytest.mark.asyncio
async def test_audit_api_endpoint(monkeypatch):
    """GET /audit-logs 端点正常返回。"""
    from app.api.v2.audit import list_audit_logs

    fake_log = MagicMock()
    fake_log.id = "log-1"
    fake_log.user_id = "u-1"
    fake_log.username = "admin"
    fake_log.action = "create"
    fake_log.resource_type = "user"
    fake_log.resource_id = "u-2"
    fake_log.detail = {"role": "viewer"}
    fake_log.ip_address = "127.0.0.1"
    fake_log.created_at = MagicMock()
    fake_log.created_at.isoformat = MagicMock(return_value="2026-01-01T00:00:00")

    async def fake_query(**kwargs):
        return [fake_log]

    monkeypatch.setattr("app.api.v2.audit.query_audit_logs", fake_query)

    me = MagicMock()
    me.role = "admin"

    result = await list_audit_logs(me=me)
    assert "admin" in str(result)
