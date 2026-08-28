"""引用构建（最小版，Plan 5 扩展为完整 DocElement 字段）。"""


def build_references(chunks: list[dict]) -> list[dict]:
    """从检索 chunks 构建轻量引用列表。

    包含前端 Reference 类型所需的全部字段（doc_title/node_title）。
    """
    return [{"ref_id": f"r{i}",
             "element_id": str(c.get("id")),
             "doc_title": c.get("document_name", ""),
             "node_title": c.get("clause_title") or c.get("section_path") or "",
             "content_preview": (c.get("content") or "")[:80],
             "score": c.get("rerank_score", c.get("rrf", c.get("score", 0))),
             "type": "text"}
            for i, c in enumerate(chunks)]
