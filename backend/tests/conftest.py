"""测试配置文件。

提供共享的 pytest fixture，包括测试客户端、模拟用户、认证头等。
"""
import asyncio
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from app.main import app
from app.models.user import User
from app.models.scene import Scene
from app.models.base import Base
from app.config import settings

# Windows 平台需要使用 SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
async def session():
    """创建数据库会话用于集成测试。

    每个测试函数获取独立的会话，测试结束后回滚以保持数据库清洁。
    """
    # 使用应用的数据库配置创建测试引擎
    engine = create_async_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=10,
        echo=False
    )

    # 创建会话工厂
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # 创建会话（不使用嵌套事务）
    async with async_session_maker() as s:
        yield s

    # 清理引擎
    await engine.dispose()


@pytest.fixture
async def client():
    """创建异步测试客户端。"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def mock_user():
    """创建模拟用户。

    返回一个模拟的用户对象，用于测试认证。
    """
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.username = "testuser"
    user.display_name = "Test User"
    user.email = "test@example.com"
    user.role = "user"
    user.is_active = True
    return user


@pytest.fixture
def mock_scenes():
    """创建模拟场景列表。

    返回模拟的场景对象列表。
    """
    scenes = []
    for i, (code, name, desc) in enumerate([
        ("general", "通用问答", "适用于一般性问题和答案"),
        ("bidding", "招投标分析", "适用于招投标文档分析"),
        ("contract", "合同审查", "适用于合同条款审查"),
        ("technical", "技术文档", "适用于技术文档解析"),
        ("legal", "法律条文", "适用于法律条文检索"),
    ]):
        scene = MagicMock(spec=Scene)
        scene.code = code
        scene.name = name
        scene.description = desc
        scene.id = uuid.uuid4()
        scene.created_at = None
        scenes.append(scene)
    return scenes


@pytest.fixture
async def auth_headers_with_mocks(client: AsyncClient, mock_user: User, mock_scenes: list):
    """创建认证头和模拟数据。

    通过覆盖依赖和模拟数据库查询来避免真实的数据库连接。
    """
    from app.api.deps import get_current_user
    from app.db.session import async_session

    # 创建模拟的数据库会话
    mock_session = AsyncMock(spec=AsyncSession)

    # 模拟场景查询结果
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_scenes
    mock_session.execute.return_value = mock_result

    # 模拟用户查询结果
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = mock_user

    # 创建模拟的 get_current_user 函数
    async def mock_get_current_user():
        return mock_user

    # 创建模拟的 async_session 上下文管理器
    class MockAsyncSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            pass

    # 覆盖依赖
    app.dependency_overrides[get_current_user] = mock_get_current_user

    # 使用 patch 来替换 async_session
    with patch('app.api.v2.scenes.async_session', return_value=MockAsyncSessionContext()):
        from app.security.jwt import create_access_token
        token = create_access_token(mock_user.id)
        yield {"Authorization": f"Bearer {token}"}

    # 清理依赖覆盖
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(client: AsyncClient, mock_user: User):
    """创建认证头（简化版本）。

    通过覆盖 get_current_user 依赖来模拟认证，避免数据库连接。
    注意：这个 fixture 不模拟数据库查询，需要配合其他 mock 使用。
    """
    from app.api.deps import get_current_user
    from app.security.jwt import create_access_token

    # 创建一个模拟的 get_current_user 函数
    async def mock_get_current_user():
        return mock_user

    # 覆盖依赖
    app.dependency_overrides[get_current_user] = mock_get_current_user

    # 创建一个有效的 token
    token = create_access_token(mock_user.id)

    yield {"Authorization": f"Bearer {token}"}

    # 清理依赖覆盖
    app.dependency_overrides.clear()