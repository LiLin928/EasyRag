"""Celery 应用配置

提供 Celery 应用实例和任务注册。
"""
from celery import Celery
import os

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

    # 队列路由 - 按业务分类
    task_routes={
        "parse.*": {"queue": "parse"},
        "workflow.*": {"queue": "workflow"},
        "agent.*": {"queue": "agent"},
    },

    # 重试配置
    task_max_retries=3,
    task_default_retry_delay=60,  # 60秒后重试

    # Worker 配置
    worker_prefetch_multiplier=1,
    worker_concurrency=4,

    # 结果过期时间
    result_expires=3600,

    # 任务追踪
    task_track_started=True,
    task_time_limit=3600,  # 任务硬超时 1 小时
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
}


def get_celery_app():
    """获取 Celery 应用实例"""
    return celery_app


# 调试：打印配置
if __name__ == "__main__":
    print("Celery App Config:")
    print(f"  Broker: {celery_app.conf.broker_url}")
    print(f"  Backend: {celery_app.conf.result_backend}")
    print(f"  Queues: default, parse, workflow, agent")
