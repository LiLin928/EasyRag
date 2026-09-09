"""MCP 模块 Pydantic schema（对齐前端 types/mcp.ts）。"""
from pydantic import BaseModel


class McpEnv(BaseModel):
    k: str
    v: str


class McpCreate(BaseModel):
    name: str
    tp: str = "stdio"
    cmd: str = ""
    status: str = "off"
    toolCount: int = 0
    env: list[McpEnv] = []
    timeout: int = 30


class McpUpdate(BaseModel):
    name: str | None = None
    tp: str | None = None
    cmd: str | None = None
    status: str | None = None
    toolCount: int | None = None
    env: list[McpEnv] | None = None
    timeout: int | None = None


class McpOut(BaseModel):
    id: str
    name: str
    tp: str
    cmd: str
    status: str
    toolCount: int
    env: list[McpEnv]
    timeout: int
    createdAt: str | None = None


class McpTestResult(BaseModel):
    success: bool
    toolCount: int
    tools: list[str] | None = None
    error: str | None = None
    duration: float
