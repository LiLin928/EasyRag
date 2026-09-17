"""查看 ResourceLimits schema"""
import httpx
import json

API_URL = "http://192.168.137.13:8090"


async def get_resource_limits_schema():
    """获取 ResourceLimits schema"""

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{API_URL}/openapi.json")
        openapi = response.json()

        schemas = openapi.get("components", {}).get("schemas", {})

        # 查看 ResourceLimits
        if "ResourceLimits" in schemas:
            print("=" * 60)
            print("ResourceLimits 定义")
            print("=" * 60)
            print(json.dumps(schemas["ResourceLimits"], indent=2))

        # 查看 ImageSpec
        if "ImageSpec" in schemas:
            print("\n" + "=" * 60)
            print("ImageSpec 定义")
            print("=" * 60)
            print(json.dumps(schemas["ImageSpec"], indent=2))


if __name__ == "__main__":
    import asyncio
    asyncio.run(get_resource_limits_schema())