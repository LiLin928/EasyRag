"""通用 schema 模块。

定义统一响应体 ApiResponse 与分页参数 PaginationParams。
"""
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应体结构。

    Attributes:
        code: 业务码，0 表示成功，非 0 表示业务错误。
        message: 提示消息。
        data: 业务数据载荷，泛型。
    """

    code: int
    message: str
    data: Optional[T] = None


class PaginationParams(BaseModel):
    """分页参数。

    Attributes:
        page: 页码，从 1 开始。
        page_size: 每页条数，默认 20。
    """

    page: int = 1
    page_size: int = 20
