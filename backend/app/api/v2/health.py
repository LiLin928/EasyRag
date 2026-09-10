"""健康检查路由。"""
from datetime import datetime
from fastapi import APIRouter

from app.api.response import ok
from app.core.celery_app import celery_app
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
    # 使用 Celery Inspect API 获取 worker 状态
    inspect = celery_app.control.inspect()

    # 获取活跃任务
    active_tasks = inspect.active() or {}
    reserved_tasks = inspect.reserved() or {}

    # 统计任务数
    pending_count = sum(len(tasks) for tasks in reserved_tasks.values())
    running_count = sum(len(tasks) for tasks in active_tasks.values())

    # 获取 worker 列表
    stats = inspect.stats() or {}
    workers = []
    for worker_name, worker_stats in stats.items():
        workers.append({
            "id": worker_name,
            "status": "active",
            "last_heartbeat": datetime.now().isoformat()
        })

    return ok({
        "queue": {
            "pending": pending_count,
            "running": running_count,
        },
        "workers": workers,
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
