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
        """转换为字典格式。

        Returns:
            包含所有属性的字典，用于序列化。

        Raises:
            不会抛出异常，使用安全的序列化方法。
        """
        try:
            args_json = json.dumps(self.args, default=str)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize args: {e}, using empty list")
            args_json = json.dumps([])

        try:
            kwargs_json = json.dumps(self.kwargs, default=str)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize kwargs: {e}, using empty dict")
            kwargs_json = json.dumps({})

        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "args": args_json,
            "kwargs": kwargs_json,
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
        """将失败任务添加到死信队列。

        先将任务持久化到数据库，成功后再发布到 Redis Streams。
        如果数据库保存失败，记录错误但不发布事件，避免数据不一致。

        Args:
            task_id: Celery 任务 ID。
            task_name: 任务名称。
            args: 任务位置参数。
            kwargs: 任务关键字参数。
            exception: 异常实例。
            traceback_str: 堆栈跟踪字符串。
            retry_count: 当前重试次数。
            max_retries: 最大重试次数。

        Returns:
            None

        Raises:
            不会抛出异常，所有错误都会被捕获并记录。
        """

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

        # 安全序列化 args 和 kwargs
        try:
            args_json = json.dumps(args, default=str)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize args for {task_id}: {e}, using empty list")
            args_json = json.dumps([])

        try:
            kwargs_json = json.dumps(kwargs, default=str)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize kwargs for {task_id}: {e}, using empty dict")
            kwargs_json = json.dumps({})

        # 1. 记录到数据库（必须成功）
        db_success = False
        try:
            async with async_session() as session:
                from app.models.dead_letter import DeadLetterTaskModel, TaskStatus

                db_task = DeadLetterTaskModel(
                    task_id=task_id,
                    task_name=task_name,
                    args=args_json,
                    kwargs=kwargs_json,
                    exception=str(exception),
                    traceback=traceback_str,
                    retry_count=retry_count,
                    max_retries=max_retries,
                    status=TaskStatus.PENDING.value,
                )
                session.add(db_task)
                await session.commit()
                db_success = True
                logger.info(f"DLQ task saved to DB: {task_id}")
        except Exception as e:
            logger.error(f"Failed to save DLQ task to DB: {e}, task_id={task_id}")
            # 不继续发布到 Streams，避免数据不一致

        # 2. 仅在数据库保存成功后，发布到 Streams
        if db_success:
            try:
                await publish_event(
                    DEAD_LETTER_STREAM,
                    "task_failed_permanently",
                    dl_task.to_dict()
                )
            except Exception as e:
                logger.error(f"Failed to publish DLQ event for {task_id}: {e}")
                # Streams 发布失败不影响已入库的数据
        else:
            logger.warning(f"Skipping Streams publish for {task_id} due to DB save failure")

        # 3. 记录日志
        logger.error(
            f"Task moved to DLQ: {task_name}[{task_id}], "
            f"retry_count={retry_count}/{max_retries}, "
            f"exception={exception}"
        )
    
    @staticmethod
    async def retry_dlq_task(task_id: str, user_id: str = None) -> bool:
        """手动重试死信队列中的任务。

        从数据库中查找指定的死信任务，解析其参数并重新提交到 Celery 队列。

        Args:
            task_id: Celery 任务 ID，唯一标识要重试的任务。
            user_id: 操作用户 ID，用于审计追踪（可选）。

        Returns:
            bool: 重试成功返回 True，失败返回 False。

        Raises:
            不会抛出异常，所有错误都会被捕获并记录。
        """
        from app.core.celery_app import celery_app
        from app.models.dead_letter import DeadLetterTaskModel, TaskStatus

        async with async_session() as session:
            # 查询死信任务
            result = await session.execute(
                select(DeadLetterTaskModel).where(DeadLetterTaskModel.task_id == task_id)
            )
            dl_task = result.scalar_one_or_none()

            if not dl_task:
                logger.warning(f"DLQ task not found: {task_id}")
                return False

            if dl_task.status != TaskStatus.PENDING:
                logger.warning(f"DLQ task already processed: {task_id}, status={dl_task.status}")
                return False

            try:
                # 解析参数（注意：args 和 kwargs 是 JSONB 类型，需要转换）
                args = tuple(dl_task.args) if dl_task.args else ()
                kwargs = dict(dl_task.kwargs) if dl_task.kwargs else {}

                # 重新提交任务
                celery_app.send_task(
                    dl_task.task_name,
                    args=args,
                    kwargs=kwargs,
                    queue=_get_queue_for_task(dl_task.task_name),
                )

                # 更新状态
                dl_task.status = TaskStatus.RETRIED
                dl_task.retried_at = datetime.utcnow()
                if user_id:
                    import uuid
                    dl_task.retried_by = uuid.UUID(user_id)

                await session.commit()
                logger.info(f"DLQ task retried: {task_id}")
                return True

            except Exception as e:
                logger.error(f"Failed to retry DLQ task {task_id}: {e}")
                return False
    
    @staticmethod
    async def get_dlq_stats() -> Dict[str, Any]:
        """获取死信队列统计。

        Returns:
            包含以下键的字典：
            - total_failed: 待处理失败任务总数
            - by_task_type: 按任务类型统计
            - last_24h: 最近 24 小时新增失败任务数
        """
        from app.models.dead_letter import DeadLetterTaskModel, TaskStatus
        from sqlalchemy import func

        async with async_session() as session:
            # 总数（仅统计 PENDING 状态）
            total_result = await session.execute(
                select(func.count(DeadLetterTaskModel.id))
                .where(DeadLetterTaskModel.status == TaskStatus.PENDING.value)
            )
            total_failed = total_result.scalar()

            # 按任务类型统计（仅 PENDING 状态）
            type_result = await session.execute(
                select(
                    DeadLetterTaskModel.task_name,
                    func.count(DeadLetterTaskModel.id)
                )
                .where(DeadLetterTaskModel.status == TaskStatus.PENDING.value)
                .group_by(DeadLetterTaskModel.task_name)
            )
            by_task_type = dict(type_result.all())

            # 最近 24 小时（仅 PENDING 状态）
            from datetime import timedelta
            recent_result = await session.execute(
                select(func.count(DeadLetterTaskModel.id))
                .where(DeadLetterTaskModel.status == TaskStatus.PENDING.value)
                .where(DeadLetterTaskModel.created_at >= datetime.utcnow() - timedelta(hours=24))
            )
            last_24h = recent_result.scalar()

        return {
            "total_failed": total_failed,
            "by_task_type": by_task_type,
            "last_24h": last_24h,
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
        # 安全地运行异步代码，避免事件循环冲突
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # 如果没有事件循环，创建一个新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(DeadLetterQueue.add_to_dlq(
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
    """定时监控死信队列。

    每小时检查一次死信队列，发送告警。
    """

    async def _check():
        stats = await DeadLetterQueue.get_dlq_stats()

        # 如果有失败任务，发送告警
        if stats["total_failed"] > 0:
            logger.warning(
                f"DLQ Alert: {stats['total_failed']} failed tasks in queue, "
                f"last_24h={stats['last_24h']}"
            )

            # 发送告警（邮件/Slack/钉钉等）
            await _send_alert(
                title="EasyRAG 死信队列告警",
                message=f"当前有 {stats['total_failed']} 个失败任务待处理，"
                        f"最近 24 小时新增 {stats['last_24h']} 个。",
                details=stats
            )

    # 安全地运行异步代码
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_check())


async def _send_alert(title: str, message: str, details: dict):
    """发送告警通知。

    支持多种告警渠道：邮件、Slack、钉钉等。

    Args:
        title: 告警标题
        message: 告警消息
        details: 详细信息
    """
    from app.config import settings

    # 邮件告警
    alert_email = getattr(settings, "alert_email", None)
    if alert_email:
        try:
            # TODO: 集成邮件发送服务
            # await send_email(to=alert_email, subject=title, body=message)
            logger.info(f"Alert email would be sent to {alert_email}: {message}")
        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")

    # Slack Webhook
    slack_webhook = getattr(settings, "slack_webhook_url", None)
    if slack_webhook:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.post(
                    slack_webhook,
                    json={
                        "text": title,
                        "attachments": [
                            {
                                "text": message,
                                "fields": [
                                    {"title": k, "value": str(v), "short": True}
                                    for k, v in details.items()
                                ]
                            }
                        ]
                    }
                )
            logger.info("Alert sent to Slack")
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

    # 钉钉 Webhook
    dingtalk_webhook = getattr(settings, "dingtalk_webhook_url", None)
    if dingtalk_webhook:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.post(
                    dingtalk_webhook,
                    json={
                        "msgtype": "text",
                        "text": {"content": f"{title}\n\n{message}"}
                    }
                )
            logger.info("Alert sent to DingTalk")
        except Exception as e:
            logger.error(f"Failed to send DingTalk alert: {e}")


# 死信队列清理任务
@shared_task(name="dlq.cleanup")
def cleanup_old_dlq_tasks(days: int = 30):
    """清理过期的死信队列任务。

    Args:
        days: 保留天数，默认 30 天
    """
    from datetime import timedelta

    async def _cleanup():
        cutoff = datetime.utcnow() - timedelta(days=days)
        logger.info(f"Cleaning up DLQ tasks older than {cutoff}")

        async with async_session() as session:
            from sqlalchemy import delete
            from app.models.dead_letter import DeadLetterTaskModel, TaskStatus

            # 只删除已处理的任务（retried/ignored）
            result = await session.execute(
                delete(DeadLetterTaskModel)
                .where(DeadLetterTaskModel.created_at < cutoff)
                .where(DeadLetterTaskModel.status.in_([TaskStatus.RETRIED.value, TaskStatus.IGNORED.value]))
            )
            deleted = result.rowcount
            await session.commit()

            logger.info(f"Deleted {deleted} old DLQ tasks")

    # 安全地运行异步代码
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_cleanup())


def _get_queue_for_task(task_name: str) -> str:
    """根据任务名称确定队列。

    Args:
        task_name: 任务名称，如 "parse_document"。

    Returns:
        队列名称，如 "parse"、"workflow"、"agent" 或 "default"。
    """
    if task_name.startswith("parse"):
        return "parse"
    elif task_name.startswith("workflow"):
        return "workflow"
    elif task_name.startswith("agent"):
        return "agent"
    return "default"
