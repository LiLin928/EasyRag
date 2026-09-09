"""智能体模块 Pydantic schema（对齐前端 types/agent.ts）。"""
from pydantic import BaseModel


class AgentCreate(BaseModel):
    name: str
    desc: str = ""
    model: str = "gpt-4o"
    prompt: str = ""
    temp: float = 0.7
    maxtok: str = "2048"
    tools: list[str] = []
    docs: list[str] = []
    wfs: list[str] = []
    mcps: list[str] = []
    skills: list[str] = []
    enabled: bool = True


class AgentUpdate(BaseModel):
    name: str | None = None
    desc: str | None = None
    model: str | None = None
    prompt: str | None = None
    temp: float | None = None
    maxtok: str | None = None
    tools: list[str] | None = None
    docs: list[str] | None = None
    wfs: list[str] | None = None
    mcps: list[str] | None = None
    skills: list[str] | None = None
    enabled: bool | None = None


class AgentOut(BaseModel):
    id: str
    name: str
    desc: str
    model: str
    prompt: str
    temp: float
    maxtok: str
    tools: list[str]
    docs: list[str]
    wfs: list[str]
    mcps: list[str]
    skills: list[str]
    enabled: bool
    lastActive: str
    createdAt: str | None = None
