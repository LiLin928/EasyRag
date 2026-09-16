"""检查执行记录状态"""
import asyncio
from sqlalchemy import select, text
from app.db.session import async_session
from app.models.workflow import WorkflowExecution

async def check_execution():
    execution_id = "f73b3b8b-a927-42d3-a94c-98ffbb65c9c4"

    async with async_session() as s:
        # 查询执行记录
        result = await s.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        )
        exec_record = result.scalar_one_or_none()

        if exec_record:
            print(f"\n[OK] 执行记录存在:")
            print(f"   ID: {exec_record.id}")
            print(f"   状态: {exec_record.status}")
            print(f"   触发类型: {exec_record.trigger_type}")
            print(f"   开始时间: {exec_record.started_at}")
            print(f"   完成时间: {exec_record.completed_at}")
            print(f"   输入: {exec_record.inputs}")
            print(f"   输出: {exec_record.outputs}")
            print(f"   持续时间: {exec_record.duration_ms}ms")
            print(f"   版本: {exec_record.version}")

            if exec_record.status == "failed":
                print(f"\n[ERROR] 执行失败:")
                print(f"   错误信息: {exec_record.outputs}")
        else:
            print(f"\n[ERROR] 执行记录不存在: {execution_id}")

        # 查询最近的所有执行记录
        print(f"\n[INFO] 最近 5 条执行记录:")
        recent = await s.execute(
            select(WorkflowExecution)
            .order_by(WorkflowExecution.created_at.desc())
            .limit(5)
        )
        for i, exec in enumerate(recent.scalars().all(), 1):
            print(f"   {i}. {exec.id} - {exec.status} - {exec.started_at}")

if __name__ == "__main__":
    asyncio.run(check_execution())