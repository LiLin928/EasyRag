"""数据库会话模块。

创建全局异步 SQLAlchemy 引擎与会话工厂，并提供 FastAPI 依赖注入用的 get_db 生成器。
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.config import settings

# Celery worker 环境：使用 NullPool 避免连接池跨事件循环问题
# NullPool 不会持久化连接，每次都创建新连接，避免跨事件循环的 Future 问题
import os
_use_null_pool = os.getenv('CELERY_WORKER') == 'true' or 'celery' in ' '.join(os.sys.argv)

# 添加 pool_pre_ping=True 以检查连接健康，避免使用失效连接
if _use_null_pool:
    # Celery worker：使用 NullPool，不设置 pool_size
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,  # 连接健康检查
        poolclass=NullPool,  # 不持久化连接池
    )
else:
    # FastAPI 服务：使用连接池
    engine = create_async_engine(
        settings.database_url,
        pool_size=10,
        max_overflow=20,
        echo=False,
        pool_pre_ping=True,  # 连接健康检查
    )

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """获取异步数据库会话的依赖生成器。

    yields 一个 AsyncSession，请求结束自动关闭；典型用法：
    ``db: AsyncSession = Depends(get_db)``。
    """
    async with async_session() as s:
        yield s
