"""elements 路由：单个元素详情 + 上下文窗口（Plan 6）。

前端在聊天引用懒加载时调用：
  GET /elements/:id          → 单个元素完整信息
  GET /elements/:id/context  → 同文档前后 N 个元素
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.document import Document
from app.models.tree_node import ElementPosition, TreeNode

router = APIRouter(tags=["elements"])


def _element_out(e: ElementPosition, doc_name: str | None, node_id, node_title: str | None) -> dict:
    """构造元素详情字典。"""
    return {
        "element_id": str(e.id),
        "type": e.element_type,
        "content": e.content,
        "page_number": e.page_number,
        "section_path": (e.metadata_ or {}).get("section_path", ""),
        "doc_title": doc_name or "",
        "node_id": str(node_id) if node_id else "",
        "node_title": node_title or "",
        "seq": e.element_index,
        "image_key": e.image_key,
        "ocr_text": e.ocr_text,
    }


@router.get("/elements/{element_id}")
async def get_element(element_id: str, me=Depends(get_current_user)):
    """获取单个元素详情。"""
    async with async_session() as s:
        row = (await s.execute(
            select(ElementPosition, Document.name, TreeNode.id, TreeNode.title)
            .outerjoin(TreeNode, ElementPosition.tree_node_id == TreeNode.id)
            .join(Document, ElementPosition.document_id == Document.id)
            .where(ElementPosition.id == element_id)
        )).first()
    if not row:
        raise BizException(ErrorCode.NOT_FOUND, "元素不存在")
    e, doc_name, node_id, node_title = row
    return ok(_element_out(e, doc_name, node_id, node_title))


@router.get("/elements/{element_id}/context")
async def get_element_context(element_id: str, window: int = Query(3, ge=1, le=20),
                             me=Depends(get_current_user)):
    """获取同文档前后 window 个元素。"""
    async with async_session() as s:
        target = await s.get(ElementPosition, element_id)
        if not target:
            raise BizException(ErrorCode.NOT_FOUND, "元素不存在")
        rows = (await s.execute(
            select(ElementPosition, Document.name, TreeNode.id, TreeNode.title)
            .outerjoin(TreeNode, ElementPosition.tree_node_id == TreeNode.id)
            .join(Document, ElementPosition.document_id == Document.id)
            .where(
                ElementPosition.document_id == target.document_id,
                ElementPosition.element_index >= target.element_index - window,
                ElementPosition.element_index <= target.element_index + window,
            )
            .order_by(ElementPosition.element_index)
        )).all()
    return ok([_element_out(e, doc_name, node_id, node_title)
               for e, doc_name, node_id, node_title in rows])
