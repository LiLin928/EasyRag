"""tree 路由：文档结构树（嵌套）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.tree_node import TreeNode

router = APIRouter(tags=["tree"])


@router.get("/documents/{doc_id}/tree")
async def get_tree(doc_id: str, me=Depends(get_current_user)):
    """返回文档的嵌套结构树（按 parent_id 组装）。"""
    async with async_session() as s:
        nodes = (await s.execute(select(TreeNode).where(TreeNode.document_id == doc_id)
                                 .order_by(TreeNode.sort_order))).scalars().all()
    if not nodes:
        raise BizException(ErrorCode.NOT_FOUND, "结构树尚未生成或文档不存在")
    by_parent: dict[str, list] = {}
    for n in nodes:
        key = str(n.parent_id) if n.parent_id else "root"
        by_parent.setdefault(key, []).append(n)

    def build(parent_key: str):
        return [{"node_id": str(n.id), "title": n.title, "level": n.level,
                 "summary": n.summary, "element_count": n.element_count,
                 "children": build(str(n.id))} for n in by_parent.get(parent_key, [])]

    root_node = by_parent.get("root", [None])[0] if by_parent.get("root") else None
    root_key = str(root_node.id) if root_node else "root"
    return ok({"document_id": doc_id,
               "title": root_node.title if root_node else "",
               "tree": build(root_key)})
