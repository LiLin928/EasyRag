"""直接测试 findings.md 中的 API 格式"""
import httpx
import json

API_URL = "http://192.168.137.13:8090"
API_KEY = "easyrag2026"


async def test_findings_format():
    """测试 findings.md 中的 API 格式"""

    headers = {
        "OPEN-SANDBOX-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }

    # 使用 findings.md 中的格式
    payload = {
        "image": "python:3.10-alpine",
        "command": ["python", "-c", "print('Hello')"],
        "resources": {
            "memory_mb": 512,
            "cpu": 1.0
        },
        "timeout_seconds": 30
    }

    print("=" * 60)
    print("测试 findings.md 中的 API 格式")
    print("=" * 60)
    print(f"请求体:\n{json.dumps(payload, indent=2)}")

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(
                f"{API_URL}/sandboxes",
                headers=headers,
                json=payload
            )
            print(f"\n状态码: {response.status_code}")
            print(f"响应头: {dict(response.headers)}")
            print(f"响应体: {response.text}")

            if response.status_code == 202:
                print("\n[OK] 沙箱创建成功")
                result = response.json()
                print(f"沙箱 ID: {result.get('sandbox_id')}")
                print(f"状态: {result.get('status')}")
            else:
                print(f"\n[FAIL] 创建失败")

        except Exception as e:
            print(f"\n[ERROR] {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_findings_format())