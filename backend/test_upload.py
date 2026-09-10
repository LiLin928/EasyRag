"""测试文档上传功能"""
from dotenv import load_dotenv
load_dotenv()

import asyncio
from app.db.session import async_session
from app.models.knowledge_base import KnowledgeBase
from app.models.document import Document, ParseTask
from app.providers.storage.factory import get_storage
from app.core.celery_app import celery_app
from sqlalchemy import select


async def test_upload():
    """测试上传流程"""
    try:
        # 模拟上传参数
        kb_id = "1bb352aa-e600-42ce-ad80-dcc876634e10"
        user_id = "0102ea2f-16cb-4029-b863-3807c213f148"
        filename = "test.txt"
        file_data = b"Test document content"
        ext = "txt"

        # 1. 创建数据库记录
        async with async_session() as session:
            kb = (
                await session.execute(
                    select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
                )
            ).scalar_one_or_none()
            if not kb:
                print("知识库不存在")
                return
            print(f"知识库: {kb.name}")

            document = Document(
                kb_id=kb.id,
                user_id=user_id,
                name=filename,
                ext=ext,
                size=len(file_data),
                mode="fast",
                status="pending",
                file_key="",
            )
            session.add(document)
            await session.flush()
            document.file_key = f"{kb.id}/{document.id}/{filename}"
            task = ParseTask(doc_id=document.id, kb_id=kb_id, status="pending")
            session.add(task)
            await session.commit()
            await session.refresh(document)
            await session.refresh(task)

            doc_id = str(document.id)
            key = document.file_key
            task_id = str(task.id)
            print(f"文档ID: {doc_id}")
            print(f"文件Key: {key}")
            print(f"任务ID: {task_id}")

        # 2. 上传文件
        storage = get_storage()
        await storage.put(key, file_data)
        print("文件上传成功")

        # 3. 提交 Celery 任务
        print("提交 Celery 任务...")
        result = celery_app.send_task(
            "parse_document",
            args=[doc_id, key, kb_id],
            queue="parse",
            task_id=task_id,
        )
        print(f"任务已提交: result.id={result.id}")
        print("上传流程完成！")
        print(f"返回: task_id={task_id}, doc_id={doc_id}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_upload())