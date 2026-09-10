"""Webhook API 端点。"""
import hmac
import hashlib
import json
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.db.session import get_db
from app.exceptions import BizException, ErrorCode
from app.models.webhook import Webhook, WebhookTriggerLog
from app.models.workflow import Workflow, WorkflowExecution
from app.api.response import ok

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    workflow_id: str = Field(..., description="关联的工作流ID")
    name: str = Field(..., max_length=100, description="Webhook名称")
    description: Optional[str] = Field(None, description="描述")
    filters: Optional[dict] = Field(None, description="触发条件过滤器")
    rate_limit_per_minute: int = Field(default=60, ge=1, le=1000)


class WebhookUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    filters: Optional[dict] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=1000)


class WebhookResponse(BaseModel):
    id: str
    workflow_id: str
    name: str
    description: Optional[str]
    is_active: bool
    filters: Optional[dict]
    rate_limit_per_minute: int
    trigger_count: int
    created_at: datetime
    updated_at: datetime


class WebhookTriggerPayload(BaseModel):
    event_type: str = Field(..., description="事件类型")
    data: dict = Field(default_factory=dict, description="事件数据")


def verify_webhook_signature(payload: bytes, secret: str, signature: str, version: str = "v1") -> bool:
    """验证Webhook签名。
    
    使用 HMAC-SHA256 算法验证请求完整性。
    """
    if not signature.startswith(f"{version}="):
        return False
    
    expected_signature = signature[len(f"{version}="):]
    
    # 计算HMAC-SHA256
    computed = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed, expected_signature)


@router.post("", response_model=dict)
async def create_webhook(
    data: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """创建Webhook触发器。"""
    # 验证工作流存在且用户有权访问
    workflow = await db.get(Workflow, data.workflow_id)
    if not workflow:
        raise BizException(ErrorCode.NOT_FOUND, "Workflow not found")

    # 验证用户权限：只有工作流所有者才能创建 webhook
    if workflow.user_id != current_user.id:
        raise BizException(ErrorCode.FORBIDDEN, "无权访问该工作流")

    # 生成随机secret
    import secrets
    webhook_secret = secrets.token_hex(32)

    webhook = Webhook(
        workflow_id=data.workflow_id,
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        secret=webhook_secret,
        filters=data.filters,
        rate_limit_per_minute=data.rate_limit_per_minute
    )

    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    return ok({
        "webhook": {
            "id": str(webhook.id),
            "workflow_id": str(webhook.workflow_id),
            "name": webhook.name,
            "secret": webhook_secret[:8] + "****",  # 只返回部分secret
            "is_active": webhook.is_active,
            "filters": webhook.filters,
            "created_at": webhook.created_at.isoformat()
        }
    })


@router.get("", response_model=dict)
async def list_webhooks(
    workflow_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """列出Webhook触发器。"""
    query = select(Webhook).where(Webhook.user_id == current_user.id)
    if workflow_id:
        query = query.where(Webhook.workflow_id == workflow_id)

    result = await db.execute(query)
    webhooks = result.scalars().all()

    return ok({
        "webhooks": [
            {
                "id": str(w.id),
                "workflow_id": str(w.workflow_id),
                "name": w.name,
                "is_active": w.is_active,
                "trigger_count": w.trigger_count,
                "last_triggered_at": w.last_triggered_at.isoformat() if w.last_triggered_at else None,
                "created_at": w.created_at.isoformat()
            }
            for w in webhooks
        ]
    })


@router.post("/trigger/{webhook_token}", response_model=dict)
async def trigger_webhook(
    webhook_token: str,
    request: Request,
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
    x_webhook_version: str = Header("v1", alias="X-Webhook-Version")
):
    """接收Webhook触发请求。
    
    URL格式: /api/v2/webhooks/trigger/{webhook_token}
    需要 Header: X-Webhook-Signature: v1=<hmac_sha256_hex>
    """
    # 读取原始请求体
    body = await request.body()
    
    # 查找webhook
    from sqlalchemy import select
    async with get_db() as db:
        result = await db.execute(
            select(Webhook).where(Webhook.secret == webhook_token)
        )
        webhook = result.scalar_one_or_none()
        
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        
        if not webhook.is_active:
            raise HTTPException(status_code=400, detail="Webhook is inactive")
        
        # 验证签名
        if not x_webhook_signature:
            raise HTTPException(status_code=400, detail="Missing signature")
        
        is_valid = verify_webhook_signature(
            body,
            webhook.secret,
            x_webhook_signature,
            x_webhook_version
        )
        
        # 记录触发日志
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw_body": body.decode('utf-8', errors='ignore')}
        
        log_entry = WebhookTriggerLog(
            webhook_id=webhook.id,
            event_type=payload.get("event_type", "unknown"),
            payload=payload,
            headers=dict(request.headers),
            signature_valid=is_valid
        )
        db.add(log_entry)
        
        if not is_valid:
            await db.commit()
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # 检查过滤器
        event_type = payload.get("event_type")
        if webhook.filters and webhook.filters.get("event_type"):
            if webhook.filters["event_type"] != event_type:
                log_entry.status = "filtered"
                await db.commit()
                return ok({"status": "filtered", "reason": "Event type mismatch"})
        
        # 触发工作流执行
        from app.core.engine.celery_client import enqueue_workflow_task
        execution_id = await enqueue_workflow_task(
            workflow_id=str(webhook.workflow_id),
            inputs=payload.get("data", {}),
            trigger="webhook",
            user_id=None
        )

        log_entry.status = "running"
        log_entry.processed_at = datetime.utcnow()

        # 更新webhook统计
        webhook.last_triggered_at = datetime.utcnow()
        webhook.trigger_count += 1

        await db.commit()

    return ok({
        "status": "triggered",
        "execution_id": execution_id
    })


@router.get("/logs", response_model=dict)
async def get_webhook_logs(
    webhook_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """获取Webhook触发日志。"""
    query = select(WebhookTriggerLog).order_by(WebhookTriggerLog.created_at.desc())
    
    if webhook_id:
        query = query.where(WebhookTriggerLog.webhook_id == webhook_id)
    
    result = await db.execute(query.limit(limit).offset(offset))
    logs = result.scalars().all()
    
    return ok({
        "logs": [
            {
                "id": str(log.id),
                "webhook_id": str(log.webhook_id),
                "event_type": log.event_type,
                "status": log.status,
                "signature_valid": log.signature_valid,
                "created_at": log.created_at.isoformat(),
                "processed_at": log.processed_at.isoformat() if log.processed_at else None
            }
            for log in logs
        ]
    })
