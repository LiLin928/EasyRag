"""测试 OpenSandbox 推荐的基础镜像"""
import httpx
import json

API_URL = "http://192.168.137.13:8090"
API_KEY = "easyrag2026"


async def test_opensandbox_images():
    """测试 OpenSandbox 推荐的镜像"""

    headers = {
        "OPEN-SANDBOX-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }

    # OpenSandbox 推荐的基础镜像
    test_images = [
        # 官方 OpenSandbox 镜像
        "ghcr.io/opensandbox-group/opensandbox-python:3.11",
        "opensandbox/python:3.11",

        # 尝试不同的 Python 镜像标签
        "python:3.11",
        "python:3.11-slim",

        # 尝试 alpine
        "alpine:latest",
    ]

    for image in test_images:
        print("=" * 60)
        print(f"测试镜像: {image}")
        print("=" * 60)

        payload = {
            "image": {"uri": image},
            "entrypoint": ["python", "-c", "print('Hello from OpenSandbox')"],
            "resourceLimits": {
                "cpu": "1000m",
                "memory": "512Mi"
            },
            "timeout": 60
        }

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.post(
                    f"{API_URL}/sandboxes",
                    headers=headers,
                    json=payload
                )
                print(f"状态码: {response.status_code}")

                if response.status_code == 202:
                    # 成功创建
                    result = response.json()
                    print(f"✓ 成功！沙箱 ID: {result['id']}")
                    print(f"状态: {result['status']}")

                    # 等待执行完成
                    sandbox_id = result['id']
                    print(f"\n等待沙箱执行...")

                    import asyncio
                    await asyncio.sleep(5)

                    # 获取结果
                    logs_response = await client.get(
                        f"{API_URL}/sandboxes/{sandbox_id}/logs",
                        headers=headers
                    )
                    print(f"日志状态码: {logs_response.status_code}")
                    print(f"日志: {logs_response.text[:500]}")

                    # 清理沙箱
                    await client.delete(
                        f"{API_URL}/sandboxes/{sandbox_id}",
                        headers=headers
                    )
                    print("沙箱已清理")
                    break
                else:
                    print(f"响应: {response.text[:300]}")

            except Exception as e:
                print(f"错误: {e}")

        print()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_opensandbox_images())