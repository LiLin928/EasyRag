"""MCP 真客户端（基于 langchain-mcp-adapters）。

两类传输：stdio（拉起子进程）/ SSE（连接远端）。
env 中的敏感值解密后传给子进程环境变量。
load_tools 返回 LangChain BaseTool 列表，供 agent / workflow 复用。
"""
import time

from app.security.crypto import decrypt

_pool: dict = {}


def _server_config(mcp) -> dict:
    """将 ORM Mcp 转为 MultiServerMCPClient 期望的 server config。"""
    if mcp.tp == "stdio":
        parts = (mcp.cmd or "").split()
        env = {}
        for e in (mcp.env or []):
            v = e.get("v", "")
            if e.get("v_enc"):
                v = decrypt(e["v_enc"])
            if e.get("k"):
                env[e["k"]] = v
        return {
            "transport": "stdio",
            "command": parts[0] if parts else "",
            "args": parts[1:],
            "env": env or None,
        }
    return {
        "transport": "sse",
        "url": mcp.cmd or "",
        "timeout": mcp.timeout,
    }


async def get_client(mcp):
    """获取或创建 MCP 客户端（按 mcp.id 缓存）。"""
    key = str(mcp.id)
    if key not in _pool:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        _pool[key] = MultiServerMCPClient({"mcp": _server_config(mcp)})
    return _pool[key]


async def load_tools(mcp) -> list:
    """发现 MCP server 工具，返回 LangChain BaseTool 列表。"""
    client = await get_client(mcp)
    return await client.get_tools()


async def test_connection(mcp) -> dict:
    """测试 MCP 连通性并发现工具数量。"""
    t0 = time.perf_counter()
    try:
        tools = await load_tools(mcp)
        duration = round((time.perf_counter() - t0) * 1000, 1)
        return {
            "success": True,
            "toolCount": len(tools),
            "tools": [t.name for t in tools],
            "duration": duration,
        }
    except Exception as e:
        duration = round((time.perf_counter() - t0) * 1000, 1)
        return {
            "success": False,
            "toolCount": 0,
            "tools": [],
            "error": str(e),
            "duration": duration,
        }
 
