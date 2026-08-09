"""ARQ worker 配置。

parse_document_task 在 Task 11 追加到 functions 注册表。
"""
from arq.connections import RedisSettings

from app.config import settings


async def startup(ctx):
    """worker 启动钩子。"""
    ctx["ok"] = True


class WorkerSettings:
    """ARQ WorkerSettings：函数表、redis 连接、并发与重试参数。"""

    functions = []  # Task 11 追加 parse_document_task
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    max_jobs = 4
    job_timeout = 600
    max_tries = 3
