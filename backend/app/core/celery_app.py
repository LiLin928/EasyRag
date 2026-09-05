"""Celery 应用配置

提供 Celery 应用实例和任务注册。
"""
from celery import Celery
import os

# 从环境变量读取 Redis URL，默认为本地
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# 创建 Celery 应用
celery_app = Celery(
    "easyrag",
    # 使用 Redis 作为 broker 和 backend
    broker=f"{REDIS_URL}/0",           # 队列
    backend=f"{REDIS_URL}/1",          # 结果存储
    # 包含任务模块
    include=[
        "app.worker.tasks.parse_tasks",
        "app.worker.tasks.workflow_tasks",
        "app.worker.tasks.agent_tasks",
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


def get_celery_app():
    """获取 Celery 应用实例"""
    return celery_app


# 调试：打印配置
if __name__ == "__main__":
    print("Celery App Config:")
    print(f"  Broker: {celery_app.conf.broker_url}")
    print(f"  Backend: {celery_app.conf.result_backend}")
    print(f"  Queues: default, parse, workflow, agent")
