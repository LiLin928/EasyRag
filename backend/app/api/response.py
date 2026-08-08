from typing import Any
from app.exceptions import ErrorCode


def ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def err(code: ErrorCode | int, message: str) -> dict:
    return {"code": int(code), "message": message, "data": None}
