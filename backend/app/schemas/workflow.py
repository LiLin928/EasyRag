"""工作流模块 Pydantic schema（对齐前端 types/workflow.ts + types/todo.ts）。

nodes / edges 在请求中以独立字段传入，落库时打包进 definition JSONB。
"""
from typing import Any

from pydantic import BaseModel


# ---------- 工作流定义 ----------

class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    version: int | None = None
    icon: str | None = None
    nodes: list[dict] | None = None
    edges: list[dict] | None = None


class WorkflowOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    status: str
    version: int
    icon: str | None = None
    nodes: list[dict]
    edges: list[dict]
    successRate: float | None = None
    lastRun: str | None = None
    createdAt: str
    updatedAt: str


# ---------- 模板 ----------

class TemplateOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    source: str
    tags: list[str]
    nodeCount: int
    useCount: int
    thumbnail: str | None = None
    definition: dict


class TemplateInstantiate(BaseModel):
    name: str | None = None


# ---------- 执行 ----------

_EXEC_STATUS_MAP = {
    "pending": "wait",
    "running": "running",
    "paused": "wait",
    "completed": "success",
    "failed": "error",
    "cancelled": "cancelled",
}

_EXEC_TRIGGER_MAP = {
    "manual": "manual",
    "api": "api",
    "webhook": "api",
    "chat": "agent",
    "agent": "agent",
    "schedule": "schedule",
}


def map_exec_status(db_status: str) -> str:
    return _EXEC_STATUS_MAP.get(db_status, db_status)


def map_exec_trigger(db_trigger: str) -> str:
    return _EXEC_TRIGGER_MAP.get(db_trigger, db_trigger)


class ExecutionOut(BaseModel):
    id: str
    workflowId: str
    workflowName: str
    status: str
    trigger: str
    startTime: str
    duration: float | None = None
    nodeProgress: str


class ExecuteRequest(BaseModel):
    debug: bool = False

    inputs: dict | None = None


# ---------- 待办 ----------

class FormField(BaseModel):
    key: str
    label: str
    type: str  # text / textarea / select / radio / number / upload
    required: bool | None = None
    options: list[dict] | None = None


class TodoOut(BaseModel):
    id: str
    title: str
    source: str
    status: str  # pending / done / rejected
    submittedAt: str | None = None
    cd: bool | None = None
    deadline: int | None = None  # 剩余秒数
    formSchema: list[dict]
    formData: dict | None = None
