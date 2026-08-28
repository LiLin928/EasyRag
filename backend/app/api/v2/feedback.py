"""feedback 路由：用户反馈（like/dislike）。"""
import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.conversation import Feedback
from app.models.user import User
from app.schemas.chat import FeedbackCreate

router = APIRouter(tags=["feedback"])


@router.post("/feedback")
async def create_feedback(body: FeedbackCreate, me: User = Depends(get_current_user)):
    """记录用户对消息的反馈。"""
    try:
        msg_uuid = uuid.UUID(body.messageId)
    except (TypeError, ValueError):
        raise BizException(ErrorCode.PARAM_ERROR, "messageId 格式错误")
    async with async_session() as s:
        fb = Feedback(message_id=msg_uuid, user_id=me.id, type=body.type)
        s.add(fb)
        await s.commit()
    return ok(None)
