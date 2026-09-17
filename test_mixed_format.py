"""测试混合格式（GitHub OpenAPI + findings.md）"""
import httpx
import json

API_URL = "http://192.168.137.13:8090"
API_KEY = "easyrag2026"


async def test_mixed_format():
    """测试混合格式"""

    headers = {
        "OPEN-SANDBOX-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }

    tests = [
        # 测试1: image 为对象，其他字段使用 findings.md 格式
        {
            "name": "image对象 + findings字段",
            "payload": {
                "image": {"uri": "python:3.10-alpine"},
                "command": ["python", "-c", "print('Hello')"],
                "resources": {
                    "memory_mb": 512,
                    "cpu": 1.0
                },
                "timeout_seconds": 30
            }
        },
        # 测试2: image 为对象，使用 GitHub OpenAPI 字段
        {
            "name": "image对象 + OpenAPI字段",
            "payload": {
                "image": {"uri": "python:3.10-alpine"},
                "entrypoint": ["python", "-c", "print('Hello')"],
                "resourceLimits": {
                    "cpu": "1000m",
                    "memory": "512Mi"
                },
                "timeout": 60
            }
        },
        # 测试3: image 为对象，混合字段
        {
            "name": "image对象 + 混合字段",
            "payload": {
                "image": {"uri": "python:3.10-alpine"},
                "command": ["python", "-c", "print('Hello')"],
                "resourceLimits": {
                    "cpu": "1000m",
                    "memory": "512Mi"
                },
                "timeout": 60
            }
        },
    ]

    async with httpx.AsyncClient(timeout=60) as client:
        for test in tests:
            print("=" * 60)
            print(f"测试: {test['name']}")
            print("=" * 60)
            print(f"请求体:\n{json.dumps(test['payload'], indent=2)}")

            try:
                response = await client.post(
                    f"{API_URL}/sandboxes",
                    headers=headers,
                    json=test['payload']
                )
                print(f"\n状态码: {response.status_code}")

                if response.status_code == 202:
                    print("[OK] 沙箱创建成功")
                    result = response.json()
                    print(f"响应: {json.dumps(result, indent=2)}")
                    break
                else:
                    print(f"响应: {response.text[:300]}")

            except Exception as e:
                print(f"[ERROR] {e}")

            print()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_mixed_format())