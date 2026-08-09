"""数据库会话模块。

创建全局异步 SQLAlchemy 引擎与会话工厂，并提供 FastAPI 依赖注入用的 get_db 生成器。
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings

engine = create_async_engine(settings.database_url, pool_size=10, max_overflow=20, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """获取异步数据库会话的依赖生成器。

    yields 一个 AsyncSession，请求结束自动关闭；典型用法：
    ``db: AsyncSession = Depends(get_db)``。
    """
    async with async_session() as s:
        yield s
