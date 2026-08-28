"""技能模块 Pydantic schema（对齐前端 types/skill.ts）。"""
from pydantic import BaseModel


class SkillExample(BaseModel):
    q: str
    a: str


class SkillScript(BaseModel):
    name: str
    content: str


class SkillCreate(BaseModel):
    ico: str = "🔧"
    name: str
    scope: str = "custom"
    ver: str = "1.0.0"
    desc: str = ""
    trigger: str = ""
    prompt: str = ""
    tools: list[str] = []
    docs: list[str] = []
    wfs: list[str] = []
    examples: list[SkillExample] = []
    scripts: list[SkillScript] = []
    budget: int | None = None


class SkillUpdate(BaseModel):
    ico: str | None = None
    name: str | None = None
    scope: str | None = None
    ver: str | None = None
    desc: str | None = None
    trigger: str | None = None
    prompt: str | None = None
    tools: list[str] | None = None
    docs: list[str] | None = None
    wfs: list[str] | None = None
    examples: list[SkillExample] | None = None
    scripts: list[SkillScript] | None = None
    budget: int | None = None


class SkillOut(BaseModel):
    id: str
    ico: str
    name: str
    scope: str
    ver: str
    desc: str
    trigger: str
    prompt: str
    tools: list[str]
    docs: list[str]
    wfs: list[str]
    examples: list[SkillExample]
    scripts: list[SkillScript]
    budget: int | None = None
    used: int | None = None
