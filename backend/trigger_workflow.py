"""手动触发工作流执行"""
import asyncio
from app.core.engine.celery_client import enqueue_workflow_task

async def test():
    workflow_id = "b9eeadc5-233f-420e-a238-723564077fac"
    inputs = {"query": "你是谁"}
    debug = True

    print(f"\n[INFO] 触发工作流执行:")
    print(f"   Workflow ID: {workflow_id}")
    print(f"   Inputs: {inputs}")
    print(f"   Debug: {debug}")

    try:
        execution_id = await enqueue_workflow_task(workflow_id, inputs, "manual", None, debug=debug)
        print(f"\n[OK] 任务已提交:")
        print(f"   Execution ID: {execution_id}")
        print(f"\n请在 Celery worker 窗口查看日志")
    except Exception as e:
        print(f"\n[ERROR] 提交失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())