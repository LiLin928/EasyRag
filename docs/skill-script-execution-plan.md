# 技能脚本执行功能实施计划

## 目标

实现技能脚本的安全执行，让技能中的 `scripts` 字段定义的代码能够被调用和执行。

## 背景

### 当前状态

**技能模型：**
```python
# backend/app/models/skill.py
scripts: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
# 存储：[{"name": "脚本名.py", "content": "代码内容"}]
```

**当前实现：**
```python
# backend/app/core/agent/tool_registry.py:133-141
def _skill_tool(sk: Skill):
    @tool(sk.name, description=f"激活技能：{sk.description or ''}")
    def _activate() -> str:
        return f"[SKILL {sk.name}]\n{sk.prompt or ''}"
    return _activate
```

**问题：**
- ✅ 脚本内容已存储
- ❌ 没有执行逻辑
- ❌ 脚本内容未被使用

---

## 设计方案

### 方案概述

将技能脚本转换为可调用的工具，类似于 Python 工具的执行方式。

### 执行流程

```
1. 用户调用技能
   └─> Agent 使用技能工具

2. 技能工具执行
   ├─> 注入技能 prompt
   ├─> 注册脚本函数到上下文
   └─> Agent 可调用脚本函数

3. 脚本执行
   ├─> 在 OpenSandbox 中运行
   ├─> 接收输入参数
   └─> 返回执行结果
```

---

## 实施步骤

### Task 1: 创建技能脚本执行器

**文件：** `backend/app/core/skills/script_executor.py`

**功能：**
```python
async def execute_skill_script(
    script_name: str,
    script_content: str,
    inputs: dict,
    timeout: int = 30
) -> dict:
    """
    在沙箱中执行技能脚本
    
    Args:
        script_name: 脚本名称
        script_content: 脚本代码
        inputs: 输入参数
        timeout: 超时时间
    
    Returns:
        执行结果
    """
    # 复用 run_in_sandbox
    from app.providers.sandbox import run_in_sandbox
    
    # 将脚本包装为可执行代码
    wrapped_code = f"""
# 脚本: {script_name}
{script_content}

# 执行入口
if 'main' in dir():
    result = main(inputs)
else:
    result = None
"""
    
    result = await run_in_sandbox(
        code=wrapped_code,
        inputs=inputs,
        timeout=timeout
    )
    
    return {
        "success": result.ok,
        "output": result.output,
        "error": result.error
    }
```

---

### Task 2: 更新技能工具构建逻辑

**文件：** `backend/app/core/agent/tool_registry.py`

**修改：**
```python
def _skill_tool(sk: Skill):
    """构建技能激活工具，注入 prompt 和脚本函数。"""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    # 如果有脚本，为每个脚本创建工具
    if sk.scripts:
        tools = []
        
        # 1. 主技能工具（注入 prompt）
        @tool(sk.name, description=f"激活技能：{sk.description or ''}")
        def _activate() -> str:
            return f"[SKILL {sk.name}]\n{sk.prompt or ''}"
        
        tools.append(_activate)
        
        # 2. 为每个脚本创建工具
        for script in sk.scripts:
            script_name = script.get("name", "unnamed")
            script_content = script.get("content", "")
            
            # 创建脚本工具
            async def _run_script(**kwargs):
                from app.core.skills.script_executor import execute_skill_script
                return await execute_skill_script(
                    script_name=script_name,
                    script_content=script_content,
                    inputs=kwargs
                )
            
            script_tool = StructuredTool.from_function(
                coroutine=_run_script,
                name=f"{sk.name}_{script_name}",
                description=f"执行技能脚本：{script_name}"
            )
            
            tools.append(script_tool)
        
        return tools
    
    # 无脚本的情况，保持原逻辑
    @tool(sk.name, description=f"激活技能：{sk.description or ''}")
    def _activate() -> str:
        return f"[SKILL {sk.name}]\n{sk.prompt or ''}"
    
    return _activate
```

---

### Task 3: 更新 build_tools 函数

**文件：** `backend/app/core/agent/tool_registry.py`

**修改：**
```python
async def build_tools(agent: Agent) -> list:
    """聚合 agent 挂载的五类资源为 BaseTool 列表。"""
    tools: list = []
    async with async_session() as s:
        # ... 其他资源聚合 ...
        
        # 5. skills → 技能激活工具
        for sid in (agent.skills or []):
            sk = (await s.execute(select(Skill).where(Skill.id == sid))).scalar_one_or_none()
            if sk:
                skill_tools = _skill_tool(sk)
                # _skill_tool 可能返回单个工具或工具列表
                if isinstance(skill_tools, list):
                    tools.extend(skill_tools)
                else:
                    tools.append(skill_tools)
    
    return tools
```

---

### Task 4: 添加脚本工具的类型定义

**文件：** `frontend/src/types/skill.ts`

**新增：**
```typescript
// 脚本执行参数
export interface ScriptExecuteArgs {
  [key: string]: any
}

// 脚本执行结果
export interface ScriptExecuteResult {
  success: boolean
  output?: any
  error?: string
}
```

---

### Task 5: 添加测试用例

**文件：** `backend/tests/test_skill_script.py`

**测试内容：**
```python
import pytest
from app.core.skills.script_executor import execute_skill_script

@pytest.mark.asyncio
async def test_simple_script():
    """测试简单脚本执行"""
    code = """
def main(inputs):
    return inputs['a'] + inputs['b']
"""
    
    result = await execute_skill_script(
        script_name="add.py",
        script_content=code,
        inputs={"a": 1, "b": 2}
    )
    
    assert result["success"] is True
    assert result["output"] == 3

@pytest.mark.asyncio
async def test_script_with_error():
    """测试脚本错误处理"""
    code = """
def main(inputs):
    raise ValueError("Test error")
"""
    
    result = await execute_skill_script(
        script_name="error.py",
        script_content=code,
        inputs={}
    )
    
    assert result["success"] is False
    assert "Test error" in result["error"]
```

---

## 使用示例

### 创建带脚本的技能

**SQL：**
```sql
INSERT INTO skills (
    id, name, scope, version, description, trigger, prompt,
    tools, docs, wfs, examples, scripts, budget
) VALUES (
    gen_random_uuid(),
    '数据分析助手',
    'custom',
    '1.0.0',
    '帮助用户进行数据分析',
    '当用户需要数据分析时触发',
    '你是数据分析专家...',
    '[]'::jsonb,
    '[]'::jsonb,
    '[]'::jsonb,
    '[]'::jsonb,
    '[
        {
            "name": "statistical_analysis.py",
            "content": "import statistics\n\ndef main(inputs):\n    data = inputs.get('data', [])\n    return {\n        'mean': statistics.mean(data),\n        'median': statistics.median(data),\n        'std': statistics.stdev(data) if len(data) > 1 else 0\n    }"
        }
    ]'::jsonb,
    5000
);
```

### 在 Agent 中使用

```python
# Agent 配置
agent = Agent(
    name="数据分析Agent",
    skills=[skill_id],
    # ...
)

# 用户输入：分析这组数据 [1, 2, 3, 4, 5]
# Agent 会：
# 1. 调用技能工具，注入 prompt
# 2. 调用 statistical_analysis.py 脚本
# 3. 返回统计结果
```

---

## 安全保障

### 沙箱隔离
- ✅ 在 OpenSandbox 容器中执行
- ✅ 无法访问主机文件系统
- ✅ 无法访问主机网络
- ✅ 资源限制（内存、CPU、超时）

### 权限控制
- ✅ 只有管理员可以创建技能
- ✅ 脚本代码在数据库中存储（可审计）
- ✅ 执行日志可追踪

---

## 预期成果

1. **✅ 技能脚本可执行**
   - 脚本代码在沙箱中安全运行
   - 支持输入参数和返回结果

2. **✅ 增强技能能力**
   - 技能不仅能提供 prompt，还能提供具体功能
   - 类似于 LangChain 的 Tool 概念

3. **✅ 保持安全性**
   - 所有脚本在沙箱中执行
   - 无权限提升风险

---

## 实施优先级

- **优先级**: 中等
- **预估时间**: 2-3 小时
- **依赖**: OpenSandbox 服务运行正常

---

## 验收标准

- [ ] 脚本执行器实现完成
- [ ] 技能工具更新完成
- [ ] 测试用例通过
- [ ] 前端类型定义更新
- [ ] 文档更新

---

## 后续优化

1. **脚本模板库**
   - 提供常用脚本模板
   - 降低用户编写难度

2. **脚本编辑器**
   - 前端添加代码编辑器
   - 语法高亮和验证

3. **脚本市场**
   - 分享和复用脚本
   - 社区贡献