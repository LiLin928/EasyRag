# 智能体问题分析与解决方案

## 问题1：技能脚本未执行

### 当前实现
```python
def _skill_tool(sk: Skill):
    """构建技能激活工具。"""
    @tool(skill_name, description=f"激活技能：{sk.description or ''}")
    def _activate() -> str:
        return f"[SKILL {sk.name}]\n{sk.prompt or ''}"  # ❌ 只返回文本
    return _activate
```

**问题**：
- 技能只返回 prompt 文本
- 脚本文件（如 `数字提取器.py`、`求和计算.py`）没有被执行
- OpenSandbox 脚本执行器存在但未使用

### 解决方案：集成脚本执行器

#### 方案A：技能脚本作为工具链执行

```python
def _skill_tool(sk: Skill):
    """构建技能工具，执行脚本链。"""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    # 定义输入参数
    class SkillInput(BaseModel):
        input_text: str = Field(description="用户输入的文本")

    async def _run(input_text: str) -> str:
        """执行技能的脚本链。"""
        results = []
        inputs = {"text": input_text}

        # 按顺序执行所有脚本
        for script in (sk.scripts or []):
            script_name = script.get("name", "unknown")
            script_content = script.get("content", "")

            if not script_content:
                continue

            # 调用脚本执行器
            from app.core.skills.script_executor import execute_skill_script
            result = await execute_skill_script(
                script_name=script_name,
                script_content=script_content,
                inputs=inputs,
            )

            if result["success"]:
                # 将输出作为下一个脚本的输入
                inputs["text"] = str(result["output"])
                results.append({
                    "script": script_name,
                    "output": result["output"]
                })
            else:
                # 脚本执行失败，记录错误
                results.append({
                    "script": script_name,
                    "error": result["error"]
                })

        # 返回最终结果
        if results:
            # 返回技能 prompt + 脚本执行结果
            return f"[SKILL {sk.name}]\n{sk.prompt or ''}\n\n脚本执行结果:\n{json.dumps(results, ensure_ascii=False, indent=2)}"
        else:
            # 没有脚本，只返回 prompt
            return f"[SKILL {sk.name}]\n{sk.prompt or ''}"

    skill_name = _sanitize_tool_name(sk.name, prefix="skill")
    return StructuredTool.from_function(
        coroutine=_run,
        name=skill_name,
        description=f"激活技能：{sk.description or ''}",
        args_schema=SkillInput,
    )
```

#### 方案B：技能脚本作为预处理工具

```python
def _skill_tool(sk: Skill):
    """技能工具：预处理输入，增强 LLM 能力。"""

    async def _process_input(query: str) -> str:
        """执行脚本预处理用户输入。"""
        # 1. 执行脚本提取信息
        extracted = {}
        for script in (sk.scripts or []):
            result = await execute_skill_script(
                script.get("name"),
                script.get("content"),
                {"text": query}
            )
            if result["success"]:
                extracted[script["name"]] = result["output"]

        # 2. 返回增强后的上下文
        context = f"[SKILL {sk.name}]\n{sk.prompt}\n\n"
        if extracted:
            context += f"预处理结果:\n{json.dumps(extracted, ensure_ascii=False, indent=2)}\n\n"
        context += f"用户输入: {query}"

        return context

    return StructuredTool.from_function(
        coroutine=_process_input,
        name=_sanitize_tool_name(sk.name, prefix="skill"),
        description=sk.description,
    )
```

---

## 问题2：编辑配置时数据丢失

### 问题分析

#### 当前流程
```
1. 用户打开编辑对话框
2. watch(() => props.visible) 触发
3. loadCandidateData() 加载候选数据
4. formData.value = {...props.data} 初始化表单
5. AgentCapabilityPicker 监听 props 变化
6. 用户选择工具/MCP/技能
7. AgentCapabilityPicker emit('update', {...})
8. handleCapabilityUpdate 更新 formData
9. 用户点击"保存"
10. emit('submit', formData.value)
```

#### 可能的问题点

**1. 初始化时机问题**
```javascript
// AgentConfigDrawer.vue
watch(() => props.visible, async (visible) => {
  if (visible) {
    await loadCandidateData()  // ⚠️ 异步加载
    if (props.data) {
      formData.value = {...props.data}  // ⚠️ 同步赋值
    }
  }
})
```

问题：`loadCandidateData()` 是异步的，但 `formData.value` 的赋值是同步的。如果 `loadCandidateData()` 还没完成，`AgentCapabilityPicker` 可能接收到空数据。

**2. AgentCapabilityPicker 初始化问题**
```javascript
// AgentCapabilityPicker.vue
const isInitialized = ref(false)

watch(() => [props.tools, ...], ([tools, ...]) => {
  // ⚠️ 每次 props 变化都更新，但可能导致死循环
  selectedTools.value = [...(tools || [])]
  if (!isInitialized.value) {
    isInitialized.value = true
  }
}, { immediate: true })
```

问题：`isInitialized` 标记在组件生命周期内只设置一次，但如果用户切换编辑不同的智能体，可能不会重新初始化。

**3. 提交数据完整性**
```javascript
function handleSubmit() {
  emit('submit', formData.value)  // ⚠️ formData 是否包含最新的工具/MCP/技能？
}
```

### 解决方案

#### 方案A：确保初始化顺序（推荐）

```javascript
// AgentConfigDrawer.vue
watch(() => props.visible, async (visible) => {
  if (visible) {
    // 1. 先加载候选数据
    await loadCandidateData()

    // 2. 再初始化表单数据
    if (props.data) {
      formData.value = {
        name: props.data.name,
        desc: props.data.desc,
        model: props.data.model,
        prompt: props.data.prompt,
        temp: props.data.temp,
        maxtok: props.data.maxtok,
        // ⚠️ 确保数组字段正确初始化
        tools: Array.isArray(props.data.tools) ? [...props.data.tools] : [],
        docs: Array.isArray(props.data.docs) ? [...props.data.docs] : [],
        wfs: Array.isArray(props.data.wfs) ? [...props.data.wfs] : [],
        mcps: Array.isArray(props.data.mcps) ? [...props.data.mcps] : [],
        skills: Array.isArray(props.data.skills) ? [...props.data.skills] : [],
        enabled: props.data.enabled
      }
    } else {
      resetForm()
    }

    // 3. 强制刷新 AgentCapabilityPicker
    // 使用 key 或强制重新渲染
  }
})
```

#### 方案B：添加调试日志

```javascript
// AgentConfigDrawer.vue
function handleSubmit() {
  console.log('=== 提交数据 ===')
  console.log('tools:', formData.value.tools)
  console.log('mcps:', formData.value.mcps)
  console.log('skills:', formData.value.skills)

  if (!formData.value.name.trim()) {
    ElMessage.warning('请输入智能体名称')
    return
  }
  emit('submit', formData.value)
}

function handleCapabilityUpdate(capabilities) {
  console.log('=== 能力更新 ===')
  console.log('接收到的数据:', capabilities)

  formData.value.tools = capabilities.tools
  formData.value.docs = capabilities.docs
  formData.value.wfs = capabilities.wfs
  formData.value.mcps = capabilities.mcps
  formData.value.skills = capabilities.skills

  console.log('更新后的 formData:', formData.value)
}
```

#### 方案C：强制重新渲染（激进方案）

```vue
<template>
  <AgentConfigDrawer
    :visible="drawerVisible"
    :data="editingAgent"
    @submit="handleSubmit"
    @update:visible="drawerVisible = $event"
  />
</template>

<!-- 改为使用 key 强制重新渲染 -->
<AgentConfigDrawer
  v-if="drawerVisible"
  :key="editingAgent?.id || 'new'"
  :visible="drawerVisible"
  :data="editingAgent"
  @submit="handleSubmit"
  @update:visible="drawerVisible = $event"
/>
```

---

## 完整修复方案

### 修复1：技能脚本执行

创建新文件：`backend/app/core/agent/skill_tool_executor.py`

```python
"""技能工具执行器：集成脚本执行到技能工具中。"""
import json
from typing import Any
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.skills.script_executor import execute_skill_script
from app.models.skill import Skill


def create_skill_tool_with_scripts(sk: Skill) -> StructuredTool:
    """创建带脚本执行的技能工具。"""

    class SkillInput(BaseModel):
        query: str = Field(description="用户查询或输入文本")

    async def _execute_skill(query: str) -> str:
        """执行技能脚本链。"""
        # 1. 准备输入数据
        inputs = {"text": query, "query": query}
        script_results = []

        # 2. 按顺序执行脚本
        for idx, script in enumerate(sk.scripts or []):
            script_name = script.get("name", f"script_{idx}")
            script_content = script.get("content", "")

            if not script_content:
                continue

            try:
                # 执行脚本
                result = await execute_skill_script(
                    script_name=script_name,
                    script_content=script_content,
                    inputs=inputs,
                    timeout=30,
                )

                if result["success"]:
                    # 将输出作为下一个脚本的输入
                    if isinstance(result["output"], dict):
                        inputs.update(result["output"])
                    else:
                        inputs["result"] = result["output"]

                    script_results.append({
                        "script": script_name,
                        "success": True,
                        "output": result["output"]
                    })
                else:
                    script_results.append({
                        "script": script_name,
                        "success": False,
                        "error": result["error"]
                    })

            except Exception as e:
                script_results.append({
                    "script": script_name,
                    "success": False,
                    "error": str(e)
                })

        # 3. 构建返回结果
        output = f"[SKILL {sk.name}]\n{sk.prompt or ''}\n\n"

        if script_results:
            # 有脚本执行结果
            output += "脚本执行结果:\n"
            for result in script_results:
                if result["success"]:
                    output += f"✓ {result['script']}: {result['output']}\n"
                else:
                    output += f"✗ {result['script']}: {result['error']}\n"
            output += f"\n用户输入: {query}"
        else:
            # 没有脚本，只返回 prompt
            output += f"用户输入: {query}"

        return output

    # 创建工具名称
    tool_name = _sanitize_tool_name(sk.name, prefix="skill")

    return StructuredTool.from_function(
        coroutine=_execute_skill,
        name=tool_name,
        description=sk.description or f"激活技能：{sk.name}",
        args_schema=SkillInput,
    )


def _sanitize_tool_name(name: str, prefix: str = "tool") -> str:
    """将名称转换为合法格式。"""
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    if sanitized and sanitized[0].isdigit():
        sanitized = f'{prefix}_{sanitized}'
    if not sanitized or sanitized == '_' * len(sanitized):
        sanitized = f'{prefix}_unnamed'
    return sanitized
```

### 修复2：前端数据丢失

创建调试和修复工具：`frontend/src/utils/agentDebug.ts`

```typescript
/**
 * 智能体配置调试工具
 */

export function debugAgentForm(formData: any, phase: string) {
  console.group(`[智能体调试] ${phase}`)
  console.log('完整表单数据:', JSON.parse(JSON.stringify(formData)))
  console.log('工具:', formData.tools)
  console.log('MCP:', formData.mcps)
  console.log('技能:', formData.skills)
  console.log('文档:', formData.docs)
  console.log('工作流:', formData.wfs)
  console.groupEnd()
}

export function validateAgentData(data: any): boolean {
  const required = ['name', 'model']
  const arrays = ['tools', 'mcps', 'skills', 'docs', 'wfs']

  let valid = true

  for (const field of required) {
    if (!data[field]) {
      console.error(`缺少必填字段: ${field}`)
      valid = false
    }
  }

  for (const field of arrays) {
    if (!Array.isArray(data[field])) {
      console.error(`${field} 不是数组:`, data[field])
      valid = false
    }
  }

  return valid
}
```

---

## 实施步骤

### 第一步：修复技能脚本执行

1. 创建 `skill_tool_executor.py`
2. 修改 `tool_registry.py` 使用新的技能工具
3. 测试脚本执行功能

### 第二步：修复前端数据丢失

1. 添加调试日志
2. 确认问题根源
3. 应用修复方案

### 第三步：验证修复

1. 测试技能脚本执行
2. 测试配置保存和编辑
3. 验证所有功能正常