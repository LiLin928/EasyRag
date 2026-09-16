"""测试工作流调试功能"""
import asyncio
from app.core.engine.celery_client import enqueue_workflow_task

async def test_debug():
    workflow_id = "b9eeadc5-233f-420e-a238-723564077fac"
    inputs = {"query": "测试调试功能"}
    debug = True

    print(f"\n[测试] 触发工作流调试执行:")
    print(f"   Workflow ID: {workflow_id}")
    print(f"   Inputs: {inputs}")
    print(f"   Debug: {debug}")

    try:
        execution_id = await enqueue_workflow_task(workflow_id, inputs, "manual", None, debug=debug)
        print(f"\n[成功] 任务已提交:")
        print(f"   Execution ID: {execution_id}")
        print(f"\n请在 Celery worker 窗口查看日志")
        print(f"前端应该收到以下事件序列:")
        print(f"   1. execution_start")
        print(f"   2. execution_paused (第一个节点前)")
        print(f"   3. 等待用户点击 '继续'")
        print(f"   4. execution_resumed")
        print(f"   5. execution_paused (下一个节点前)")
        print(f"   6. ... 重复直到所有节点执行完成")
        print(f"   7. execution_complete")
    except Exception as e:
        print(f"\n[失败] 提交失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_debug())