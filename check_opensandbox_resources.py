"""检查 OpenSandbox 的模板和快照"""
import httpx
import json

API_URL = "http://192.168.137.13:8090"
API_KEY = "easyrag2026"


async def check_opensandbox_resources():
    """检查 OpenSandbox 可用的资源"""

    headers = {
        "OPEN-SANDBOX-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        # 1. 检查模板
        print("=" * 60)
        print("检查可用模板")
        print("=" * 60)

        try:
            response = await client.get(
                f"{API_URL}/templates",
                headers=headers
            )
            print(f"状态码: {response.status_code}")
            print(f"响应: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"错误: {e}")

        # 2. 检查快照
        print("\n" + "=" * 60)
        print("检查可用快照")
        print("=" * 60)

        try:
            response = await client.get(
                f"{API_URL}/snapshots",
                headers=headers
            )
            print(f"状态码: {response.status_code}")
            print(f"响应: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"错误: {e}")

        # 3. 查看 OpenAPI 文档中的可用端点
        print("\n" + "=" * 60)
        print("查看 API 端点")
        print("=" * 60)

        try:
            response = await client.get(f"{API_URL}/openapi.json")
            openapi = response.json()

            print("可用端点:")
            for path in openapi.get("paths", {}).keys():
                print(f"  {path}")

            # 查看模板相关端点
            if "/templates" in openapi.get("paths", {}):
                print("\n模板端点详情:")
                template_path = openapi["paths"]["/templates"]
                print(json.dumps(template_path, indent=2))

        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(check_opensandbox_resources())