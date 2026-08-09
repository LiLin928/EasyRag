"""parse-tasks 路由：解析进度轮询。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.document import ParseTask

router = APIRouter(tags=["parse-tasks"])


@router.get("/parse-tasks/{task_id}")
async def get_task(task_id: str, me=Depends(get_current_user)):
    """查询解析任务进度（前端轮询用）。"""
    async with async_session() as s:
        t = (await s.execute(select(ParseTask).where(ParseTask.id == task_id))).scalar_one_or_none()
    if not t:
        raise BizException(ErrorCode.NOT_FOUND, "解析任务不存在")
    return ok({"task_id": str(t.id), "doc_id": str(t.doc_id), "status": t.status, "pct": t.pct, "error": t.error})
