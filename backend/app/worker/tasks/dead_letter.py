"""死信队列处理

处理超过最大重试次数的任务。
"""
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

from celery import shared_task
from celery.signals import task_failure

from app.core.redis_streams import publish_event
from app.db.session import async_session
from sqlalchemy import select, insert, update
from sqlalchemy.dialects.postgresql import JSONB

logger = logging.getLogger(__name__)


# 死信队列配置
DEAD_LETTER_MAX_RETRIES = 3
DEAD_LETTER_QUEUE = "dead_letter"
DEAD_LETTER_STREAM = "dead_letter:events"


@dataclass
class DeadLetterTask:
    """死信任务数据结构"""
    task_id: str
    task_name: str
    args: tuple
    kwargs: dict
    exception: str
    traceback: str
    timestamp: datetime
    retry_count: int
    max_retries: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "args": json.dumps(self.args, default=str),
            "kwargs": json.dumps(self.kwargs, default=str),
            "exception": self.exception,
            "traceback": self.traceback,
            "timestamp": self.timestamp.isoformat(),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


class DeadLetterQueue:
    """死信队列管理器"""
    
    @staticmethod
    async def add_to_dlq(
        task_id: str,
        task_name: str,
        args: tuple,
        kwargs: dict,
        exception: Exception,
        traceback_str: str,
        retry_count: int,
        max_retries: int
    ):
        """将失败任务添加到死信队列"""
        
        dl_task = DeadLetterTask(
            task_id=task_id,
            task_name=task_name,
            args=args,
            kwargs=kwargs,
            exception=str(exception),
            traceback=traceback_str,
            timestamp=datetime.utcnow(),
            retry_count=retry_count,
            max_retries=max_retries
        )
        
        # 1. 记录到数据库
        try:
            async with async_session() as session:
                # TODO: 创建 dead_letter_tasks 表
                # from app.models.dead_letter import DeadLetterTaskModel
                # session.add(DeadLetterTaskModel(**dl_task.to_dict()))
                # await session.commit()
                pass
        except Exception as e:
            logger.error(f"Failed to save DLQ task to DB: {e}")
        
        # 2. 发布到 Streams
        try:
            await publish_event(
                DEAD_LETTER_STREAM,
                "task_failed_permanently",
                dl_task.to_dict()
            )
        except Exception as e:
            logger.error(f"Failed to publish DLQ event: {e}")
        
        # 3. 记录日志
        logger.error(
            f"Task moved to DLQ: {task_name}[{task_id}], "
            f"retry_count={retry_count}/{max_retries}, "
            f"exception={exception}"
        )
    
    @staticmethod
    async def retry_dlq_task(task_id: str):
        """手动重试死信队列中的任务"""
        # TODO: 实现手动重试逻辑
        logger.info(f"Retrying DLQ task: {task_id}")
        pass
    
    @staticmethod
    async def get_dlq_stats() -> Dict[str, Any]:
        """获取死信队列统计"""
        # TODO: 从数据库统计
        return {
            "total_failed": 0,
            "by_task_type": {},
            "last_24h": 0,
        }


# Celery 信号处理
@task_failure.connect
def handle_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **extra):
    """
    任务失败信号处理
    
    当任务达到最大重试次数时，添加到死信队列
    """
    retry_count = sender.request.retries
    max_retries = sender.max_retries
    
    # 只在达到最大重试次数时处理
    if retry_count >= max_retries:
        asyncio.run(DeadLetterQueue.add_to_dlq(
            task_id=task_id,
            task_name=sender.name,
            args=args,
            kwargs=kwargs,
            exception=exception,
            traceback_str=str(traceback) if traceback else "",
            retry_count=retry_count,
            max_retries=max_retries
        ))


# 死信队列监控任务
@shared_task(name="dlq.monitor")
def monitor_dead_letter_queue():
    """
    定时监控死信队列
    
    每小时检查一次死信队列，发送告警
    """
    import asyncio
    
    async def _check():
        stats = await DeadLetterQueue.get_dlq_stats()
        
        # 如果有失败任务，发送告警
        if stats["total_failed"] > 0:
            logger.warning(
                f"DLQ Alert: {stats[\'total_failed\']} failed tasks in queue, "
                f"last_24h={stats[\'last_24h\']}"
            )
            
            # TODO: 发送邮件/Slack 告警
            # await send_alert(f"Dead Letter Queue has {stats[\'total_failed\']} tasks")
    
    asyncio.run(_check())


# 死信队列清理任务
@shared_task(name="dlq.cleanup")
def cleanup_old_dlq_tasks(days: int = 30):
    """
    清理过期的死信队列任务
    
    Args:
        days: 保留天数，默认 30 天
    """
    import asyncio
    from datetime import timedelta
    
    async def _cleanup():
        cutoff = datetime.utcnow() - timedelta(days=days)
        logger.info(f"Cleaning up DLQ tasks older than {cutoff}")
        
        # TODO: 从数据库删除旧任务
        # async with async_session() as session:
        #     await session.execute(
        #         delete(DeadLetterTaskModel)
        #         .where(DeadLetterTaskModel.created_at < cutoff)
        #     )
        #     await session.commit()
    
    asyncio.run(_cleanup())
