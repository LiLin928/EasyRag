"""统一响应封装模块。

提供 ok/err 工具函数，生成符合 ApiResponse 结构的字典。
"""
from typing import Any
from app.exceptions import ErrorCode


def ok(data: Any = None, message: str = "success") -> dict:
    """构造成功响应字典。

    Args:
        data: 业务数据载荷，默认空。
        message: 提示消息，默认 "success"。

    Returns:
        形如 ``{"code": 0, "message": ..., "data": ...}`` 的字典。
    """
    return {"code": 0, "message": message, "data": data}


def err(code: ErrorCode | int, message: str) -> dict:
    """构造失败响应字典。

    Args:
        code: 错误码。
        message: 错误消息。

    Returns:
        形如 ``{"code": <code>, "message": ..., "data": None}`` 的字典。
    """
    return {"code": int(code), "message": message, "data": None}
