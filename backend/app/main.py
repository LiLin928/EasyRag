from fastapi import FastAPI

app = FastAPI(title="EasyRAG API", version="0.1.0")


@app.get("/")
def root():
    return {"code": 0, "message": "success", "data": {"service": "easyrag", "status": "ok"}}
