"""
使用完整的必需字段测试 OpenSandbox
"""
import httpx
import json
import asyncio

API_URL = "http://192.168.137.13:8090"
API_KEY = "easyrag2026"


async def test_complete_payload():
    """测试包含所有必需字段的请求"""

    headers = {
        "OPEN-SANDBOX-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }

    # 完整的必需字段
    payload = {
        "image": {"uri": "python:3.11-slim"},
        "entrypoint": ["python", "-c", "print('Hello from EasyRAG')"],
        "resourceLimits": {
            "cpu": "500m",
            "memory": "256Mi"
        },
        "timeout": 60
    }

    print("=" * 80)
    print("测试完整请求（所有必需字段）")
    print("=" * 80)
    print(f"请求体:\n{json.dumps(payload, indent=2)}")

    async with httpx.AsyncClient(timeout=180) as client:
        try:
            print("\n正在创建沙箱...")
            response = await client.post(
                f"{API_URL}/sandboxes",
                headers=headers,
                json=payload
            )

            print(f"\n状态码: {response.status_code}")
            print(f"响应: {response.text}")

            if response.status_code in [200, 202]:
                print("\n[成功] 沙箱创建成功！")
                result = response.json()
                sandbox_id = result.get('id') or result.get('sandbox_id')
                print(f"沙箱 ID: {sandbox_id}")

                # 等待执行
                print(f"\n等待执行...")
                await asyncio.sleep(15)

                # 获取状态
                status_resp = await client.get(
                    f"{API_URL}/sandboxes/{sandbox_id}",
                    headers=headers
                )
                if status_resp.status_code == 200:
                    status = status_resp.json()
                    print(f"状态: {json.dumps(status, indent=2)}")

                # 获取日志
                logs_resp = await client.get(
                    f"{API_URL}/sandboxes/{sandbox_id}/diagnostics/logs",
                    headers=headers
                )
                if logs_resp.status_code == 200:
                    logs = logs_resp.json()
                    print(f"\n输出:")
                    print(f"  stdout: {logs.get('stdout', '')}")
                    print(f"  stderr: {logs.get('stderr', '')}")

                # 清理
                await client.delete(
                    f"{API_URL}/sandboxes/{sandbox_id}",
                    headers=headers
                )
                print("\n沙箱已清理")

                return True

            elif response.status_code == 422:
                error = response.json()
                print(f"\n[422 错误]")
                if 'detail' in error:
                    for detail in error['detail']:
                        print(f"  位置: {detail.get('loc')}")
                        print(f"  消息: {detail.get('msg')}")

            elif response.status_code == 500:
                error = response.json()
                print(f"\n[500 错误]")
                print(f"  代码: {error.get('code')}")
                print(f"  消息: {error.get('message', '')[:300]}")

                if 'execd' in error.get('message', ''):
                    print("\n结论: 镜像缺少 /execd 文件")

            return False

        except Exception as e:
            print(f"\n[异常] {e}")
            return False


if __name__ == "__main__":
    result = asyncio.run(test_complete_payload())
    if result:
        print("\n" + "=" * 80)
        print("测试成功！OpenSandbox 正常工作")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("测试失败，需要在虚拟机上构建兼容镜像")
        print("=" * 80)