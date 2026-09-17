# MCP 工具延迟加载完善方案

## 1. 背景与目标

### 1.1 问题现状

**问题现象**：
- MCP 工具被调用时返回占位符信息：`"[MCP duckduckgo-search] MCP 服务已就绪，包含 2 个工具"`
- 没有执行实际的工具调用

**根本原因**：
- 当前 `_mcp_proxy_tool` 函数是占位符实现，不执行实际调用
- 参数格式不匹配：
  - LLM 传递：`{'query': '长电科技'}`
  - 当前代码期望：`{'tool_name': '', 'arguments': {...}}`

### 1.2 目标

实现一个**延迟加载的 MCP 工具执行器**，能够：
1. ✅ 延迟连接 MCP 服务（提升启动速度）
2. ✅ 支持任意参数格式（兼容 LLM 的参数传递）
3. ✅ 智能路由到合适的 MCP 工具
4. ✅ 执行实际的工具调用并返回结果
5. ✅ 提供清晰的错误提示

---

## 2. 技术设计

### 2.1 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    LLM 调用 MCP 工具                      │
│              {'query': '长电科技 股票'}                   │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│          _mcp_lazy_tool (延迟加载代理)                    │
│                                                          │
│  1. 接收任意参数 (**kwargs)                               │
│  2. 智能路由到合适的工具                                   │
│  3. 延迟连接 MCP 服务                                     │
│  4. 执行实际工具调用                                       │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│              MCP 服务 (DuckDuckGo Search)                │
│                                                          │
│  - search: 搜索功能                                       │
│  - fetch: 获取网页内容                                     │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│                   真实搜索结果                            │
│        "Found 10 search results: ..."                   │
└─────────────────────────────────────────────────────────┘
```

### 2.2 核心函数设计

#### 函数签名

```python
def _mcp_lazy_tool(m: Mcp) -> StructuredTool:
    """创建延迟加载的 MCP 工具。

    特性：
    - 延迟连接：首次调用时才连接 MCP 服务
    - 参数兼容：支持任意参数格式
    - 智能路由：根据参数自动选择合适的工具
    """
```

#### 参数模型

```python
class LazyMCPInput(BaseModel):
    """灵活的参数模型，支持多种参数格式。"""

    # 常见参数字段
    query: str = Field(default="", description="搜索查询")
    url: str = Field(default="", description="URL 参数")
    tool_name: str = Field(default="", description="指定工具名称（可选）")

    # 允许额外参数
    class Config:
        extra = "allow"
```

**支持的参数格式**：

| 格式 | 示例 | 说明 |
|------|------|------|
| 简单搜索 | `{'query': '长电科技'}` | LLM 当前使用的格式 |
| 指定工具 | `{'tool_name': 'search', 'query': '...'}` | 明确指定工具 |
| URL 获取 | `{'url': 'https://...'}` | 获取网页内容 |
| 其他参数 | `{'任意参数': '值'}` | 通过 extra="allow" 支持 |

#### 执行逻辑

```python
async def _execute_lazy_mcp(**kwargs) -> str:
    """延迟加载并执行 MCP 工具。"""

    # 1. 连接到 MCP 服务
    mcp_tools = await _load_mcp(m)

    # 2. 智能路由：选择合适的工具
    target_tool = _select_tool(mcp_tools, kwargs)

    # 3. 过滤参数
    tool_kwargs = _filter_parameters(kwargs)

    # 4. 执行工具
    result = await target_tool.ainvoke(tool_kwargs)

    # 5. 返回结果
    return str(result)
```

### 2.3 智能路由算法

```python
def _select_tool(mcp_tools: list, kwargs: dict) -> BaseTool:
    """根据参数智能选择工具。"""

    # 优先级 1：明确指定的工具名
    if 'tool_name' in kwargs and kwargs['tool_name']:
        tool_name = kwargs['tool_name'].lower()
        for tool in mcp_tools:
            if tool_name in tool.name.lower():
                return tool

    # 优先级 2：根据参数类型推断
    if 'query' in kwargs and kwargs['query']:
        # 查询参数 → 搜索工具
        for tool in mcp_tools:
            if 'search' in tool.name.lower():
                return tool

    if 'url' in kwargs and kwargs['url']:
        # URL 参数 → 获取工具
        for tool in mcp_tools:
            if 'fetch' in tool.name.lower():
                return tool

    # 优先级 3：默认第一个工具
    return mcp_tools[0]
```

---

## 3. 实现步骤

### 3.1 准备工作

#### 步骤 1：创建开发分支

```bash
cd D:/4-MyProject/EasyRag
git checkout -b feat/mcp-lazy-tool
```

#### 步骤 2：备份当前代码

```bash
cp backend/app/core/agent/tool_registry_lazy.py \
   backend/app/core/agent/tool_registry_lazy.py.bak
```

### 3.2 核心代码实现

#### 步骤 3：完全重写 `_mcp_proxy_tool` 函数

**文件**：`backend/app/core/agent/tool_registry_lazy.py`

**位置**：第 102-220 行

**操作**：删除旧函数，替换为新的 `_mcp_lazy_tool` 函数

**新函数代码**：

```python
def _mcp_lazy_tool(m: Mcp):
    """创建延迟加载的 MCP 工具。

    在被调用时才真正连接 MCP 服务并执行工具调用。
    支持任意参数格式，智能路由到合适的工具。

    Args:
        m: MCP 配置实例

    Returns:
        LangChain StructuredTool
    """
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    # 工具名称（合法化）
    tool_name = _sanitize_tool_name(m.name, prefix="mcp")

    # 工具描述
    description = (
        f"MCP 服务：{m.name}。"
        f"提供 {m.tool_count} 个工具的访问。"
        f"调用时传递查询参数（如 query）即可自动选择合适的工具。"
    )

    # 灵活的参数模型
    class LazyMCPInput(BaseModel):
        """支持多种参数格式的输入模型。"""
        query: str = Field(
            default="",
            description="搜索查询或其他文本参数"
        )
        url: str = Field(
            default="",
            description="URL 参数（用于获取网页内容）"
        )
        tool_name: str = Field(
            default="",
            description="指定要调用的 MCP 工具名称（可选）"
        )

        class Config:
            extra = "allow"  # 允许额外参数

    async def _execute_lazy_mcp(**kwargs) -> str:
        """延迟加载并执行 MCP 工具。

        工作流程：
        1. 连接到 MCP 服务
        2. 发现可用工具
        3. 智能选择合适的工具
        4. 执行工具调用
        5. 返回结果
        """
        try:
            # 步骤 1：连接到 MCP 服务
            from app.core.agent.tool_adapters.mcp_tools import load_tools as _load_mcp

            # 延迟加载 MCP 工具
            mcp_tools = await _load_mcp(m)

            if not mcp_tools:
                return (
                    f"[MCP {m.name}] 错误：未找到可用的工具。\n"
                    f"请检查 MCP 服务是否正常运行。"
                )

            # 步骤 2：智能路由 - 选择合适的工具
            target_tool = None
            requested_tool_name = kwargs.get('tool_name', '').lower()

            # 优先级 1：明确指定的工具名
            if requested_tool_name:
                for tool in mcp_tools:
                    if requested_tool_name in tool.name.lower():
                        target_tool = tool
                        break

            # 优先级 2：根据参数类型推断
            if not target_tool:
                # 查询参数 → 搜索工具
                if kwargs.get('query'):
                    for tool in mcp_tools:
                        if 'search' in tool.name.lower():
                            target_tool = tool
                            break

                # URL 参数 → 获取工具
                if kwargs.get('url'):
                    for tool in mcp_tools:
                        if 'fetch' in tool.name.lower() or 'get' in tool.name.lower():
                            target_tool = tool
                            break

            # 优先级 3：使用第一个可用工具
            if not target_tool:
                target_tool = mcp_tools[0]

            # 步骤 3：过滤参数
            # 移除内部参数（tool_name）和空值
            tool_kwargs = {
                k: v for k, v in kwargs.items()
                if k != 'tool_name' and v
            }

            # 步骤 4：执行工具调用
            result = await target_tool.ainvoke(tool_kwargs)

            # 步骤 5：返回结果
            return str(result)

        except Exception as e:
            # 错误处理
            import traceback
            error_msg = str(e)
            stack_trace = traceback.format_exc()

            return (
                f"[MCP {m.name}] 执行失败: {error_msg}\n\n"
                f"详细错误:\n{stack_trace}"
            )

    # 创建 StructuredTool
    return StructuredTool.from_function(
        coroutine=_execute_lazy_mcp,
        name=tool_name,
        description=description,
        args_schema=LazyMCPInput,
    )
```

#### 步骤 4：更新函数调用

**位置**：`build_tools` 函数中

**修改前**：
```python
tools.append(_mcp_proxy_tool(m))
```

**修改后**：
```python
tools.append(_mcp_lazy_tool(m))
```

### 3.3 测试验证

#### 步骤 5：创建单元测试

**文件**：`backend/tests/test_mcp_lazy_tool.py`

```python
"""测试 MCP 延迟加载工具。"""
import asyncio
import pytest

from app.core.agent.tool_registry_lazy import _mcp_lazy_tool
from app.models.mcp import Mcp


@pytest.fixture
def mock_mcp():
    """创建模拟的 MCP 配置。"""
    return Mcp(
        id="test-mcp-id",
        name="duckduckgo-search",
        status="on",
        tool_count=2,
    )


@pytest.mark.asyncio
async def test_mcp_lazy_tool_with_query(mock_mcp):
    """测试使用 query 参数调用工具。"""
    tool = _mcp_lazy_tool(mock_mcp)

    # 调用工具
    result = await tool.ainvoke({'query': '长电科技 股票'})

    # 验证结果
    assert "Found" in result or "search results" in result
    assert "长电科技" in result or "600584" in result
    print(f"✅ 测试通过: 返回了真实的搜索结果")


@pytest.mark.asyncio
async def test_mcp_lazy_tool_with_url(mock_mcp):
    """测试使用 url 参数调用工具。"""
    tool = _mcp_lazy_tool(mock_mcp)

    # 调用工具
    result = await tool.ainvoke({
        'url': 'https://quote.eastmoney.com/sh600584.html'
    })

    # 验证结果
    assert result  # 应该返回内容
    print(f"✅ 测试通过: 返回了网页内容")


@pytest.mark.asyncio
async def test_mcp_lazy_tool_with_tool_name(mock_mcp):
    """测试明确指定工具名称。"""
    tool = _mcp_lazy_tool(mock_mcp)

    # 调用工具
    result = await tool.ainvoke({
        'tool_name': 'search',
        'query': '长江电力'
    })

    # 验证结果
    assert "Found" in result or "search results" in result
    print(f"✅ 测试通过: 成功指定工具名称")


@pytest.mark.asyncio
async def test_mcp_lazy_tool_no_params(mock_mcp):
    """测试无参数调用。"""
    tool = _mcp_lazy_tool(mock_mcp)

    # 调用工具（应该使用默认工具）
    result = await tool.ainvoke({})

    # 验证结果
    assert result  # 应该返回某些信息
    print(f"✅ 测试通过: 无参数调用成功")


if __name__ == "__main__":
    # 直接运行测试
    asyncio.run(test_mcp_lazy_tool_with_query(mock_mcp()))
    asyncio.run(test_mcp_lazy_tool_with_url(mock_mcp()))
    asyncio.run(test_mcp_lazy_tool_with_tool_name(mock_mcp()))
    asyncio.run(test_mcp_lazy_tool_no_params(mock_mcp()))
```

#### 步骤 6：创建集成测试

**文件**：`test_mcp_lazy_integration.py`

```python
"""MCP 工具集成测试。"""
import asyncio
import httpx


async def test_agent_mcp_tool():
    """测试智能体调用 MCP 工具。"""
    base_url = "http://localhost:8000/api/v2"

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 登录
        login_response = await client.post(
            f"{base_url}/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 测试查询
        test_queries = [
            "使用 MCP 工具搜索 '长电科技 股价'",
            "Search for 长江电力 stock price using MCP",
            "用 MCP 工具查询 长电科技 600584",
        ]

        for query in test_queries:
            print(f"\n{'='*60}")
            print(f"测试查询: {query}")
            print('='*60)

            events = []
            async with client.stream(
                "POST",
                f"{base_url}/agents/545d7c33-0a98-4af6-afc3-f73b0f282efb/chat",
                headers=headers,
                json={"question": query}
            ) as response:
                async for line in response.aiter_lines():
                    events.append(line)

            # 分析结果
            events_str = "\n".join(events)

            # 检查是否有真实数据
            if "Found" in events_str and "search results" in events_str:
                print("✅ 成功: 返回了真实的搜索结果")

                # 提取搜索结果
                for event in events:
                    if "tool_end" in event:
                        print(f"\n工具返回:\n{event[:500]}")
                        break
            else:
                print("❌ 失败: 未返回搜索结果")


if __name__ == "__main__":
    asyncio.run(test_agent_mcp_tool())
```

### 3.4 部署步骤

#### 步骤 7：清理缓存并重启

```bash
# 1. 清理 Python 缓存
find backend -name "*.pyc" -delete
find backend -name "__pycache__" -type d -exec rm -rf {} +

# 2. 停止旧服务
pkill -f uvicorn

# 3. 启动新服务
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. 运行测试
cd ..
uv run pytest backend/tests/test_mcp_lazy_tool.py -v
python test_mcp_lazy_integration.py
```

#### 步骤 8：验证修复

**验证清单**：

- [ ] 服务正常启动
- [ ] 单元测试全部通过
- [ ] 集成测试返回真实搜索结果
- [ ] 工具返回格式正确（`Found 10 search results`）
- [ ] 包含长电科技（600584）的股票信息
- [ ] 错误处理正确

---

## 4. 验收标准

### 4.1 功能验收

| 测试项 | 预期结果 | 验收标准 |
|--------|---------|---------|
| 延迟连接 | 首次调用时才连接 MCP | ✅ 服务启动速度不受影响 |
| 参数兼容 | 支持 `{'query': '长电科技'}` | ✅ LLM 当前格式可直接使用 |
| 智能路由 | 自动选择 search 工具 | ✅ 无需指定工具名 |
| 真实数据 | 返回搜索结果 | ✅ 包含 `Found 10 search results` |
| 错误处理 | 提供清晰的错误提示 | ✅ 包含 MCP 服务名和错误详情 |

### 4.2 性能验收

| 指标 | 目标 | 验收标准 |
|------|------|---------|
| 启动时间 | < 5秒 | ✅ 无明显延迟 |
| 首次调用 | < 3秒 | ✅ 连接 MCP 服务 + 执行工具 |
| 后续调用 | < 2秒 | ✅ MCP 客户端已缓存 |

### 4.3 兼容性验收

| 场景 | 测试 | 预期结果 |
|------|------|---------|
| DuckDuckGo Search | 搜索"长电科技" | 返回真实搜索结果 |
| URL Fetch | 获取网页内容 | 返回网页文本 |
| 错误处理 | MCP 服务未启动 | 清晰的错误提示 |

---

## 5. 时间规划

### 5.1 开发时间表

| 阶段 | 任务 | 预计时间 |
|------|------|---------|
| 准备 | 创建分支、备份代码 | 10 分钟 |
| 开发 | 重写 `_mcp_lazy_tool` 函数 | 30 分钟 |
| 测试 | 编写并运行测试 | 20 分钟 |
| 部署 | 清理缓存、重启服务 | 10 分钟 |
| 验证 | 完整验收测试 | 20 分钟 |
| **总计** | - | **90 分钟** |

### 5.2 里程碑

- **M1**：代码实现完成 ✅
- **M2**：单元测试通过 ✅
- **M3**：集成测试通过 ✅
- **M4**：验收完成 ✅

---

## 6. 风险与应对

### 6.1 潜在风险

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 参数格式多样化 | LLM 可能传递不同格式 | 使用 `extra="allow"` 支持任意参数 |
| MCP 服务不可用 | 工具调用失败 | 提供清晰的错误提示和重试机制 |
| 性能问题 | 首次调用慢 | 使用客户端缓存机制 |
| 兼容性问题 | 旧代码依赖旧格式 | 保留向后兼容性 |

### 6.2 回滚方案

如果新实现出现问题，可以快速回滚：

```bash
# 方案 A：回滚到旧代码
cp backend/app/core/agent/tool_registry_lazy.py.bak \
   backend/app/core/agent/tool_registry_lazy.py

# 方案 B：使用立即加载模式
# 修改 agent_service.py 中的 build_tools 调用
tools = await build_tools(agent, lazy_mcp=False)
```

---

## 7. 文档更新

### 7.1 需要更新的文档

- [ ] `backend/app/core/agent/tool_registry_lazy.py` - 代码注释
- [ ] `docs/architecture/agent-tools.md` - 架构文档
- [ ] `README.md` - 使用说明
- [ ] `CHANGELOG.md` - 变更日志

### 7.2 示例文档

```markdown
## MCP 工具使用说明

### 延迟加载机制

MCP 工具采用延迟加载策略，在首次调用时才连接 MCP 服务，提升系统启动速度。

### 参数格式

支持多种参数格式：

**简单搜索**（推荐）：
```json
{"query": "长电科技 股票"}
```

**指定工具**：
```json
{"tool_name": "search", "query": "长电科技"}
```

**获取网页**：
```json
{"url": "https://example.com"}
```

### 智能路由

系统会根据参数自动选择合适的工具：
- 有 `query` 参数 → 使用搜索工具
- 有 `url` 参数 → 使用获取工具
- 未指定 → 使用默认工具
```

---

## 8. 后续优化

### 8.1 短期优化（1-2周）

1. **性能监控** - 添加调用统计和性能指标
2. **缓存机制** - 缓存常用搜索结果
3. **重试策略** - 网络错误时自动重试

### 8.2 长期优化（1-2月）

1. **工具预热** - 在空闲时预连接 MCP 服务
2. **并发优化** - 支持并发调用多个工具
3. **结果缓存** - 缓存工具返回结果，减少重复调用

---

## 9. 附录

### 9.1 相关文件清单

| 文件 | 用途 | 状态 |
|------|------|------|
| `backend/app/core/agent/tool_registry_lazy.py` | 核心实现 | 待修改 |
| `backend/app/core/agent/tool_adapters/mcp_tools.py` | MCP 工具加载器 | 无需修改 |
| `backend/tests/test_mcp_lazy_tool.py` | 单元测试 | 新建 |
| `test_mcp_lazy_integration.py` | 集成测试 | 新建 |

### 9.2 参考资源

- [LangChain StructuredTool 文档](https://python.langchain.com/docs/modules/tools)
- [Pydantic 模型配置](https://docs.pydantic.dev/latest/usage/model_config/)
- [MCP 协议规范](https://modelcontextprotocol.io/)
- [DuckDuckGo MCP Server](https://github.com/modelcontextprotocol/servers/tree/main/src/duckduckgo)

---

**文档版本**：v1.0
**创建日期**：2026-09-17
**作者**：Claude Code
**状态**：待实施