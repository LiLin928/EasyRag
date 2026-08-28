"""工具模块 Pydantic schema（对齐前端 types/tool.ts）。"""
from typing import Any

from pydantic import BaseModel


class ToolParam(BaseModel):
    n: str
    t: str = "string"
    d: str = ""


class ToolAuth(BaseModel):
    mode: str = "none"  # none / apikey / bearer
    key: str = ""


class ToolCreate(BaseModel):
    name: str
    type: str = "HTTP"
    desc: str = ""
    sig: str = ""
    enabled: bool = True
    params: list[ToolParam] = []
    auth: ToolAuth = ToolAuth()
    config: dict[str, Any] = {}


class ToolUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    desc: str | None = None
    sig: str | None = None
    enabled: bool | None = None
    params: list[ToolParam] | None = None
    auth: ToolAuth | None = None
    config: dict[str, Any] | None = None


class ToolOut(BaseModel):
    id: str
    name: str
    type: str
    desc: str
    sig: str
    enabled: bool
    params: list[ToolParam]
    auth: ToolAuth
    createdAt: str | None = None
    config: dict[str, Any] = {}


class ToolTestResult(BaseModel):
    success: bool
    data: Any | None = None
    error: str | None = None
    duration: float
