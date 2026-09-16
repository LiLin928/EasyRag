@echo off
echo 正在停止所有 Celery worker...
taskkill /F /IM python.exe 2>nul

timeout /t 2 /nobreak >nul

echo 正在启动 Celery worker...
cd /d D:\4-MyProject\EasyRag\backend
start "Celery Worker" cmd /c "uv run celery -A app.core.celery_app worker --loglevel=info -Q high,default,low,parse,workflow,agent -n worker1@%%h"

timeout /t 5 /nobreak >nul

echo Celery worker 已启动！
echo 请保持命令窗口打开，然后在前端测试工作流调试功能。
pause