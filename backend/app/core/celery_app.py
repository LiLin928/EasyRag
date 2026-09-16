"""Celery 应用配置

提供 Celery 应用实例和任务注册。
"""
# 在最顶部加载 .env 文件，确保环境变量已加载
from dotenv import load_dotenv
load_dotenv()

from celery import Celery
from celery.signals import worker_process_init
from kombu import Queue
import os
import asyncio
import logging

logger = logging.getLogger(__name__)

# 优先使用 Celery 专用配置，回退到通用 Redis URL
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL", "redis://localhost:6379")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND") or os.getenv("REDIS_URL", "redis://localhost:6379")

# 如果 REDIS_URL 没有指定数据库，自动添加
if CELERY_BROKER_URL and not CELERY_BROKER_URL.endswith(("/0", "/1")):
    CELERY_BROKER_URL = f"{CELERY_BROKER_URL}/0"
if CELERY_RESULT_BACKEND and not CELERY_RESULT_BACKEND.endswith(("/0", "/1")):
    CELERY_RESULT_BACKEND = f"{CELERY_RESULT_BACKEND}/1"

# 创建 Celery 应用
celery_app = Celery(
    "easyrag",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    # 包含任务模块
    include=[
        "app.worker.tasks.parse_tasks",
        "app.worker.tasks.workflow_tasks",
        "app.worker.tasks.agent_tasks",
        "app.worker.tasks.dead_letter",  # 死信队列任务
        "app.worker.tasks.sse_cleanup",  # SSE 连接清理任务
    ],
)

# 可选配置
celery_app.conf.update(
    # 序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,

    # 任务默认配置
    task_default_queue="default",
    task_default_routing_key="default",

    # 优先级队列配置
    task_queues={
        "high": Queue("high", routing_key="high"),
        "default": Queue("default", routing_key="default"),
        "low": Queue("low", routing_key="low"),
        "parse": Queue("parse", routing_key="parse"),
        "workflow": Queue("workflow", routing_key="workflow"),
        "agent": Queue("agent", routing_key="agent"),
    },

    # 队列路由 - 按业务分类 + 优先级
    task_routes={
        # 业务队列路由
        "parse.*": {"queue": "parse"},
        "workflow.*": {"queue": "workflow"},
        "agent.*": {"queue": "agent"},
        # 高优先级任务
        "workflow.urgent": {"queue": "high"},
        # 低优先级任务
        "cleanup.*": {"queue": "low"},
        "retrieval_test.*": {"queue": "low"},
    },

    # 重试配置
    task_max_retries=3,
    task_default_retry_delay=60,  # 60秒后重试

    # Worker 配置 - Windows 兼容
    # Windows 不支持 prefork，使用 solo 模式
    # 注意：solo 模式不支持并发，一次只能处理一个任务
    worker_pool="solo",  # Windows 兼容模式
    worker_prefetch_multiplier=1,
    worker_concurrency=1,  # solo 模式下 concurrency 应为 1

    # 结果过期时间
    result_expires=3600,

    # 任务追踪
    task_track_started=True,
    task_time_limit=3600,  # 任务硬超时 1 小时
    task_soft_time_limit=3300,  # 软超时 55 分钟，提前 5 分钟警告

    # 延迟确认 - 任务完成后再确认，避免任务丢失
    task_acks_late=True,
)

# Celery Beat 定时任务
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "monitor-dlq": {
        "task": "dlq.monitor",
        "schedule": crontab(minute=0),  # 每小时执行
    },
    "cleanup-dlq": {
        "task": "dlq.cleanup",
        "schedule": crontab(hour=2, minute=0),  # 每天凌晨 2 点执行
        "args": (30,),  # 保留 30 天
    },
    "cleanup-sse": {
        "task": "sse.cleanup_expired",
        "schedule": crontab(minute="*/5"),  # 每 5 分钟执行
    },
}


def get_celery_app():
    """获取 Celery 应用实例"""
    return celery_app


# Worker 进程初始化钩子
@worker_process_init.connect
def init_worker_process(**kwargs):
    """Celery worker 进程启动时初始化资源"""
    logger.info("[Celery] Worker process initializing...")

    # 设置环境变量标识这是 Celery worker
    import os
    os.environ['CELERY_WORKER'] = 'true'
    logger.info("[Celery] Set CELERY_WORKER=true for NullPool database connections")

    # Windows 兼容性：设置正确的事件循环策略
    import sys
    if sys.platform == 'win32':
        import asyncio
        from asyncio import WindowsSelectorEventLoopPolicy
        asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
        logger.info("[Celery] Set WindowsSelectorEventLoopPolicy for asyncpg compatibility")

    # 初始化 checkpointer（在事件循环中运行）
    try:
        from app.core.agent.memory import get_checkpointer
        checkpointer = asyncio.run(get_checkpointer())
        logger.info(f"[Celery] Checkpointer initialized: {type(checkpointer)}")
    except Exception as e:
        logger.error(f"[Celery] Failed to initialize checkpointer: {e}", exc_info=True)

    logger.info("[Celery] Worker process initialized")


# 调试：打印配置
if __name__ == "__main__":
    print("Celery App Config:")
    print(f"  Broker: {celery_app.conf.broker_url}")
    print(f"  Backend: {celery_app.conf.result_backend}")
    print(f"  Queues: high, default, low, parse, workflow, agent")
