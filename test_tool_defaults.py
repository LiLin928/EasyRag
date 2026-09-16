"""测试工具参数默认值"""
import asyncio
import sys
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from app.services.tool_service import execute_tool

async def test_tool_defaults():
    tool_id = "6b92349d-99a7-47f4-91d4-7006e37716b6"

    print("测试1：只传城市名，使用默认的 appid 和 units")
    result1 = await execute_tool(tool_id, {"q": "Beijing"})
    print(f"结果：{'成功' if result1['success'] else '失败'}")
    if result1['success']:
        print(f"温度：{result1['data']['main']['temp']}°C")
        print(f"天气：{result1['data']['weather'][0]['description']}")
    else:
        print(f"错误：{result1['error']}")
    print()

    print("测试2：只传城市名（中文）")
    result2 = await execute_tool(tool_id, {"q": "北京"})
    print(f"结果：{'成功' if result2['success'] else '失败'}")
    if result2['success']:
        print(f"温度：{result2['data']['main']['temp']}°C")
        print(f"天气：{result2['data']['weather'][0]['description']}")
    else:
        print(f"错误：{result2['error']}")
    print()

    print("测试3：传完整参数")
    result3 = await execute_tool(tool_id, {
        "q": "Shanghai",
        "appid": "1564bd59e86f981289a646fb2c421a63",
        "units": "metric"
    })
    print(f"结果：{'成功' if result3['success'] else '失败'}")
    if result3['success']:
        print(f"温度：{result3['data']['main']['temp']}°C")
        print(f"天气：{result3['data']['weather'][0]['description']}")
    else:
        print(f"错误：{result3['error']}")

if __name__ == "__main__":
    asyncio.run(test_tool_defaults())