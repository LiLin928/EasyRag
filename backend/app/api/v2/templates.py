"""templates 路由：工作流模板列表 + 从模板实例化。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.workflow import Workflow, WorkflowTemplate
from app.schemas.workflow import TemplateInstantiate
from app.api.v2.workflows import _out as _wf_out

router = APIRouter(prefix="/templates", tags=["templates"])


def _out(tpl: WorkflowTemplate) -> dict:
    """构造模板响应字典。"""
    return {
        "id": str(tpl.id),
        "name": tpl.name,
        "description": tpl.description or "",
        "source": tpl.source,
        "tags": tpl.tags or [],
        "nodeCount": tpl.node_count,
        "useCount": tpl.use_count,
        "thumbnail": tpl.thumbnail,
        "definition": tpl.definition or {},
    }


@router.get("")
async def list_(me=Depends(get_current_user)):
    """列出所有工作流模板。"""
    async with async_session() as s:
        rows = (
            await s.execute(
                select(WorkflowTemplate).order_by(WorkflowTemplate.use_count.desc())
            )
        ).scalars().all()
    return ok([_out(r) for r in rows])


@router.post("/{tpl_id}/instantiate")
async def instantiate(tpl_id: str, body: TemplateInstantiate, me=Depends(get_current_user)):
    """从模板创建工作流实例。"""
    async with async_session() as s:
        tpl = (
            await s.execute(
                select(WorkflowTemplate).where(WorkflowTemplate.id == tpl_id)
            )
        ).scalar_one_or_none()
        if not tpl:
            raise BizException(ErrorCode.NOT_FOUND, "模板不存在")
        wf = Workflow(
            user_id=me.id,
            name=body.name or tpl.name,
            description=tpl.description,
            status="draft",
            icon=tpl.icon,
            definition=tpl.definition,
        )
        tpl.use_count += 1
        s.add(wf)
        await s.commit()
        await s.refresh(wf)
    return ok(_wf_out(wf))
