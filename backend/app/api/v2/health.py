"""健康检查路由。"""
from datetime import datetime
from fastapi import APIRouter

from app.api.response import ok
from app.core.engine.pg_queue import PGJobQueue
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from sqlalchemy import text

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    """基础健康检查。"""
    return ok({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "EasyRAG"
    })


@router.get("/workers")
async def worker_health():
    """Worker 健康状态。
    
    返回队列状态和运行中的 worker 列表。
    """
    async with async_session() as s:
        pending = await PGJobQueue.count_pending(s)
        running = await PGJobQueue.count_running(s)
        workers = await PGJobQueue.list_workers(s)
    
    return ok({
        "queue": {
            "pending": pending,
            "running": running,
        },
        "workers": [
            {
                "id": w["worker_id"],
                "status": "active",
                "last_heartbeat": w["last_active"].isoformat() if w["last_active"] else None
            }
            for w in workers
        ],
        "timestamp": datetime.now().isoformat()
    })


@router.get("/ready")
async def readiness_check():
    """就绪检查：数据库连接。
    
    用于 Kubernetes readiness probe。
    """
    try:
        async with async_session() as s:
            await s.execute(text("SELECT 1"))
        return ok({"status": "ready"})
    except Exception as e:
        raise BizException(ErrorCode.SERVICE_ERROR, f"Database not ready: {e}")


@router.get("/live")
async def liveness_check():
    """存活检查。
    
    用于 Kubernetes liveness probe。
    """
    return ok({"status": "alive"})
