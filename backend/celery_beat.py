"""Celery Beat 定时任务配置

定义周期性任务
"""
from celery import Celery
from celery.schedules import crontab

from app.core.celery_app import celery_app

# 定时任务配置
celery_app.conf.beat_schedule = {
    # 清理过期任务结果 (每天凌晨)
    "cleanup-task-results": {
        "task": "beat.cleanup_results",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "default"},
    },
    
    # 清理过期 Streams (每天凌晨 3 点)
    "cleanup-expired-streams": {
        "task": "beat.cleanup_streams",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "default"},
    },
    
    # 死信队列监控 (每小时)
    "monitor-dlq": {
        "task": "dlq.monitor",
        "schedule": 3600.0,  # 每小时
        "options": {"queue": "default"},
    },
    
    # 死信队列清理 (每天凌晨 4 点)
    "cleanup-dlq": {
        "task": "dlq.cleanup",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": "default"},
    },
    
    # 健康检查 (每 5 分钟)
    "health-check": {
        "task": "beat.health_check",
        "schedule": 300.0,  # 5 分钟
        "options": {"queue": "default"},
    },
    
    # 统计上报 (每小时)
    "report-stats": {
        "task": "beat.report_stats",
        "schedule": 3600.0,
        "options": {"queue": "default"},
    },
}


# 定时任务
@celery_app.task(name="beat.cleanup_results")
def cleanup_task_results():
    """清理过期的任务结果"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Cleaning up expired task results...")
    
    # Celery 会自动清理，这里可以做额外清理
    from celery.app.control import Control
    
    # 清理 MongoDB/Redis 中的旧结果
    # 默认 Celery 会按 result_expires 自动清理
    logger.info("Task results cleanup completed")


@celery_app.task(name="beat.cleanup_streams")
def cleanup_expired_streams():
    """清理过期的 Redis Streams"""
    import logging
    import asyncio
    import redis.asyncio as aioredis
    
    logger = logging.getLogger(__name__)
    logger.info("Cleaning up expired streams...")
    
    async def _cleanup():
        from app.core.config import settings
        
        redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        
        # 查找所有 parse:* 和 workflow:* streams
        patterns = ["parse:*", "workflow:*", "agent:*"]
        
        total_trimmed = 0
        for pattern in patterns:
            keys = await redis.keys(pattern)
            for key in keys:
                # 只保留最新的 1000 条
                trimmed = await redis.xtrim(key, maxlen=1000, approximate=True)
                total_trimmed += trimmed
        
        await redis.close()
        logger.info(f"Streams cleanup completed, trimmed {total_trimmed} messages")
    
    asyncio.run(_cleanup())


@celery_app.task(name="beat.health_check")
def health_check():
    """系统健康检查"""
    import logging
    import asyncio
    import redis.asyncio as aioredis
    from sqlalchemy import text
    
    from app.db.session import async_session
    
    logger = logging.getLogger(__name__)
    
    results = {
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # 检查 PostgreSQL
    try:
        async def check_pg():
            async with async_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        
        pg_ok = asyncio.run(check_pg())
        results["checks"]["postgresql"] = "healthy" if pg_ok else "unhealthy"
    except Exception as e:
        results["checks"]["postgresql"] = f"error: {e}"
        logger.error(f"PostgreSQL health check failed: {e}")
    
    # 检查 Redis
    try:
        async def check_redis():
            redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)
            pong = await redis.ping()
            await redis.close()
            return pong
        
        redis_ok = asyncio.run(check_redis())
        results["checks"]["redis"] = "healthy" if redis_ok else "unhealthy"
    except Exception as e:
        results["checks"]["redis"] = f"error: {e}"
        logger.error(f"Redis health check failed: {e}")
    
    # 检查队列长度
    try:
        async def check_queues():
            redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)
            
            queue_lengths = {}
            for queue in ["default", "parse", "workflow", "agent"]:
                length = await redis.llen(f"celery@{queue}")
                queue_lengths[queue] = length
            
            await redis.close()
            return queue_lengths
        
        queue_lengths = asyncio.run(check_queues())
        results["checks"]["queues"] = queue_lengths
        
        # 告警：队列堆积
        for queue, length in queue_lengths.items():
            if length > 1000:
                logger.warning(f"Queue {queue} has {length} pending tasks!")
                
    except Exception as e:
        results["checks"]["queues"] = f"error: {e}"
    
    # 总结
    all_healthy = all(
        v == "healthy" for v in results["checks"].values()
        if isinstance(v, str)
    )
    results["status"] = "healthy" if all_healthy else "degraded"
    
    logger.info(f"Health check: {results[\'status\']}")
    return results


@celery_app.task(name="beat.report_stats")
def report_stats():
    """统计上报"""
    import logging
    from datetime import datetime, timedelta
    
    logger = logging.getLogger(__name__)
    logger.info("Reporting statistics...")
    
    # 收集统计信息
    stats = {
        "timestamp": datetime.utcnow().isoformat(),
        "period": "hourly",
    }
    
    # TODO: 从数据库和 Redis 收集统计
    # - 任务执行数量
    # - 成功率
    # - 平均执行时间
    # - 队列长度趋势
    
    logger.info(f"Statistics reported: {stats}")
    return stats
