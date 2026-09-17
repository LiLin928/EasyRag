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
        """技能工具输入参数。"""
        query: str = Field(
            default="",
            description="用户查询或输入文本（可选，如果不提供将使用空字符串）"
        )

    async def _execute_skill(query: str = "") -> str:
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
                # 执行脚本（script_executor.py 会自动包装和调用函数）
                result = await execute_skill_script(
                    script_name=script_name,
                    script_content=script_content,  # 直接传入原始脚本内容
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

    # 增强工具描述，明确使用场景
    enhanced_description = sk.description or f"激活技能：{sk.name}"

    # 如果有脚本，添加更明确的描述
    if sk.scripts:
        enhanced_description = (
            f"执行数学计算任务。{enhanced_description} "
            f"**必须使用此工具**来处理所有数学运算、数字计算、加法、减法等计算任务。"
        )

    return StructuredTool.from_function(
        coroutine=_execute_skill,
        name=tool_name,
        description=enhanced_description,
        args_schema=SkillInput,
    )


