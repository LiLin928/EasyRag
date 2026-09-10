"""应用层指标采集。

使用 prometheus-fastapi-instrumentator 自动采集 HTTP 指标。
"""
from prometheus_fastapi_instrumentator import Instrumentator
from app.config import settings


def setup_app_metrics(app):
    """配置 FastAPI 应用指标采集。

    Args:
        app: FastAPI 应用实例
    """
    if not settings.prometheus_enabled:
        return

    # 设置环境变量以启用 Prometheus 指标
    import os
    os.environ["PROMETHEUS_ENABLED"] = "true"

    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        env_var_name="PROMETHEUS_ENABLED",
    )

    instrumentator.instrument(app).expose(app)