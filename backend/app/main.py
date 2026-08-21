"""FastAPI 应用入口模块。

负责创建应用、注册中间件与路由、配置异常处理器与生命周期。
"""
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.exceptions import BizException
from app.security.init_admin import ensure_admin
from app.api.v2 import assets, auth, elements_list, health, knowledge, metadata, parse_tasks, retrieval, retrieval_settings, settings as settings_api, tree
from app.logging import setup_logging, new_request_id

setup_logging()
_log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时确保初始管理员存在、seed 内置数据、配置 tracing。"""
    from app.core.seed import run_seed
    from app.providers.trace.factory import configure_tracing
    await ensure_admin()
    await run_seed()
    configure_tracing()
    yield


app = FastAPI(title="EasyRAG API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """请求 id 中间件。

    从 ``X-Request-ID`` 头读取或生成新的请求 id，绑定到 structlog contextvars，
    并在响应头回写该 id，便于全链路追踪。
    """
    rid = request.headers.get("X-Request-ID") or new_request_id()
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=rid, path=request.url.path)
    _log.info("request.start")
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    _log.info("request.end", status_code=response.status_code)
    return response


@app.exception_handler(BizException)
async def biz_exception_handler(request: Request, exc: BizException):
    """全局业务异常处理器。

    将 BizException 转换为 HTTP 200 + 业务错误码的 ApiResponse 结构。
    """
    return JSONResponse(status_code=200, content={"code": exc.code, "message": exc.message, "data": None})


app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(assets.router, prefix=settings.api_prefix)
app.include_router(knowledge.router, prefix=settings.api_prefix)
app.include_router(metadata.router, prefix=settings.api_prefix)
app.include_router(retrieval_settings.router, prefix=settings.api_prefix)
app.include_router(retrieval.router, prefix=settings.api_prefix)
app.include_router(parse_tasks.router, prefix=settings.api_prefix)
app.include_router(settings_api.router, prefix=settings.api_prefix)
app.include_router(tree.router, prefix=settings.api_prefix)
app.include_router(elements_list.router, prefix=settings.api_prefix)
app.include_router(health.router)


@app.get("/")
def root():
    """根路径健康探针，返回服务名与状态。"""
    return {"code": 0, "message": "success", "data": {"service": "easyrag", "status": "ok"}}
