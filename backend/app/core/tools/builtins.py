"""内置工具注册表。

内置工具通过名称查找，直接在进程内执行，无需外部调用。
新增内置工具只需在 BUILTIN 字典中注册。
"""
from datetime import datetime, timezone


def _current_time(args: dict) -> dict:
    return {"now": datetime.now(timezone.utc).isoformat()}


def _string_length(args: dict) -> dict:
    return {"length": len(str(args.get("s", "")))}


def _uuid_gen(args: dict) -> dict:
    import uuid
    return {"uuid": str(uuid.uuid4())}


BUILTIN: dict[str, callable] = {
    "current_time": _current_time,
    "string_length": _string_length,
    "uuid": _uuid_gen,
}
 
