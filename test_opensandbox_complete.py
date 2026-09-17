"""
完整的 OpenSandbox 功能测试
"""
import asyncio
import sys
import json
import httpx

sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')


async def test_opensandbox_complete():
    """完整测试：创建 -> 执行 -> 获取日志 -> 清理"""

    API_URL = "http://192.168.137.13:8090"
    API_KEY = "easyrag2026"

    headers = {
        "OPEN-SANDBOX-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "image": {"uri": "python:3.11-slim"},
        "entrypoint": ["python", "-c", "print('Hello from OpenSandbox!'); print('1+100=', 1+100)"],
        "resourceLimits": {
            "cpu": "500m",
            "memory": "256Mi"
        },
        "timeout": 60
    }

    print("=" * 80)
    print("OpenSandbox 完整功能测试")
    print("=" * 80)

    async with httpx.AsyncClient(timeout=180) as client:
        try:
            # 1. 创建沙箱
            print("\n[1/4] 创建沙箱")
            print("-" * 80)
            print(f"请求:\n{json.dumps(payload, indent=2)}")

            response = await client.post(f"{API_URL}/sandboxes", headers=headers, json=payload)
            print(f"\n状态码: {response.status_code}")

            if response.status_code not in [200, 202]:
                print(f"[失败] {response.text}")
                return False

            result = response.json()
            sandbox_id = result.get("id")
            print(f"\n[成功] 沙箱创建成功")
            print(f"  ID: {sandbox_id}")
            print(f"  状态: {result.get('status', {}).get('state')}")

            # 2. 等待执行完成
            print("\n[2/4] 等待执行")
            print("-" * 80)

            await asyncio.sleep(10)

            status_response = await client.get(f"{API_URL}/sandboxes/{sandbox_id}", headers=headers)
            if status_response.status_code == 200:
                status = status_response.json()
                print(f"状态: {status.get('status', {}).get('state')}")

            # 3. 获取日志
            print("\n[3/4] 获取日志")
            print("-" * 80)

            logs_response = await client.get(f"{API_URL}/sandboxes/{sandbox_id}/diagnostics/logs", headers=headers)
            if logs_response.status_code == 200:
                logs = logs_response.json()
                stdout = logs.get('stdout', '')
                stderr = logs.get('stderr', '')

                print(f"输出:")
                print(f"  stdout: {stdout}")
                if stderr:
                    print(f"  stderr: {stderr}")

                if "Hello from OpenSandbox" in stdout:
                    print("\n[成功] 代码执行成功")
                    success = True
                else:
                    print("\n[失败] 未找到预期输出")
                    success = False
            else:
                print(f"[失败] 无法获取日志: {logs_response.status_code}")
                success = False

            # 4. 清理
            print("\n[4/4] 清理沙箱")
            print("-" * 80)

            delete_response = await client.delete(f"{API_URL}/sandboxes/{sandbox_id}", headers=headers)
            print(f"删除状态: {delete_response.status_code}")
            print("[完成] 沙箱已清理")

            return success

        except Exception as e:
            print(f"\n[异常] {type(e).__name__}: {e}")
            return False


async def test_skill_script():
    """测试技能脚本执行"""

    print("\n" + "=" * 80)
    print("技能脚本执行测试")
    print("=" * 80)

    # 使用后端代码
    from app.providers.sandbox import run_in_sandbox

    code = """
import re

def main(inputs):
    text = inputs.get('text', inputs.get('query', ''))
    pattern = r"[-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?"
    numbers = re.findall(pattern, text)
    numbers = [float(n) for n in numbers]

    if not numbers:
        return {"error": "未找到数字"}

    total = sum(numbers) + 100
    expression = " + ".join(str(n) for n in numbers)
    result = f"{expression} = {int(total)}"

    return {
        "numbers": numbers,
        "total": total,
        "result": result
    }
"""

    print("\n执行技能脚本: 计算 1+100+100")
    print("-" * 80)

    result = await run_in_sandbox(
        code=code,
        inputs={"text": "计算 1+100", "query": "计算 1+100"},
        timeout=60,
        memory_mb=256,
    )

    print(f"成功: {result.ok}")
    print(f"输出: {result.output}")
    print(f"错误: {result.error}")

    if result.ok and result.output:
        output = result.output
        if isinstance(output, dict):
            print(f"\n结果:")
            print(f"  数字: {output.get('numbers')}")
            print(f"  总和: {output.get('total')}")
            print(f"  算式: {output.get('result')}")

            if output.get('total') == 201:
                print("\n[成功] 技能脚本正确执行：1+100+100=201")
                return True
            else:
                print(f"\n[失败] 结果不正确")
                return False

    return False


async def main():
    """主测试流程"""

    # 测试1: 完整功能测试
    result1 = await test_opensandbox_complete()

    # 测试2: 技能脚本测试
    if result1:
        result2 = await test_skill_script()
    else:
        result2 = False

    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print(f"沙箱功能测试: {'通过' if result1 else '失败'}")
    print(f"技能脚本测试: {'通过' if result2 else '失败'}")

    if result1 and result2:
        print("\n[全部通过] OpenSandbox 集成正常工作！")
        print("技能脚本可以正确执行 1+100+100=201")
    else:
        print("\n[部分失败] 需要进一步调试")

    return result1 and result2


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)