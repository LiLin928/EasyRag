"""日志配置模块。

基于 structlog 配置结构化 JSON 日志，并提供请求 id 生成工具。
"""
import logging
import uuid
import structlog
from app.config import settings


def setup_logging() -> None:
    """初始化全局日志配置。

    同步配置标准 logging 等级，并为 structlog 启用 JSON 渲染、时间戳、
    日志等级以及 contextvars 合并等处理器。
    """
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level.upper(), logging.INFO)),
        cache_logger_on_first_use=True,
    )


def new_request_id() -> str:
    """生成一个新的请求 id（uuid4 的 hex 字符串）。"""
    return uuid.uuid4().hex
