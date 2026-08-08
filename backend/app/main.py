from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.exceptions import BizException
from app.security.init_admin import ensure_admin
from app.api.v2 import auth, health


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


@app.exception_handler(BizException)
async def biz_exception_handler(request: Request, exc: BizException):
    return JSONResponse(status_code=200, content={"code": exc.code, "message": exc.message, "data": None})


app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(health.router)   # /health at root


@app.get("/")
def root():
    return {"code": 0, "message": "success", "data": {"service": "easyrag", "status": "ok"}}
