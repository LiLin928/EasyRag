"""工作流状态定义与变量解析。

WorkflowState 是 LangGraph StateGraph 的状态类型，贯穿整个执行生命周期。
VariableResolver 解析 {{node_id.output.field}} / {{workflow.custom.x}} / {{loop.item}} 插值。
"""
import re
from typing import Optional, TypedDict


class WorkflowState(TypedDict, total=False):
    workflow_id: str
    execution_id: str
    thread_id: str
    user_id: str
    variables: dict            # 全局变量池 workflow.custom.*
    node_outputs: dict          # {node_id: {output, error, metadata}}
    current_node: Optional[str]
    status: str                 # pending/running/paused/completed/failed/cancelled
    error: Optional[str]
    started_at: float
    node_timings: dict          # {node_id: ms}
    debug_mode: bool
    loop_stack: list


_PATTERN = re.compile(r"\{\{\s*([\w.]+)(?:\[(\d+)\])?(\.\w+)?\s*\}\}")


def resolve(expr: str, state: dict) -> str:
    """解析 {{node_id.output.field}} / {{workflow.custom.x}} / {{loop.item}}。"""
    if not expr:
        return ""

    def _sub(m):
        path = m.group(1)
        idx = m.group(2)
        field = m.group(3)
        if path.startswith("workflow.custom."):
            key = path.split(".", 2)[-1]
            return str(state.get("variables", {}).get(key, ""))
        if path.startswith("loop."):
            return str(state.get("_loop", {}).get(path.split(".", 1)[-1], ""))
        parts = path.split(".", 1)
        nid = parts[0]
        f = parts[1] if len(parts) > 1 else "output"
        out = state.get("node_outputs", {}).get(nid, {})
        val = out.get(f, "")
        if idx is not None and isinstance(val, list):
            val = val[int(idx)] if int(idx) < len(val) else ""
        if field and isinstance(val, dict):
            val = val.get(field.lstrip("."), "")
        return str(val)

    return _PATTERN.sub(_sub, expr)


def resolve_dict(d: dict, state: dict) -> dict:
    """递归解析字典中所有字符串值。"""
    if not d:
        return {}
    result = {}
    for k, v in d.items():
        if isinstance(v, str):
            result[k] = resolve(v, state)
        elif isinstance(v, dict):
            result[k] = resolve_dict(v, state)
        else:
            result[k] = v
    return result
 
