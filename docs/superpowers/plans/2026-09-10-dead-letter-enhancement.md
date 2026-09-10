# 死信队列完善实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完善死信队列功能，添加专用数据库表、手动重试逻辑和统计告警机制

**Architecture:** 基于现有 Celery 死信信号处理，添加 PostgreSQL 持久化、Redis Streams 告警和手动重试 API

**Tech Stack:** PostgreSQL, Celery, Redis Streams, FastAPI, SQLAlchemy

**关联文档:**
- 当前实现: `backend/app/worker/tasks/dead_letter.py`
- 架构文档: `docs/backend-architecture-v2.md`

---

## 概览

**当前状态:**
- ✅ Celery task_failure 信号处理已实现
- ✅ 失败任务日志记录
- ✅ Redis Streams 事件发布
- ❌ 专用数据库表（TODO 占位）
- ❌ 手动重试逻辑（TODO 占位）
- ❌ 统计和告警机制（TODO 占位）

**目标:**
- 创建 dead_letter_tasks 表 + ORM 模型
- 实现手动重试 API
- 实现统计查询 API
- 实现定时告警任务

**预计任务数:** 4
**预计时间:** 1天

---

## Task 1: 创建死信队列数据库表和 ORM

**优先级:** P0
**预计时间:** 1小时

### Step 1.1: 定义死信任务 ORM 模型

- [ ] **创建死信任务 ORM**

Create: `backend/app/models/dead_letter.py`

```python
"""死信任务 ORM 模型。"""
from sqlalchemy import Column, String, Text, Integer, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import uuid
from datetime import datetime


class DeadLetterTaskModel(Base):
    """死信任务持久化模型。

    存储超过最大重试次数的失败任务，支持手动重试和统计分析。
    """
    __tablename__ = "dead_letter_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(100), unique=True, nullable=False, comment="Celery 任务 ID")
    task_name = Column(String(255), nullable=False, comment="任务名称")
    args = Column(Text, comment="任务参数（JSON）")
    kwargs = Column(Text, comment="任务关键字参数（JSON）")
    exception = Column(Text, nullable=False, comment="异常信息")
    traceback = Column(Text, comment="堆栈跟踪")
    retry_count = Column(Integer, nullable=False, default=0, comment="重试次数")
    max_retries = Column(Integer, nullable=False, default=3, comment="最大重试次数")
    status = Column(String(20), default="pending", comment="pending/retried/ignored")
    created_at = Column(DateTime(timezone=True), server_default="now()", comment="创建时间")
    retried_at = Column(DateTime(timezone=True), comment="重试时间")
    retried_by = Column(UUID(as_uuid=True), comment="重试操作用户")

    def __repr__(self):
        return f"<DeadLetterTask {self.task_name}[{self.task_id}]>"
```

### Step 1.2: 创建迁移文件

- [ ] **生成并应用数据库迁移**

```bash
cd backend && uv run alembic revision --autogenerate -m "add dead_letter_tasks table"
cd backend && uv run alembic upgrade head
```

Expected: 迁移成功，表创建完成

### Step 1.3: 更新死信队列处理器

- [ ] **修改 DeadLetterQueue 添加数据库持久化**

Modify: `backend/app/worker/tasks/dead_letter.py:84-92`

将 TODO 部分替换为实际实现：

```python
# 1. 记录到数据库
try:
    async with async_session() as session:
        from app.models.dead_letter import DeadLetterTaskModel

        db_task = DeadLetterTaskModel(
            task_id=task_id,
            task_name=task_name,
            args=json.dumps(args, default=str),
            kwargs=json.dumps(kwargs, default=str),
            exception=str(exception),
            traceback=traceback_str,
            retry_count=retry_count,
            max_retries=max_retries,
            status="pending",
        )
        session.add(db_task)
        await session.commit()
        logger.info(f"DLQ task saved to DB: {task_id}")
except Exception as e:
    logger.error(f"Failed to save DLQ task to DB: {e}")
```

### Step 1.4: 提交代码

```bash
git add backend/app/models/dead_letter.py backend/app/worker/tasks/dead_letter.py backend/alembic/versions/*.py
git commit -m "feat(models): add dead_letter_tasks table and ORM"
```

---

## Task 2: 实现手动重试逻辑

**优先级:** P0
**预计时间:** 1.5小时

### Step 2.1: 实现重试逻辑

- [ ] **完善 DeadLetterQueue.retry_dlq_task 方法**

Modify: `backend/app/worker/tasks/dead_letter.py:113-117`

```python
@staticmethod
async def retry_dlq_task(task_id: str, user_id: str = None) -> bool:
    """手动重试死信队列中的任务。

    Args:
        task_id: Celery 任务 ID
        user_id: 操作用户 ID

    Returns:
        是否重试成功
    """
    from app.core.celery_app import celery_app

    async with async_session() as session:
        # 查询死信任务
        result = await session.execute(
            select(DeadLetterTaskModel).where(DeadLetterTaskModel.task_id == task_id)
        )
        dl_task = result.scalar_one_or_none()

        if not dl_task:
            logger.warning(f"DLQ task not found: {task_id}")
            return False

        if dl_task.status != "pending":
            logger.warning(f"DLQ task already processed: {task_id}, status={dl_task.status}")
            return False

        try:
            # 解析参数
            args = json.loads(dl_task.args) if dl_task.args else ()
            kwargs = json.loads(dl_task.kwargs) if dl_task.kwargs else {}

            # 重新提交任务
            celery_app.send_task(
                dl_task.task_name,
                args=args,
                kwargs=kwargs,
                queue=_get_queue_for_task(dl_task.task_name),
            )

            # 更新状态
            dl_task.status = "retried"
            dl_task.retried_at = datetime.utcnow()
            if user_id:
                dl_task.retried_by = uuid.UUID(user_id)

            await session.commit()
            logger.info(f"DLQ task retried: {task_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to retry DLQ task {task_id}: {e}")
            return False


def _get_queue_for_task(task_name: str) -> str:
    """根据任务名称确定队列。

    Args:
        task_name: 任务名称

    Returns:
        队列名称
    """
    if task_name.startswith("parse"):
        return "parse"
    elif task_name.startswith("workflow"):
        return "workflow"
    elif task_name.startswith("agent"):
        return "agent"
    return "default"
```

### Step 2.2: 创建死信队列 API

- [ ] **创建死信队列管理路由**

Create: `backend/app/api/v2/dead_letter.py`

```python
"""死信队列管理 API。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.dead_letter import DeadLetterTaskModel
from app.models.user import User
from app.worker.tasks.dead_letter import DeadLetterQueue
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


router = APIRouter(prefix="/dead-letter", tags=["dead-letter"])


class DeadLetterTaskOut(BaseModel):
    """死信任务输出。"""
    id: str
    task_id: str
    task_name: str
    exception: str
    traceback: Optional[str]
    retry_count: int
    max_retries: int
    status: str
    created_at: datetime
    retried_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("/tasks")
async def list_dlq_tasks(
    status: str = None,
    limit: int = 50,
    offset: int = 0,
    me: User = Depends(get_current_user)
):
    """列出死信任务。

    Args:
        status: 状态过滤（pending/retried/ignored）
        limit: 返回数量
        offset: 偏移量
    """
    async with async_session() as session:
        query = select(DeadLetterTaskModel)

        if status:
            query = query.where(DeadLetterTaskModel.status == status)

        query = query.order_by(DeadLetterTaskModel.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await session.execute(query)
        tasks = result.scalars().all()

        return ok([
            DeadLetterTaskOut(
                id=str(t.id),
                task_id=t.task_id,
                task_name=t.task_name,
                exception=t.exception,
                traceback=t.traceback,
                retry_count=t.retry_count,
                max_retries=t.max_retries,
                status=t.status,
                created_at=t.created_at,
                retried_at=t.retried_at,
            ).model_dump()
            for t in tasks
        ])


@router.post("/tasks/{task_id}/retry")
async def retry_dlq_task(
    task_id: str,
    me: User = Depends(get_current_user)
):
    """重试死信任务。

    Args:
        task_id: Celery 任务 ID
    """
    success = await DeadLetterQueue.retry_dlq_task(task_id, str(me.id))

    if not success:
        raise HTTPException(status_code=400, detail="重试失败")

    return ok({"message": "任务已重新提交"})


@router.post("/tasks/{task_id}/ignore")
async def ignore_dlq_task(
    task_id: str,
    me: User = Depends(get_current_user)
):
    """忽略死信任务（标记为已处理）。

    Args:
        task_id: Celery 任务 ID
    """
    async with async_session() as session:
        result = await session.execute(
            select(DeadLetterTaskModel).where(DeadLetterTaskModel.task_id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        task.status = "ignored"
        await session.commit()

    return ok({"message": "任务已忽略"})


@router.get("/stats")
async def get_dlq_stats(me: User = Depends(get_current_user)):
    """获取死信队列统计。"""
    async with async_session() as session:
        # 总数
        total_result = await session.execute(
            select(func.count(DeadLetterTaskModel.id))
        )
        total = total_result.scalar()

        # 按状态统计
        status_result = await session.execute(
            select(
                DeadLetterTaskModel.status,
                func.count(DeadLetterTaskModel.id)
            )
            .group_by(DeadLetterTaskModel.status)
        )
        by_status = dict(status_result.all())

        # 按任务类型统计
        type_result = await session.execute(
            select(
                DeadLetterTaskModel.task_name,
                func.count(DeadLetterTaskModel.id)
            )
            .group_by(DeadLetterTaskModel.task_name)
        )
        by_type = dict(type_result.all())

        # 最近 24 小时
        from datetime import timedelta
        recent_result = await session.execute(
            select(func.count(DeadLetterTaskModel.id))
            .where(DeadLetterTaskModel.created_at >= datetime.utcnow() - timedelta(hours=24))
        )
        last_24h = recent_result.scalar()

    return ok({
        "total": total,
        "by_status": by_status,
        "by_type": by_type,
        "last_24h": last_24h,
    })
```

### Step 2.3: 注册路由

- [ ] **在主路由中注册死信队列路由**

Modify: `backend/app/api/v2/__init__.py`

添加导入和注册：

```python
from app.api.v2.dead_letter import router as dead_letter_router
# ... 其他导入 ...

api_router.include_router(dead_letter_router, prefix="/dead-letter", tags=["dead-letter"])
```

### Step 2.4: 提交代码

```bash
git add backend/app/api/v2/dead_letter.py backend/app/api/v2/__init__.py backend/app/worker/tasks/dead_letter.py
git commit -m "feat(api): add dead letter queue management API and retry logic"
```

---

## Task 3: 实现定时告警

**优先级:** P0
**预计时间:** 1小时

### Step 3.1: 完善监控任务

- [ ] **实现告警通知逻辑**

Modify: `backend/app/worker/tasks/dead_letter.py:156-178`

将 TODO 部分替换为实际实现：

```python
@shared_task(name="dlq.monitor")
def monitor_dead_letter_queue():
    """定时监控死信队列。

    每小时检查一次死信队列，发送告警。
    """
    import asyncio

    async def _check():
        stats = await DeadLetterQueue.get_dlq_stats()

        # 如果有失败任务，发送告警
        if stats["total_failed"] > 0:
            logger.warning(
                f"DLQ Alert: {stats['total_failed']} failed tasks in queue, "
                f"last_24h={stats['last_24h']}"
            )

            # 发送告警（邮件/Slack/钉钉等）
            await _send_alert(
                title="EasyRAG 死信队列告警",
                message=f"当前有 {stats['total_failed']} 个失败任务待处理，"
                        f"最近 24 小时新增 {stats['last_24h']} 个。",
                details=stats
            )

    asyncio.run(_check())


async def _send_alert(title: str, message: str, details: dict):
    """发送告警通知。

    支持多种告警渠道：邮件、Slack、钉钉等。

    Args:
        title: 告警标题
        message: 告警消息
        details: 详细信息
    """
    from app.config import settings

    # 邮件告警
    alert_email = getattr(settings, "alert_email", None)
    if alert_email:
        try:
            # TODO: 集成邮件发送服务
            # await send_email(to=alert_email, subject=title, body=message)
            logger.info(f"Alert email would be sent to {alert_email}: {message}")
        except Exception as e:
            logger.error(f"Failed to send alert email: {e}")

    # Slack Webhook
    slack_webhook = getattr(settings, "slack_webhook_url", None)
    if slack_webhook:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.post(
                    slack_webhook,
                    json={
                        "text": title,
                        "attachments": [
                            {
                                "text": message,
                                "fields": [
                                    {"title": k, "value": str(v), "short": True}
                                    for k, v in details.items()
                                ]
                            }
                        ]
                    }
                )
            logger.info("Alert sent to Slack")
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

    # 钉钉 Webhook
    dingtalk_webhook = getattr(settings, "dingtalk_webhook_url", None)
    if dingtalk_webhook:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.post(
                    dingtalk_webhook,
                    json={
                        "msgtype": "text",
                        "text": {"content": f"{title}\n\n{message}"}
                    }
                )
            logger.info("Alert sent to DingTalk")
        except Exception as e:
            logger.error(f"Failed to send DingTalk alert: {e}")
```

### Step 3.2: 完善清理任务

- [ ] **实现清理逻辑**

Modify: `backend/app/worker/tasks/dead_letter.py:183-206`

```python
@shared_task(name="dlq.cleanup")
def cleanup_old_dlq_tasks(days: int = 30):
    """清理过期的死信队列任务。

    Args:
        days: 保留天数，默认 30 天
    """
    import asyncio
    from datetime import timedelta

    async def _cleanup():
        cutoff = datetime.utcnow() - timedelta(days=days)
        logger.info(f"Cleaning up DLQ tasks older than {cutoff}")

        async with async_session() as session:
            from sqlalchemy import delete

            # 只删除已处理的任务（retried/ignored）
            result = await session.execute(
                delete(DeadLetterTaskModel)
                .where(DeadLetterTaskModel.created_at < cutoff)
                .where(DeadLetterTaskModel.status.in_(["retried", "ignored"]))
            )
            deleted = result.rowcount
            await session.commit()

            logger.info(f"Deleted {deleted} old DLQ tasks")

    asyncio.run(_cleanup())
```

### Step 3.3: 更新统计方法

- [ ] **实现真实的统计查询**

Modify: `backend/app/worker/tasks/dead_letter.py:120-128`

```python
@staticmethod
async def get_dlq_stats() -> Dict[str, Any]:
    """获取死信队列统计。"""
    async with async_session() as session:
        # 总数
        total_result = await session.execute(
            select(func.count(DeadLetterTaskModel.id))
            .where(DeadLetterTaskModel.status == "pending")
        )
        total_failed = total_result.scalar()

        # 按任务类型统计
        type_result = await session.execute(
            select(
                DeadLetterTaskModel.task_name,
                func.count(DeadLetterTaskModel.id)
            )
            .where(DeadLetterTaskModel.status == "pending")
            .group_by(DeadLetterTaskModel.task_name)
        )
        by_task_type = dict(type_result.all())

        # 最近 24 小时
        recent_result = await session.execute(
            select(func.count(DeadLetterTaskModel.id))
            .where(DeadLetterTaskModel.status == "pending")
            .where(DeadLetterTaskModel.created_at >= datetime.utcnow() - timedelta(hours=24))
        )
        last_24h = recent_result.scalar()

    return {
        "total_failed": total_failed,
        "by_task_type": by_task_type,
        "last_24h": last_24h,
    }
```

### Step 3.4: 配置定时任务

- [ ] **添加 Celery Beat 配置**

Modify: `backend/app/core/celery_app.py`

添加定时任务配置：

```python
from celery.schedules import crontab

# Celery Beat 定时任务
celery_app.conf.beat_schedule = {
    "monitor-dlq": {
        "task": "dlq.monitor",
        "schedule": crontab(minute=0),  # 每小时执行
    },
    "cleanup-dlq": {
        "task": "dlq.cleanup",
        "schedule": crontab(hour=2, minute=0),  # 每天凌晨 2 点执行
        "args": (30,),  # 保留 30 天
    },
}
```

### Step 3.5: 添加配置项

- [ ] **添加告警配置项**

Modify: `backend/app/config.py`

```python
class Settings(BaseSettings):
    # ... 现有配置 ...

    # 告警配置
    alert_email: str | None = None
    slack_webhook_url: str | None = None
    dingtalk_webhook_url: str | None = None
```

### Step 3.6: 提交代码

```bash
git add backend/app/worker/tasks/dead_letter.py backend/app/core/celery_app.py backend/app/config.py
git commit -m "feat(worker): add DLQ monitoring and alerting"
```

---

## Task 4: 测试和文档

**优先级:** P0
**预计时间:** 1小时

### Step 4.1: 编写单元测试

- [ ] **创建死信队列测试**

Create: `backend/tests/test_dead_letter.py`

```python
"""死信队列功能测试。"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.models.dead_letter import DeadLetterTaskModel
from app.worker.tasks.dead_letter import DeadLetterQueue


@pytest.mark.asyncio
async def test_add_to_dlq(async_session):
    """测试添加任务到死信队列。"""
    await DeadLetterQueue.add_to_dlq(
        task_id="test-123",
        task_name="parse_document",
        args=("doc-1",),
        kwargs={},
        exception=ValueError("test error"),
        traceback_str="test traceback",
        retry_count=3,
        max_retries=3
    )

    # 验证数据库记录
    from sqlalchemy import select
    result = await async_session.execute(
        select(DeadLetterTaskModel).where(DeadLetterTaskModel.task_id == "test-123")
    )
    task = result.scalar_one_or_none()

    assert task is not None
    assert task.task_name == "parse_document"
    assert task.status == "pending"
    assert task.retry_count == 3


@pytest.mark.asyncio
async def test_retry_dlq_task(async_session):
    """测试手动重试死信任务。"""
    # 创建测试任务
    task = DeadLetterTaskModel(
        task_id="test-456",
        task_name="parse_document",
        args='["doc-2"]',
        kwargs="{}",
        exception="test error",
        traceback="",
        retry_count=3,
        max_retries=3,
        status="pending"
    )
    async_session.add(task)
    await async_session.commit()

    # Mock Celery
    with patch("app.worker.tasks.dead_letter.celery_app") as mock_celery:
        mock_celery.send_task = AsyncMock()

        # 重试任务
        success = await DeadLetterQueue.retry_dlq_task("test-456", "user-1")

        assert success is True
        mock_celery.send_task.assert_called_once()

        # 验证状态更新
        await async_session.refresh(task)
        assert task.status == "retried"
        assert task.retried_at is not None


@pytest.mark.asyncio
async def test_get_dlq_stats(async_session):
    """测试获取死信队列统计。"""
    # 创建测试数据
    for i in range(3):
        task = DeadLetterTaskModel(
            task_id=f"test-{i}",
            task_name="parse_document",
            args="[]",
            kwargs="{}",
            exception=f"error {i}",
            traceback="",
            retry_count=3,
            max_retries=3,
            status="pending",
            created_at=datetime.utcnow() - timedelta(hours=i)
        )
        async_session.add(task)

    await async_session.commit()

    # 获取统计
    stats = await DeadLetterQueue.get_dlq_stats()

    assert stats["total_failed"] == 3
    assert "parse_document" in stats["by_task_type"]
    assert stats["last_24h"] == 3


def test_dlq_api_list(client, auth_headers):
    """测试死信队列 API 列表接口。"""
    response = client.get("/api/v2/dead-letter/tasks", headers=auth_headers)
    assert response.status_code == 200
    assert "data" in response.json()


def test_dlq_api_retry(client, auth_headers):
    """测试死信队列 API 重试接口。"""
    response = client.post(
        "/api/v2/dead-letter/tasks/test-123/retry",
        headers=auth_headers
    )
    # 可能失败（任务不存在），但接口正常
    assert response.status_code in [200, 400]


def test_dlq_api_stats(client, auth_headers):
    """测试死信队列 API 统计接口。"""
    response = client.get("/api/v2/dead-letter/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert "total" in data
    assert "by_status" in data
```

### Step 4.2: 运行测试

```bash
cd backend && uv run pytest tests/test_dead_letter.py -v
```

Expected: 所有测试通过

### Step 4.3: 更新架构文档

- [ ] **更新架构文档中的死信队列部分**

Modify: `docs/backend-architecture-v2.md`

在"错误处理与重试"部分添加死信队列说明：

```markdown
## 死信队列管理

### 数据库表

```sql
CREATE TABLE dead_letter_tasks (
    id UUID PRIMARY KEY,
    task_id VARCHAR(100) UNIQUE NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    exception TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### API 接口

- `GET /api/v2/dead-letter/tasks` - 列出死信任务
- `POST /api/v2/dead-letter/tasks/{task_id}/retry` - 重试任务
- `POST /api/v2/dead-letter/tasks/{task_id}/ignore` - 忽略任务
- `GET /api/v2/dead-letter/stats` - 获取统计

### 告警机制

- 每小时自动检查死信队列
- 支持邮件/Slack/钉钉告警
- 配置项：`alert_email`, `slack_webhook_url`, `dingtalk_webhook_url`
```

### Step 4.4: 提交代码

```bash
git add tests/test_dead_letter.py docs/backend-architecture-v2.md
git commit -m "test: add DLQ tests and update documentation"
```

---

## 验收标准

- [ ] 死信任务数据库表创建完成
- [ ] 失败任务自动持久化到数据库
- [ ] 手动重试 API 可用
- [ ] 统计查询 API 可用
- [ ] 定时告警任务配置完成
- [ ] 所有测试通过
- [ ] 文档更新完成

---

## 风险和依赖

**风险:**
1. 告警发送失败：需要考虑重试机制
2. 数据库连接池：大量失败任务可能耗尽连接

**依赖:**
- Celery 配置正确
- PostgreSQL 连接正常
- Redis Streams 正常运行

---

**计划保存至:** `docs/superpowers/plans/2026-09-10-dead-letter-enhancement.md`