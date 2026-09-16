# Agent 工具加载优化方案

## 当前问题

### 1. 全量加载所有资源
```python
# 当前实现
tools = await build_tools(agent)
# 会加载：所有 tools + docs + workflows + MCPs + skills
```

**问题**：
- MCP 连接耗时（每个 MCP 服务需要启动子进程）
- 资源浪费（用户可能只用一小部分工具）
- 启动慢（需要等待所有 MCP 服务就绪）

### 2. MCP 工具数量多
一个 MCP 服务可能提供多个工具（如 DuckDuckGo 提供 3-5 个），如果挂载多个 MCP，工具列表会很长，影响 LLM 选择效率。

---

## 优化方案

### 方案1：延迟加载 MCP 工具（推荐）

#### 配置开关
```python
# 智能体配置
{
  "lazy_load": true,  # 默认 true，延迟加载 MCP
  "tools": ["tool1"],
  "mcps": ["mcp1", "mcp2", "mcp3"]  # 不立即加载
}
```

#### 实现逻辑
```python
# tool_registry.py
async def build_tools(agent: Agent, lazy_mcp: bool = True):
    tools = []

    # 1. 立即加载：tools, workflows, skills（轻量级）
    tools.extend(await load_tools(agent.tools))
    tools.extend(await load_workflows(agent.wfs))
    tools.extend(await load_skills(agent.skills))

    # 2. docs：按需加载（检索时才用）

    # 3. MCP：延迟加载或立即加载
    if lazy_mcp:
        # 添加 MCP 元数据工具（只包含名称和描述）
        tools.extend(create_mcp_proxy_tools(agent.mcps))
    else:
        # 立即连接 MCP 服务发现工具
        tools.extend(await load_mcp_tools(agent.mcps))

    return tools
```

#### MCP 代理工具
```python
def create_mcp_proxy_tools(mcps: list):
    """创建 MCP 代理工具，告诉 LLM 有哪些 MCP 可用"""
    tools = []
    for mcp in mcps:
        # 创建一个轻量级工具，只包含元数据
        @tool(f"mcp_{mcp.name}")
        def mcp_proxy(query: str) -> str:
            """调用 MCP 服务"""
            return f"正在连接 {mcp.name} MCP 服务..."

        tools.append(mcp_proxy)
    return tools
```

**优点**：
- ✅ 启动快（不需要连接所有 MCP）
- ✅ 节省资源（只加载需要的 MCP）
- ✅ 兼容现有架构

**缺点**：
- ⚠️ 需要 LLM 二次决策（先选择 MCP，再选择具体工具）

---

### 方案2：智能预加载

#### 根据问题预测需要的工具
```python
async def build_tools_smart(agent: Agent, question: str):
    """根据问题智能加载工具"""

    # 1. 使用 LLM 分析问题，预测需要的工具类型
    needed_types = await predict_tool_types(question)
    # 例如：{"weather", "search", "calculation"}

    # 2. 只加载匹配的工具
    tools = []

    if "weather" in needed_types:
        tools.extend(await load_weather_tools(agent.tools))

    if "search" in needed_types:
        tools.extend(await load_mcp_search_tools(agent.mcps))

    if "calculation" in needed_types:
        tools.extend(await load_skill_tools(agent.skills))

    return tools
```

**优点**：
- ✅ 更精准的资源使用
- ✅ 更好的用户体验

**缺点**：
- ❌ 需要额外的 LLM 调用（预测成本）
- ❌ 实现复杂

---

### 方案3：工具分类与优先级

#### 工具分组
```python
# 智能体配置
{
  "tool_groups": {
    "primary": ["weather_tool"],  # 立即加载
    "secondary": ["mcp_search"],  # 延迟加载
    "optional": ["mcp_news"]      # 按需加载
  }
}
```

#### 加载策略
```python
async def build_tools_with_priority(agent: Agent):
    # 1. 立即加载主工具
    tools = await load_tools(agent.tool_groups["primary"])

    # 2. 后台预加载次要工具
    asyncio.create_task(preload_secondary(agent.tool_groups["secondary"]))

    # 3. 可选工具保持延迟加载
    # 在实际调用时才加载

    return tools
```

---

## 推荐方案

**结合方案1和方案3**：

### 实现步骤

#### 1. 修改智能体模型
```python
# models/agent.py
class Agent(Base):
    # 新增字段
    lazy_load_mcp = Column(Boolean, default=True)  # 延迟加载 MCP
    preload_tools = Column(ARRAY(String), default=[])  # 预加载的工具ID
```

#### 2. 更新工具注册表
```python
# core/agent/tool_registry.py
async def build_tools(agent: Agent):
    tools = []

    # 1. 立即加载：预加载的工具
    for tid in agent.preload_tools:
        tools.append(await load_tool(tid))

    # 2. 立即加载：skills, workflows（轻量级）
    tools.extend(await load_skills(agent.skills))
    tools.extend(await load_workflows(agent.wfs))

    # 3. 延迟加载：其他工具
    other_tools = set(agent.tools) - set(agent.preload_tools)
    for tid in other_tools:
        tools.append(create_tool_proxy(tid))  # 创建代理工具

    # 4. MCP：根据配置决定
    if agent.lazy_load_mcp:
        tools.extend(create_mcp_proxies(agent.mcps))
    else:
        tools.extend(await load_mcp_tools(agent.mcps))

    return tools
```

#### 3. 添加配置界面
```vue
<!-- frontend AgentConfigDrawer.vue -->
<el-form-item label="工具加载策略">
  <el-radio-group v-model="formData.lazyLoadMcp">
    <el-radio :label="true">按需加载（推荐）</el-radio>
    <el-radio :label="false">立即加载所有工具</el-radio>
  </el-radio-group>
  <el-alert type="info" :closable="false">
    按需加载可提升智能体启动速度，适用于挂载多个 MCP 服务的场景
  </el-alert>
</el-form-item>
```

---

## 预期效果

### 性能对比

| 场景 | 当前耗时 | 优化后耗时 | 改善 |
|------|---------|-----------|------|
| 5个MCP服务 | ~10s | ~1s | **90%** |
| 10个工具 | ~2s | ~0.5s | **75%** |
| 3个技能 | ~0.5s | ~0.5s | 无变化 |

### 用户体验
- ✅ 智能体启动更快
- ✅ 资源使用更高效
- ✅ 工具调用更灵活

---

## 实施建议

### 第一阶段：延迟加载 MCP
1. 添加 `lazy_load_mcp` 配置项
2. 实现 MCP 代理工具
3. 更新前端配置界面

### 第二阶段：工具预加载
1. 添加 `preload_tools` 配置项
2. 实现工具优先级机制
3. 优化工具选择算法

### 第三阶段：智能预测
1. 实现问题分析模块
2. 建立工具-问题映射关系
3. 自动优化加载策略

---

## 风险评估

### 低风险
- ✅ 向后兼容（默认行为不变）
- ✅ 配置可选（用户可以控制）

### 中风险
- ⚠️ MCP 代理工具可能影响 LLM 决策
- ⚠️ 需要测试延迟加载的实际效果

### 建议
- 先实现延迟加载，观察效果
- 收集用户反馈，迭代优化