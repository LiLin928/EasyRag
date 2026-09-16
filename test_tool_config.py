"""测试工具配置的正确性"""
import httpx
import asyncio
import json

# 你的配置
TOOL_CONFIG = {
    "url": "https://api.openweathermap.org/data/2.5/weather?q={q}&appid={appid}&units={units}",
    "method": "GET",
    "headers": {}
}

# 测试参数
TEST_ARGS = {
    "q": "BeiJing",
    "appid": "1564bd59e86f981289a646fb2c421a63",
    "units": "metric"
}

def render_url(url: str, args: dict) -> str:
    """参数替换"""
    for k, v in args.items():
        url = url.replace(f"{{{k}}}", str(v))
    return url

async def test_tool():
    """测试工具"""
    url = render_url(TOOL_CONFIG["url"], TEST_ARGS)

    print("=" * 60)
    print("测试工具配置")
    print("=" * 60)
    print(f"\n原始URL: {TOOL_CONFIG['url']}")
    print(f"\n参数: {json.dumps(TEST_ARGS, indent=2)}")
    print(f"\n替换后URL: {url}")

    print("\n" + "=" * 60)
    print("发送请求...")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(url, headers=TOOL_CONFIG["headers"])

            print(f"\n状态码: {resp.status_code}")

            if resp.status_code == 200:
                data = resp.json()
                print(f"\n✅ 成功！返回数据:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print(f"\n❌ 失败！响应:")
                print(resp.text)

        except Exception as e:
            print(f"\n❌ 请求异常: {e}")

if __name__ == "__main__":
    asyncio.run(test_tool())