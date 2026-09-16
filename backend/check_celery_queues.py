"""检查 Redis 队列中的任务"""
import redis

redis_url = "redis://:easyrag2026@192.168.137.13:6379"

r = redis.from_url(redis_url)

print("\n[INFO] 检查 Celery 队列:")
for queue_name in ["high", "default", "low", "parse", "workflow", "agent"]:
    # Celery 使用 celery 队列前缀
    key = f"celery:{queue_name}"
    length = r.llen(key)
    print(f"   {key}: {length} 个任务")

    if length > 0:
        # 查看队列中的任务
        tasks = r.lrange(key, 0, 5)
        for i, task in enumerate(tasks):
            print(f"      Task {i+1}: {task[:100]}")

print("\n[INFO] 检查 Celery 结果后端:")
# 检查任务结果
execution_id = "f73b3b8b-a927-42d3-a94c-98ffbb65c9c4"
result_key = f"celery-task-meta-{execution_id}"
if r.exists(result_key):
    print(f"   {result_key}: 存在")
    result = r.get(result_key)
    print(f"   内容: {result[:200]}")
else:
    print(f"   {result_key}: 不存在")

# 检查所有 celery-task-meta-* 键
print("\n[INFO] 所有任务结果:")
result_keys = r.keys("celery-task-meta-*")
if result_keys:
    for key in result_keys[:10]:
        result = r.get(key)
        print(f"   {key.decode()}: {result[:100] if result else 'None'}")
else:
    print("   没有找到任务结果")