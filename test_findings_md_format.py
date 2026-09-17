"""严格按照 findings.md 的 API 格式测试"""
import httpx
import json
import asyncio

API_URL = "http://192.168.137.13:8090"
API_KEY = "easyrag2026"


async def test_findings_md_format():
    """完全按照 findings.md 第 83-95 行的格式测试"""

    headers = {
        "OPEN-SANDBOX-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }

    # findings.md 中的格式
    payload = {
        "image": "python:3.10-alpine",
        "command": ["python", "-c", "print('Hello from findings.md')"],
        "env": {"KEY": "value"},
        "resources": {
            "memory_mb": 512,
            "cpu": 1.0
        },
        "timeout_seconds": 30,
        "metadata": {"key": "value"}
    }

    print("=" * 80)
    print("测试 findings.md API 格式")
    print("=" * 80)
    print(f"请求体:\n{json.dumps(payload, indent=2)}")

    async with httpx.AsyncClient(timeout=120) as client:
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
                print("\n[成功] 沙箱创建成功！")
                result = response.json()
                print(f"沙箱 ID: {result.get('sandbox_id')}")
                print(f"状态: {result.get('status')}")
                return True
            elif response.status_code == 500:
                # 500 错误可能是因为镜像缺少 /execd
                error = response.json()
                print(f"\n[500 错误] {error.get('message', '')[:200]}")
                print("\n可能的原因：镜像缺少 /execd 文件")
                return False
            elif response.status_code == 422:
                # 422 错误是格式问题
                print(f"\n[422 错误] 格式不符合 API 要求")
                return False
            else:
                print(f"\n[其他错误] 状态码: {response.status_code}")
                return False

        except Exception as e:
            print(f"\n[异常] {e}")
            return False


if __name__ == "__main__":
    result = asyncio.run(test_findings_md_format())
    if result:
        print("\n✓ findings.md 格式可用")
    else:
        print("\n✗ findings.md 格式不可用，需要查看错误原因")