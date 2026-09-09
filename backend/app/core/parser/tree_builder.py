"""结构树构建（栈式层级）。"""
from sqlalchemy import select

from app.core.parser.models import ParsedElement
from app.db.session import async_session
from app.models.tree_node import TreeNode


async def build_tree(doc_id: str, elements: list[ParsedElement]) -> list[TreeNode]:
    """从 heading 元素构建层级树并入库，返回除根外的所有节点。

    简化：每个 heading 节点 page_start=page_end=该 heading 页码；summary 暂为 title。
    """
    headings = [e for e in elements if e.element_type == "heading" and e.level > 0]
    async with async_session() as s:
        root = TreeNode(document_id=doc_id, level=0, sort_order=0, title="文档",
                        page_start=headings[0].page_number if headings else 1, page_end=1)
        s.add(root)
        await s.flush()

        stack: list[tuple[int, TreeNode]] = [(0, root)]
        order = 1
        for h in headings:
            while stack and stack[-1][0] >= h.level:
                stack.pop()
            parent = stack[-1][1] if stack else root
            node = TreeNode(document_id=doc_id, parent_id=parent.id, level=h.level,
                            sort_order=order, title=h.content, summary=h.content,
                            page_start=h.page_number, page_end=h.page_number)
            s.add(node)
            await s.flush()
            stack.append((h.level, node))
            order += 1

        await s.commit()
        rows = (await s.execute(select(TreeNode).where(TreeNode.document_id == doc_id)
                                .order_by(TreeNode.sort_order))).scalars().all()
        return [r for r in rows if r.level > 0]
