"""技能工具执行器：集成脚本执行到技能工具中。"""
import json
import re
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.skills.script_executor import execute_skill_script
from app.models.skill import Skill


def _sanitize_tool_name(name: str, prefix: str = "skill") -> str:
    """将名称转换为合法格式。"""
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    if sanitized and sanitized[0].isdigit():
        sanitized = f'{prefix}_{sanitized}'
    if not sanitized or sanitized == '_' * len(sanitized):
        sanitized = f'{prefix}_unnamed'
    return sanitized


def create_skill_tool_with_scripts(sk: Skill) -> StructuredTool:
    """创建带脚本执行的技能工具。

    Args:
        sk: 技能实例

    Returns:
        LangChain StructuredTool
    """

    class SkillInput(BaseModel):
        query: str = Field(description="用户查询或输入文本")

    async def _execute_skill(query: str) -> str:
        """执行技能脚本链。

        工作流程：
        1. 准备输入数据
        2. 按顺序执行所有脚本
        3. 将每个脚本的输出作为下一个脚本的输入
        4. 返回增强后的上下文
        """
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
                # 智能包装脚本，自动识别和调用函数
                wrapped_script = _wrap_script_with_auto_call(
                    script_name,
                    script_content,
                    inputs
                )

                # 执行脚本
                result = await execute_skill_script(
                    script_name=script_name,
                    script_content=wrapped_script,
                    inputs=inputs,
                    timeout=30,
                )

                if result["success"]:
                    # 将输出作为下一个脚本的输入
                    output = result["output"]
                    if isinstance(output, dict):
                        inputs.update(output)
                    else:
                        inputs["result"] = output

                    script_results.append({
                        "script": script_name,
                        "success": True,
                        "output": output
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
                    output_result = result["output"]
                    if isinstance(output_result, (dict, list)):
                        output_result = json.dumps(output_result, ensure_ascii=False)
                    output += f"✓ {result['script']}: {output_result}\n"
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


def _wrap_script_with_auto_call(script_name: str, script_content: str, inputs: dict) -> str:
    """智能包装脚本，自动识别和调用函数。

    检测脚本中定义的函数，并自动调用最合适的函数。
    """
    # 1. 提取脚本中定义的函数名
    function_pattern = r'def\s+(\w+)\s*\('
    defined_functions = re.findall(function_pattern, script_content)

    if not defined_functions:
        # 没有定义函数，直接返回原脚本
        return script_content

    # 2. 生成自动调用代码
    auto_call_code = f"""
# 自动生成的函数调用逻辑
import json

# 已定义的函数: {defined_functions}
_defined_functions = {defined_functions}

# 根据函数名和参数智能调用
result = None
inputs = json.loads('''{json.dumps(inputs)}''')

# 尝试调用最合适的函数
if 'main' in _defined_functions:
    result = main(inputs)
elif 'run' in _defined_functions:
    result = run(inputs)
elif 'execute' in _defined_functions:
    result = execute(inputs)
else:
    # 尝试根据输入参数匹配函数
    for func_name in _defined_functions:
        try:
            func = eval(func_name)
            # 尝试不同的参数组合
            if 'text' in inputs or 'query' in inputs:
                text_param = inputs.get('text', inputs.get('query', ''))
                result = func(text_param)
                break
            elif 'numbers' in inputs:
                result = func(inputs['numbers'])
                break
            else:
                # 尝试直接传入 inputs 字典
                result = func(inputs)
                break
        except Exception as e:
            continue

# 如果所有尝试都失败，返回 None
if result is None:
    result = {{"warning": "No suitable function found", "available_functions": _defined_functions}}

print(json.dumps({{"success": True, "output": result}}))
"""

    # 3. 组合完整脚本
    return f"{script_content}\n\n{auto_call_code}"