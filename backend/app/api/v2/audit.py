"""审计日志查询路由。"""
from fastapi import APIRouter, Depends

from app.api.deps import require_roles
from app.api.response import ok
from app.services.audit_service import query_audit_logs

router = APIRouter(prefix="/audit-logs", tags=["audit"])


def _out(log) -> dict:
    return {
        "id": str(log.id),
        "userId": str(log.user_id),
        "username": log.username,
        "action": log.action,
        "resourceType": log.resource_type,
        "resourceId": log.resource_id,
        "detail": log.detail,
        "ipAddress": log.ip_address,
        "createdAt": log.created_at.isoformat() if log.created_at else "",
    }


@router.get("")
async def list_audit_logs(
    userId: str | None = None,
    action: str | None = None,
    resourceType: str | None = None,
    limit: int = 50,
    offset: int = 0,
    me=Depends(require_roles("admin")),
):
    """查询审计日志（admin 专属）。"""
    logs = await query_audit_logs(
        user_id=userId,
        action=action,
        resource_type=resourceType,
        limit=limit,
        offset=offset,
    )
    return ok([_out(l) for l in logs])
