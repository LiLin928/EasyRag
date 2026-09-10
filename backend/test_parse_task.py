"""直接测试解析任务"""
from dotenv import load_dotenv
load_dotenv()

import sys
import logging
sys.path.insert(0, '.')

from app.worker.tasks.parse_tasks import parse_document

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

# 创建模拟的 self 对象
class MockRequest:
    retries = 0
    max_retries = 3

class MockSelf:
    request = MockRequest()

    def retry(self, exc=None, countdown=None):
        print(f'Retry called: exc={exc}, countdown={countdown}')
        if exc:
            raise exc
        raise Exception('Retry')

print('Starting task execution test...')
print('This will call parse_document with test parameters')
print()

try:
    # 调用任务函数 - 不传递 self（Celery 会自动注入）
    result = parse_document.run(
        'test-doc-id',
        'test-key',
        'test-kb-id'
    )
    print(f'\nTask completed successfully!')
    print(f'Result: {result}')
except Exception as e:
    print(f'\nTask failed!')
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()