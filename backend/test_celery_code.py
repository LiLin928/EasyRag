"""
测试 Celery Worker 是否加载了新代码
"""
import sys

# 检查 pipeline.py 中的 _single_channel 方法
from app.core.retrieval.pipeline import RetrievalPipeline

# 获取 _single_channel 方法的源代码
import inspect
source = inspect.getsource(RetrievalPipeline._single_channel)

print("=" * 80)
print("检查 pipeline.py 中的 _single_channel 方法:")
print("=" * 80)
print()

# 检查是否包含 "rrf_score"
if '"rrf_score"' in source:
    print("[OK] 代码已修复：使用 'rrf_score' 字段")
else:
    print("[FAIL] 代码未修复：仍使用旧字段名")

print()
print("=" * 80)
print("源代码片段:")
print("=" * 80)
print(source)