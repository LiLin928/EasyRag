"""elements 路由：文档内元素列表（前端知识库详情页用）。

注：完整 DocElement 字段的 GET /elements/:id（引用懒加载）在 Plan 6 实现。
ElementPosition 定义在 app.models.tree_node（与 TreeNode 同文件）。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.document import Document
from app.models.tree_node import ElementPosition, TreeNode

router = APIRouter(tags=["elements"])


@router.get("/documents/{doc_id}/elements")
async def list_elements(doc_id: str, page: int = 1, page_size: int = 50,
                        type: str | None = Query(None), me=Depends(get_current_user)):
    """列出文档元素，支持按 type 过滤与分页；返回 doc_title/node_id/node_title/seq。"""
    async with async_session() as s:
        q = (
            select(ElementPosition, Document.name, TreeNode.id, TreeNode.title)
            .outerjoin(TreeNode, ElementPosition.tree_node_id == TreeNode.id)
            .join(Document, ElementPosition.document_id == Document.id)
            .where(ElementPosition.document_id == doc_id)
        )
        if type:
            q = q.where(ElementPosition.element_type == type)
        total = (await s.execute(select(func.count()).select_from(q.subquery()))).scalar()
        rows = (await s.execute(q.order_by(ElementPosition.element_index)
                                .limit(page_size).offset((page - 1) * page_size))).all()
    return ok({"list": [{"element_id": str(e.id), "type": e.element_type, "content": e.content,
                         "page_number": e.page_number,
                         "section_path": (e.metadata_ or {}).get("section_path", ""),
                         "doc_title": doc_name or "",
                         "node_id": str(node_id) if node_id else "",
                         "node_title": node_title or "",
                         "seq": e.element_index}
                        for e, doc_name, node_id, node_title in rows], "total": total})
