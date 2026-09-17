"""
检查日志 API 响应格式
"""
import asyncio
import httpx

API_URL = "http://192.168.137.13:8090"
API_KEY = "easyrag2026"


async def test_logs_api():
    """测试日志 API"""

    headers = {
        "OPEN-SANDBOX-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "image": {"uri": "python:3.11-slim"},
        "entrypoint": ["python", "-c", "print('Test')"],
        "resourceLimits": {"cpu": "500m", "memory": "256Mi"},
        "timeout": 60
    }

    async with httpx.AsyncClient(timeout=180) as client:
        # 创建沙箱
        response = await client.post(f"{API_URL}/sandboxes", headers=headers, json=payload)
        sandbox_id = response.json().get("id")
        print(f"沙箱 ID: {sandbox_id}")

        # 等待执行
        await asyncio.sleep(10)

        # 获取日志（检查原始响应）
        print("\n获取日志...")
        logs_response = await client.get(
            f"{API_URL}/sandboxes/{sandbox_id}/diagnostics/logs",
            headers=headers
        )

        print(f"状态码: {logs_response.status_code}")
        print(f"Content-Type: {logs_response.headers.get('content-type')}")
        print(f"\n原始响应:\n{logs_response.text}")

        # 清理
        await client.delete(f"{API_URL}/sandboxes/{sandbox_id}", headers=headers)
        print("\n沙箱已清理")


if __name__ == "__main__":
    asyncio.run(test_logs_api())