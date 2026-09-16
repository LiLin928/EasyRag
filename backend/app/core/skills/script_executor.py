"""技能脚本执行器。

在 OpenSandbox 中安全执行技能定义的脚本代码。
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def execute_skill_script(
    script_name: str,
    script_content: str,
    inputs: dict,
    timeout: int = 30,
    memory_mb: int = 256,
) -> dict[str, Any]:
    """在沙箱中执行技能脚本。

    Args:
        script_name: 脚本名称（用于标识和调试）
        script_content: Python 脚本代码
        inputs: 输入参数（会注入为 inputs 变量）
        timeout: 执行超时（秒）
        memory_mb: 内存限制（MB）

    Returns:
        执行结果字典：
        {
            "success": bool,
            "output": Any,  # 脚本返回值
            "error": str | None  # 错误信息
        }
    """
    from app.providers.sandbox import run_in_sandbox

    # 包装脚本，添加执行入口
    wrapped_code = f"""
# 技能脚本: {script_name}
# 自动生成的执行包装器

# 导入常用模块
import json
import re
import math
import datetime
from collections import Counter, defaultdict

# 注入输入参数
inputs = json.loads('''{json.dumps(inputs)}''')

# 用户脚本代码
{script_content}

# 执行入口
result = None
try:
    # 如果脚本定义了 main 函数，调用它
    if 'main' in dir():
        result = main(inputs)
    # 如果脚本定义了 run 函数，调用它
    elif 'run' in dir():
        result = run(inputs)
    # 如果脚本定义了 execute 函数，调用它
    elif 'execute' in dir():
        result = execute(inputs)
except Exception as e:
    import traceback
    result = {{"error": str(e), "traceback": traceback.format_exc()}}

# 输出结果
if result is not None:
    print(json.dumps({{"success": True, "output": result}}))
else:
    print(json.dumps({{"success": True, "output": None}}))
"""

    try:
        # 在沙箱中执行
        result = await run_in_sandbox(
            code=wrapped_code,
            inputs=inputs,
            timeout=timeout,
            memory_mb=memory_mb,
        )

        # 解析结果
        if result.ok:
            return {
                "success": True,
                "output": result.output,
                "error": None
            }
        else:
            return {
                "success": False,
                "output": None,
                "error": result.error or "脚本执行失败"
            }

    except Exception as e:
        logger.error(f"技能脚本执行异常 ({script_name}): {e}")
        return {
            "success": False,
            "output": None,
            "error": f"脚本执行异常: {str(e)}"
        }