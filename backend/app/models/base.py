"""ORM 模型基类模块。

定义声明式基类 Base 以及通用的主键、时间戳混入。
"""
import uuid
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的声明式基类。"""
    pass


class TimestampMixin:
    """时间戳混入，为模型增加 created_at / updated_at 字段。

    Attributes:
        created_at: 创建时间，默认为入库时数据库当前时间。
        updated_at: 更新时间，每次更新时刷新为数据库当前时间。
    """

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class UUIDPk:
    """UUID 主键混入，为模型增加 UUID 类型自增主键 id。

    Attributes:
        id: 主键，默认由 uuid.uuid4 生成。
    """

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
