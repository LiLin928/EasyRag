import os
import sys
import asyncio

import pytest

# Windows: asyncpg recommends SelectorEventLoop (ProactorEventLoop has fd/teardown issues)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 必填配置由 backend/.env 提供（SECRET_KEY / DATABASE_URL / INIT_ADMIN_PASSWORD）。
# 不在此 setdefault：pydantic 中 os.environ 优先级高于 env_file，setdefault 会覆盖 .env，
# 导致测试建的 admin 密码与 .env（真实部署）不一致。


@pytest.fixture(scope="function", autouse=True)
async def _dispose_engine():
    """Dispose the shared async engine after each test function.

    The shared module-level ``engine`` (app.db.session) binds pooled
    connections to the event loop that first uses them. pytest-asyncio gives
    each async test its own function-scoped loop, so a pool populated by one
    test leaks connections bound to that loop into the next test, raising
    ``RuntimeError: ... attached to a different loop``. Disposing per-function
    empties the pool so each test creates fresh connections on its own loop.
    """
    yield
    from app.db.session import engine
    try:
        await engine.dispose()
    except Exception:
        pass


# 注：不在此处加 session 级 admin bootstrap。admin 用户由 Task 10 在 easyrag_v2 持久化，
# 且 session 级 asyncio.run 会用独立 event loop 连 PG，导致共享 engine 绑定到 bootstrap loop，
# 与各测试的 function-scoped loop 冲突（"attached to a different loop"）。故省略。
