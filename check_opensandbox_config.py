"""检查 OpenSandbox 服务配置和可用镜像"""
import httpx
import json

API_URL = "http://192.168.137.13:8090"
API_KEY = "easyrag2026"


async def check_opensandbox_config():
    """检查 OpenSandbox 服务配置"""

    headers = {
        "OPEN-SANDBOX-API-KEY": API_KEY,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        # 1. 检查健康状态
        print("=" * 60)
        print("1. 服务健康状态")
        print("=" * 60)

        try:
            response = await client.get(f"{API_URL}/health")
            print(f"状态: {response.status_code}")
            print(f"响应: {response.json()}")
        except Exception as e:
            print(f"错误: {e}")

        # 2. 检查可用的 pools
        print("\n" + "=" * 60)
        print("2. 可用的沙箱池")
        print("=" * 60)

        try:
            response = await client.get(f"{API_URL}/pools", headers=headers)
            print(f"状态: {response.status_code}")
            if response.status_code == 200:
                pools = response.json()
                print(json.dumps(pools, indent=2))
            else:
                print(f"响应: {response.text}")
        except Exception as e:
            print(f"错误: {e}")

        # 3. 检查 OpenAPI 文档中的 schemas
        print("\n" + "=" * 60)
        print("3. 检查 CreateSandboxRequest schema")
        print("=" * 60)

        try:
            response = await client.get(f"{API_URL}/openapi.json")
            openapi = response.json()

            # 提取 CreateSandboxRequest schema
            schemas = openapi.get("components", {}).get("schemas", {})

            if "CreateSandboxRequest" in schemas:
                print("CreateSandboxRequest 定义:")
                print(json.dumps(schemas["CreateSandboxRequest"], indent=2))

        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(check_opensandbox_config())