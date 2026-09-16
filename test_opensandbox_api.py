"""测试 OpenSandbox HTTP API 格式"""
import httpx
import json

API_URL = "http://192.168.137.13:8090"
API_KEY = "easyrag2026"


async def test_opensandbox_api():
    """测试不同的 API 请求格式"""

    headers = {
        "OPEN-SANDBOX-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }

    # 测试1: 最简单的请求（仅必需字段）
    print("=" * 60)
    print("测试1: 最简单的请求")
    print("=" * 60)

    payload1 = {
        "image": {"uri": "python:3.11-slim"},
        "entrypoint": ["python", "-c", "print('Hello')"],
        "resourceLimits": {
            "cpu": "1000m",
            "memory": "512Mi"
        },
        "timeout": 60
    }

    print(f"请求体:\n{json.dumps(payload1, indent=2)}")

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                f"{API_URL}/sandboxes",
                headers=headers,
                json=payload1
            )
            print(f"\n状态码: {response.status_code}")
            print(f"响应: {response.text}")
        except Exception as e:
            print(f"\n错误: {e}")

    # 测试2: 尝试不同的字段名
    print("\n" + "=" * 60)
    print("测试2: 尝试使用 command 而不是 entrypoint")
    print("=" * 60)

    payload2 = {
        "image": {"uri": "python:3.11-slim"},
        "command": ["python", "-c", "print('Hello')"],
        "resourceLimits": {
            "cpu": "1000m",
            "memory": "512Mi"
        },
        "timeout": 60
    }

    print(f"请求体:\n{json.dumps(payload2, indent=2)}")

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                f"{API_URL}/sandboxes",
                headers=headers,
                json=payload2
            )
            print(f"\n状态码: {response.status_code}")
            print(f"响应: {response.text}")
        except Exception as e:
            print(f"\n错误: {e}")

    # 测试3: 查看当前 API 支持的字段
    print("\n" + "=" * 60)
    print("测试3: 获取 API 文档")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            # 尝试 OpenAPI 端点
            for endpoint in ["/openapi.json", "/docs", "/api", "/swagger.json"]:
                response = await client.get(f"{API_URL}{endpoint}")
                if response.status_code == 200:
                    print(f"找到文档: {endpoint}")
                    if endpoint.endswith(".json"):
                        print(response.text[:500])
                    break
        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_opensandbox_api())