from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.exceptions import BizException

app = FastAPI(title="EasyRAG API", version="0.1.0")


@app.exception_handler(BizException)
async def biz_exception_handler(request: Request, exc: BizException):
    # 业务异常：HTTP 200 + code（适配前端 axios 拦截器）
    return JSONResponse(status_code=200, content={"code": exc.code, "message": exc.message, "data": None})


@app.get("/")
def root():
    return {"code": 0, "message": "success", "data": {"service": "easyrag", "status": "ok"}}
