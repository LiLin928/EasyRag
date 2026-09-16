"""测试 Redis Stream 连接和内容"""
import redis
import json
import sys
import io

# 设置 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 从 .env 读取配置
redis_url = "redis://:easyrag2026@192.168.137.13:6379"

try:
    r = redis.from_url(redis_url)

    # 测试连接
    print("[OK] Redis 连接成功")
    print(f"   Ping: {r.ping()}")

    # 检查最近的 execution ID
    execution_id = "f73b3b8b-a927-42d3-a94c-98ffbb65c9c4"
    stream_key = f"workflow:{execution_id}"

    print(f"\n[INFO] 检查 Stream: {stream_key}")

    # 获取 Stream 信息
    try:
        info = r.xinfo_stream(stream_key)
        print(f"   Stream 存在！")
        print(f"   长度: {info['length']}")
        print(f"   最后消息 ID: {info['last-generated-id']}")

        # 读取消息
        messages = r.xrange(stream_key, count=10)
        print(f"\n[INFO] 最近 {len(messages)} 条消息:")
        for msg_id, data in messages:
            event_type = data.get(b'type', b'unknown').decode()
            payload = json.loads(data.get(b'payload', b'{}').decode())
            print(f"   [{msg_id.decode()}] {event_type}: {json.dumps(payload, ensure_ascii=False)[:100]}")

    except redis.exceptions.ResponseError as e:
        if "no such key" in str(e).lower():
            print(f"   [ERROR] Stream 不存在！")
            print(f"   这说明任务没有推送任何事件到 Redis Stream")
        else:
            raise

    # 列出所有 workflow: streams
    print("\n[INFO] 所有 workflow: streams:")
    all_keys = r.keys("workflow:*")
    if all_keys:
        for key in all_keys[:10]:  # 只显示前10个
            key_str = key.decode()
            try:
                info = r.xinfo_stream(key)
                print(f"   {key_str}: {info['length']} 条消息")
            except:
                print(f"   {key_str}: 无法读取")
    else:
        print("   没有找到任何 workflow: stream")

except Exception as e:
    print(f"[ERROR] 错误: {e}")
    import traceback
    traceback.print_exc()