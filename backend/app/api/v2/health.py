"""健康检查路由模块。"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.response import ok
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """健康检查接口。

    执行 ``SELECT 1`` 探测数据库连通性，正常返回 status=ok，异常返回 degraded。
    """
    try:
        (await db.execute(text("SELECT 1"))).scalar()
        return ok({"status": "ok", "db": "ok"})
    except Exception as e:
        return ok({"status": "degraded", "db": str(e)})
