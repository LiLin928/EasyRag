"""
使用配置文件中的设置测试 OpenSandbox

根据 opensandbox-config.toml 的分析：
- execd_image 已配置为 python:3.11-slim
- 这意味着 OpenSandbox 应该能够正常工作
"""
import httpx
import json
import asyncio

API_URL = "http://192.168.137.13:8090"
API_KEY = "easyrag2026"


async def test_with_config():
    """根据配置文件测试"""

    headers = {
        "OPEN-SANDBOX-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }

    # 尝试1: 使用配置文件中的镜像，不指定镜像（使用默认）
    tests = [
        {
            "name": "测试1: 使用默认镜像（不指定）",
            "payload": {
                "command": ["python", "-c", "print('Hello')"],
                "timeout_seconds": 60
            }
        },
        {
            "name": "测试2: 指定镜像为字符串",
            "payload": {
                "image": "python:3.11-slim",
                "command": ["python", "-c", "print('Hello')"],
                "timeout_seconds": 60
            }
        },
        {
            "name": "测试3: 指定镜像为对象",
            "payload": {
                "image": {"uri": "python:3.11-slim"},
                "entrypoint": ["python", "-c", "print('Hello')"],
                "timeout": 60,
                "resourceLimits": {
                    "cpu": "500m",
                    "memory": "256Mi"
                }
            }
        },
    ]

    async with httpx.AsyncClient(timeout=180) as client:
        for test in tests:
            print("=" * 80)
            print(test['name'])
            print("=" * 80)
            print(f"请求体:\n{json.dumps(test['payload'], indent=2)}")

            try:
                response = await client.post(
                    f"{API_URL}/sandboxes",
                    headers=headers,
                    json=test['payload']
                )

                print(f"\n状态码: {response.status_code}")

                if response.status_code in [200, 202]:
                    print("[成功] 沙箱创建成功！")
                    result = response.json()
                    print(f"响应: {json.dumps(result, indent=2)}")

                    # 如果成功，等待并获取结果
                    sandbox_id = result.get('id') or result.get('sandbox_id')
                    if sandbox_id:
                        print(f"\n等待执行...")
                        await asyncio.sleep(10)

                        # 获取日志
                        logs_resp = await client.get(
                            f"{API_URL}/sandboxes/{sandbox_id}/diagnostics/logs",
                            headers=headers
                        )
                        if logs_resp.status_code == 200:
                            logs = logs_resp.json()
                            print(f"输出: {logs.get('stdout', '')}")

                        # 清理
                        await client.delete(
                            f"{API_URL}/sandboxes/{sandbox_id}",
                            headers=headers
                        )
                        print("沙箱已清理")

                    return True
                elif response.status_code == 422:
                    error = response.json()
                    print(f"[422] {error.get('detail', [{}])[0].get('msg', '格式错误')}")
                elif response.status_code == 500:
                    error = response.json()
                    print(f"[500] {error.get('message', '')[:200]}")
                else:
                    print(f"响应: {response.text[:300]}")

            except Exception as e:
                print(f"[异常] {e}")

            print()

    return False


if __name__ == "__main__":
    result = asyncio.run(test_with_config())
    if result:
        print("\n✓ 测试成功")
    else:
        print("\n✗ 所有测试失败")