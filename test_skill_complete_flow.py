"""
完整测试技能脚本执行

测试流程：
1. 检查 OpenSandbox 服务
2. 检查镜像是否包含 /execd
3. 测试技能工具创建
4. 测试脚本执行
"""
import asyncio
import sys
import json
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')


async def test_opensandbox_service():
    """测试 OpenSandbox 服务"""
    import httpx

    print("=" * 80)
    print("1. 测试 OpenSandbox 服务")
    print("=" * 80)

    API_URL = "http://192.168.137.13:8090"
    API_KEY = "easyrag2026"

    headers = {"OPEN-SANDBOX-API-KEY": API_KEY}

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(f"{API_URL}/health")
            if response.status_code == 200:
                print("[OK] 服务健康")
                return True
            else:
                print(f"[FAIL] 服务异常: {response.status_code}")
                return False
        except Exception as e:
            print(f"[ERROR] {e}")
            return False


async def test_skill_script_execution():
    """测试技能脚本执行"""
    from app.core.agent.skill_tool_executor import create_skill_tool_with_scripts
    from app.models.skill import Skill

    print("\n" + "=" * 80)
    print("2. 测试技能脚本执行")
    print("=" * 80)

    # 创建测试技能
    skill = Skill(
        id="test-skill",
        name="数字相加计算",
        description="执行数字相加计算",
        prompt="你是一个数学计算助手。",
        scripts=[
            {
                "name": "数字相加.py",
                "content": """
import re

def main(inputs):
    text = inputs.get('text', inputs.get('query', ''))

    # 提取数字
    pattern = r"[-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?"
    numbers = re.findall(pattern, text)
    numbers = [float(n) for n in numbers]

    if not numbers:
        return {"error": "未找到数字"}

    # 计算总和（加 100 测试）
    total = sum(numbers) + 100

    # 格式化结果
    expression = " + ".join(str(n) for n in numbers)
    result = f"{expression} = {int(total)}"

    return {
        "numbers": numbers,
        "total": total,
        "result": result
    }
"""
            }
        ]
    )

    # 创建工具
    tool = create_skill_tool_with_scripts(skill)
    print(f"[OK] 工具创建成功: {tool.name}")

    # 测试执行
    print("\n测试执行...")
    try:
        result = await tool.ainvoke({"query": "计算 1+100"})
        print(f"\n[结果]\n{result}")

        # 验证结果
        if "201" in str(result):
            print("\n[OK] 测试通过：正确计算了 1+100+100=201")
            return True
        else:
            print(f"\n[FAIL] 测试失败：未找到预期结果")
            return False

    except Exception as e:
        print(f"\n[ERROR] 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试流程"""
    print("\n" + "=" * 80)
    print("EasyRAG 技能脚本执行测试")
    print("=" * 80)

    # 测试1: OpenSandbox 服务
    service_ok = await test_opensandbox_service()

    if not service_ok:
        print("\n[跳过] OpenSandbox 服务不可用，无法继续测试")
        return

    # 测试2: 技能脚本执行
    execution_ok = await test_skill_script_execution()

    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print(f"OpenSandbox 服务: {'OK' if service_ok else 'FAIL'}")
    print(f"技能脚本执行: {'OK' if execution_ok else 'FAIL'}")

    if execution_ok:
        print("\n所有测试通过！技能脚本执行正常工作。")
    else:
        print("\n测试失败。请检查 OpenSandbox 镜像是否包含 /execd 文件。")
        print("参考: docs/opensandbox-integration.md")


if __name__ == "__main__":
    asyncio.run(main())