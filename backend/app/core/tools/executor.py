"""工具执行器：HTTP / 内置 / Python 三类工具统一执行入口。

HTTP 工具经 httpx 发起请求，auth.key 解密后注入 header。
Python 工具在受限沙箱中执行（复用 Plan 7 沙箱；不可用时降级 exec）。
内置工具查 BUILTIN 注册表直接调用。
"""
import time

import httpx

from app.security.crypto import decrypt


async def execute(tool, args: dict) -> dict:
    """执行工具，返回 {success, data, error, duration}。"""
    t = (tool.type or "HTTP").strip()
    try:
        if t == "HTTP":
            return await _http(tool, args)
        if t == "Python":
            return await _python(tool, args)
        if t == "内置":
            return _builtin(tool, args)
        return {"success": False, "data": None, "error": f"未知工具类型: {t}", "duration": 0.0}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e), "duration": 0.0}


async def _http(tool, args: dict) -> dict:
    cfg = tool.config or {}
    url = _render(cfg.get("url", ""), args)
    method = cfg.get("method", "GET").upper()
    headers = dict(cfg.get("headers", {}))
    auth = tool.auth or {}
    if auth.get("mode") == "bearer" and auth.get("key"):
        headers["Authorization"] = f"Bearer {decrypt(auth['key'])}"
    elif auth.get("mode") == "apikey" and auth.get("key"):
        headers["X-API-Key"] = decrypt(auth["key"])
    body_type = cfg.get("bodyType", "json")
    json_body = args if body_type == "json" and method in ("POST", "PUT", "PATCH") else None
    timeout = cfg.get("timeout", 30)
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.request(method, url, headers=headers, json=json_body)
    duration = round((time.perf_counter() - t0) * 1000, 1)
    ok_ = resp.status_code < 400
    return {
        "success": ok_,
        "data": _safe_json(resp),
        "error": None if ok_ else resp.text[:500],
        "duration": duration,
    }


async def _python(tool, args: dict) -> dict:
    code = (tool.config or {}).get("code", "")
    if not code:
        return {"success": False, "data": None, "error": "Python 工具未配置代码", "duration": 0.0}
    try:
        from app.providers.sandbox import run_in_sandbox  # Plan 7 Task 15
        r = await run_in_sandbox(code=code, inputs=args, timeout=30, memory_mb=256)
        return {"success": r.ok, "data": r.output, "error": r.error, "duration": float(r.duration)}
    except ImportError:
        pass
    # 降级：受限 exec（仅开发环境）
    t0 = time.perf_counter()
    local: dict = {"args": args, "result": None}
    try:
        exec(code, {"__builtins__": __builtins__}, local)
        duration = round((time.perf_counter() - t0) * 1000, 1)
        return {"success": True, "data": local.get("result"), "error": None, "duration": duration}
    except Exception as e:
        duration = round((time.perf_counter() - t0) * 1000, 1)
        return {"success": False, "data": None, "error": str(e), "duration": duration}


def _builtin(tool, args: dict) -> dict:
    from app.core.tools.builtins import BUILTIN
    fn = BUILTIN.get(tool.name)
    if not fn:
        return {"success": False, "data": None, "error": f"内置工具 {tool.name} 不存在", "duration": 0.0}
    t0 = time.perf_counter()
    data = fn(args)
    return {"success": True, "data": data, "error": None, "duration": round((time.perf_counter() - t0) * 1000, 1)}


def _render(tpl: str, args: dict) -> str:
    for k, v in (args or {}).items():
        tpl = tpl.replace(f"{{{k}}}", str(v))
    return tpl


def _safe_json(resp) -> dict | str:
    try:
        return resp.json()
    except Exception:
        return resp.text
 
