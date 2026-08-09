"""引用构建（最小版，Plan 5 扩展为完整 DocElement 字段）。"""


def build_references(chunks: list[dict]) -> list[dict]:
    """从检索 chunks 构建轻量引用列表。

    Plan 5 将扩展为含完整 DocElement 字段（element_id/page/section_path 等）。
    """
    return [{"ref_id": f"r{i}", "element_id": str(c.get("id")),
             "content_preview": (c.get("content") or "")[:80],
             "score": c.get("rerank_score", c.get("rrf", c.get("score", 0))), "type": "text"}
            for i, c in enumerate(chunks)]
