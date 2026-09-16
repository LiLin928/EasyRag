import httpx
import asyncio

async def test():
    # 测试1: 直接用完整URL
    url1 = "https://api.openweathermap.org/data/2.5/weather?q=BeiJing&appid=1564bd59e86f981289a646fb2c421a63&units=metric"
    
    # 测试2: 模拟参数替换
    args = {
        "q": "BeiJing",
        "appid": "1564bd59e86f981289a646fb2c421a63",
        "units": "metric"
    }
    tpl = "https://api.openweathermap.org/data/2.5/weather?q={q}&appid={appid}&units={units}"
    url2 = tpl
    for k, v in args.items():
        url2 = url2.replace(f"{{{k}}}", str(v))
    
    print("测试1 URL:", url1)
    print("测试2 URL:", url2)
    print("URL相同?", url1 == url2)
    
    # 发送请求测试
    async with httpx.AsyncClient(timeout=30) as client:
        resp1 = await client.get(url1)
        print("\n测试1 响应:", resp1.status_code)
        if resp1.status_code == 200:
            print("成功！数据:", resp1.json())
        else:
            print("失败:", resp1.text[:200])
        
        resp2 = await client.get(url2)
        print("\n测试2 响应:", resp2.status_code)
        if resp2.status_code == 200:
            print("成功！数据:", resp2.json())
        else:
            print("失败:", resp2.text[:200])

asyncio.run(test())
