"""审计日志服务。"""
import structlog

from sqlalchemy import select

from app.db.session import async_session
from app.models.audit_log import AuditLog

_log = structlog.get_logger(__name__)


async def log_audit(
    user_id: str,
    username: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    detail: dict | None = None,
    ip: str | None = None,
) -> None:
    """写入一条审计日志。内部异常静默处理，不影响主流程。"""
    try:
        async with async_session() as s:
            s.add(AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=detail,
                ip_address=ip,
            ))
            await s.commit()
    except Exception as e:
        _log.warning("audit.log_failed", error=str(e), action=action, resource_type=resource_type)


async def query_audit_logs(
    user_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLog]:
    """查询审计日志，可按 user/action/resource_type 过滤。"""
    async with async_session() as s:
        q = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        if user_id:
            q = q.where(AuditLog.user_id == user_id)
        if action:
            q = q.where(AuditLog.action == action)
        if resource_type:
            q = q.where(AuditLog.resource_type == resource_type)
        return list((await s.execute(q)).scalars().all())
