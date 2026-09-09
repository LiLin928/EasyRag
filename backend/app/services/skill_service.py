"""技能服务：触发词匹配 + 资源聚合。

match_skills 按逗号分隔的 trigger 关键词命中用户输入。
apply_skills 返回追加 system_prompt、关联 doc_ids、tool_ids 供对话/Agent 使用。
"""


def match_skills(text: str, candidates) -> list:
    """按 trigger 关键词（逗号分隔）命中，返回匹配的技能列表。"""
    hit = []
    for sk in candidates:
        triggers = [t.strip() for t in (sk.trigger or "").split(",") if t.strip()]
        if any(t in text for t in triggers):
            hit.append(sk)
    return hit


def apply_skills(skills: list) -> tuple[str, list, list]:
    """返回 (追加 system_prompt, doc_ids, tool_ids)。"""
    extra = "\n\n".join(f"[技能 {s.name}]\n{s.prompt}" for s in skills if s.prompt)
    doc_ids = [d for s in skills for d in (s.docs or [])]
    tool_ids = [t for s in skills for t in (s.tools or [])]
    return extra, doc_ids, tool_ids
 
