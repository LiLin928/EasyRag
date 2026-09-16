"""读取任务结果详情"""
import redis
import json

redis_url = "redis://:easyrag2026@192.168.137.13:6379"

r = redis.from_url(redis_url)

execution_id = "f73b3b8b-a927-42d3-a94c-98ffbb65c9c4"
result_key = f"celery-task-meta-{execution_id}"

result = r.get(result_key)
if result:
    print(f"\n[INFO] 任务结果内容:")
    try:
        data = json.loads(result)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except:
        print(result)
else:
    print(f"\n[ERROR] 无法读取任务结果")

# 检查最近的几个任务结果
print(f"\n[INFO] 最近的 10 个任务结果:")
result_keys = r.keys("celery-task-meta-*")
for key in result_keys[-10:]:
    result = r.get(key)
    if result:
        try:
            data = json.loads(result)
            status = data.get("status", "UNKNOWN")
            print(f"   {key.decode()}: {status}")
        except:
            print(f"   {key.decode()}: 无法解析")