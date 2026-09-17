"""
详细调试 OpenSandbox API
"""
import asyncio
import sys
import json
import httpx

sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.providers.sandbox.opensandbox_client import get_opensandbox_client


async def debug_opensandbox_api():
    """详细调试 API 调用"""

    print("=" * 80)
    print("详细调试 OpenSandbox API")
    print("=" * 80)

    client = get_opensandbox_client()

    # 准备 payload
    payload = {
        "image": {"uri": "python:3.11-slim"},
        "entrypoint": ["python", "-c", "print('test')"],
        "resourceLimits": {
            "cpu": "500m",
            "memory": "256Mi"
        },
        "timeout": 60
    }

    print(f"\n请求体:\n{json.dumps(payload, indent=2)}")

    try:
        print("\n正在创建沙箱...")
        response = await client._request("POST", "/sandboxes", json=payload)

        print(f"\n[成功] 响应:")
        print(json.dumps(response, indent=2))

    except Exception as e:
        print(f"\n[错误] {type(e).__name__}: {e}")

        # 尝试直接 HTTP 调用
        print("\n尝试直接 HTTP 调用...")

        async with httpx.AsyncClient(timeout=180) as http_client:
            try:
                response = await http_client.post(
                    "http://192.168.137.13:8090/sandboxes",
                    headers={
                        "OPEN-SANDBOX-API-KEY": "easyrag2026",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )

                print(f"\nHTTP 状态码: {response.status_code}")
                print(f"HTTP 响应: {response.text}")

                if response.status_code == 500:
                    error = response.json()
                    print(f"\n错误代码: {error.get('code')}")
                    print(f"错误消息: {error.get('message', '')[:300]}")

                    if 'execd' in error.get('message', ''):
                        print("\n确认: 镜像缺少 /execd 文件")

            except Exception as e2:
                print(f"\nHTTP 调用失败: {e2}")


if __name__ == "__main__":
    asyncio.run(debug_opensandbox_api())