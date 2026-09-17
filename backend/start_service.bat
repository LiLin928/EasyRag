@echo off
echo === 启动 EasyRAG 后端服务 ===
echo.
echo 检查虚拟环境...
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] 虚拟环境不存在，请先创建：
    echo   uv venv --python 3.11
    echo   uv pip install -e ".[dev]"
    pause
    exit /b 1
)

echo [OK] 虚拟环境存在
echo.
echo 启动服务...
echo 提示：确保使用 uv run 来运行 uvicorn
echo.
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause