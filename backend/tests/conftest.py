import os
import sys
import asyncio

import pytest

# Windows: asyncpg recommends SelectorEventLoop (ProactorEventLoop has fd/teardown issues)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Fallbacks for required settings if .env absent during collection.
# DATABASE_URL is provided by backend/.env (VM easyrag_v2); do NOT override here.
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "pw12345")


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
