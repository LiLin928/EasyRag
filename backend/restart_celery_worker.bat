@echo off
echo ================================================================================
echo 重启 Celery Worker
echo ================================================================================
echo.

echo [步骤 1] 停止所有 Celery Worker 进程...
taskkill /F /PID 31844
taskkill /F /PID 23284

echo.
echo [步骤 2] 等待 2 秒...
timeout /t 2 /nobreak >nul

echo.
echo [步骤 3] 启动新的 Celery Worker...
start "Celery Worker" cmd /k "cd /d D:\4-MyProject\EasyRag\backend && uv run python celery_worker_main.py"

echo.
echo ================================================================================
echo 重启完成！
echo 新的 Celery Worker 已在新窗口中启动
echo ================================================================================
pause