"""使用正确的 OpenSandbox API 格式"""
import httpx
import json
import asyncio

API_URL = "http://192.168.137.13:8090"
API_KEY = "easyrag2026"


async def test_correct_format():
    """使用正确的 API 格式（从错误信息中推断）"""

    headers = {
        "OPEN-SANDBOX-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }

    # 正确的格式
    payload = {
        "image": {"uri": "python:3.10-alpine"},
        "entrypoint": ["python", "-c", "print('Hello from OpenSandbox')"],
        "resourceLimits": {
            "cpu": "1000m",
            "memory": "512Mi"
        },
        "timeout": 120  # 增加超时，允许镜像拉取
    }

    print("=" * 60)
    print("使用正确的 OpenSandbox API 格式")
    print("=" * 60)
    print(f"请求体:\n{json.dumps(payload, indent=2)}")

    async with httpx.AsyncClient(timeout=180) as client:  # 3分钟超时
        try:
            print("\n正在创建沙箱...")
            response = await client.post(
                f"{API_URL}/sandboxes",
                headers=headers,
                json=payload
            )

            print(f"\n状态码: {response.status_code}")
            print(f"响应体: {response.text}")

            if response.status_code == 202:
                result = response.json()
                sandbox_id = result.get("id") or result.get("sandbox_id")
                print(f"\n[OK] 沙箱创建成功，ID: {sandbox_id}")

                # 等待执行完成
                print("\n等待执行...")
                for i in range(20):  # 最多等待 20 次
                    await asyncio.sleep(3)

                    status_response = await client.get(
                        f"{API_URL}/sandboxes/{sandbox_id}",
                        headers=headers
                    )

                    if status_response.status_code == 200:
                        status = status_response.json()
                        state = status.get("status", {}).get("state") or status.get("status")
                        print(f"  [{i+1}] 状态: {state}")

                        if state in ["Terminated", "Error"]:
                            break

                # 获取日志
                logs_response = await client.get(
                    f"{API_URL}/sandboxes/{sandbox_id}/diagnostics/logs",
                    headers=headers
                )

                if logs_response.status_code == 200:
                    logs = logs_response.json()
                    print(f"\n日志:")
                    print(f"  stdout: {logs.get('stdout', '')[:500]}")
                    print(f"  stderr: {logs.get('stderr', '')[:500]}")

                # 清理
                await client.delete(
                    f"{API_URL}/sandboxes/{sandbox_id}",
                    headers=headers
                )
                print("\n沙箱已清理")

        except httpx.TimeoutException:
            print("\n[TIMEOUT] 请求超时，可能镜像正在下载")
        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_correct_format())