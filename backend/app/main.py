import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.exceptions import BizException
from app.security.init_admin import ensure_admin
from app.api.v2 import auth, health
from app.logging import setup_logging, new_request_id

setup_logging()
_log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_admin()
    yield


app = FastAPI(title="EasyRAG API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
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
    return JSONResponse(status_code=200, content={"code": exc.code, "message": exc.message, "data": None})


app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(health.router)


@app.get("/")
def root():
    return {"code": 0, "message": "success", "data": {"service": "easyrag", "status": "ok"}}
