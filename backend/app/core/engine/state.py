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
    inputs: dict              # 用户输入参数（从 start 节点传入）
    variables: dict            # 全局变量池 workflow.custom.*
    node_outputs: dict          # {node_id: {output, error, metadata}}
    current_node: Optional[str]
    status: str                 # pending/running/paused/completed/failed/cancelled
    error: Optional[str]
    started_at: float
    node_timings: dict          # {node_id: ms}
    debug_mode: bool
    loop_stack: list


_PATTERN = re.compile(r"\{\{\s*([\w-]+(?:\.[\w-]+)*)\s*\}\}")


def resolve(expr: str, state: dict) -> str:
    """解析 {{node_id.field}} / {{workflow.custom.x}} / {{loop.item}}。

    支持的格式：
    - {{node_id.field}} → state["node_outputs"]["node_id"]["field"]
    - {{node_id}} → state["node_outputs"]["node_id"]["output"] (默认字段)
    - {{workflow.custom.x}} → state["variables"]["x"]
    - {{loop.item}} → state["_loop"]["item"]
    """
    if not expr:
        return ""

    def _sub(m):
        # 正则分组：{{node_id.field}} 或 {{node_id}}
        path = m.group(1)  # node_id 或 node_id.field

        # 1. 处理 workflow.custom.*
        if path.startswith("workflow.custom."):
            key = path.split(".", 2)[-1]
            return str(state.get("variables", {}).get(key, ""))

        # 2. 处理 loop.*
        if path.startswith("loop."):
            return str(state.get("_loop", {}).get(path.split(".", 1)[-1], ""))

        # 3. 处理 {{node_id.field}} 或 {{node_id}}
        parts = path.split(".", 1)
        node_id = parts[0]

        # 确定字段名：
        # - 如果格式是 {{node_id.field}}，使用 field
        # - 如果格式是 {{node_id}}，默认使用 "output"
        field_name = parts[1] if len(parts) > 1 else "output"

        # 从 node_outputs 中获取值
        node_output = state.get("node_outputs", {}).get(node_id, {})
        value = node_output.get(field_name, "")

        return str(value)

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
 
