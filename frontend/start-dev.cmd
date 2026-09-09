@echo off
cd /d D:\4-MyProject\EasyRag\frontend
set VITE_USE_MOCK=true
set VITE_API_BASE=/api/v2
"D:\Program Files\nodejs\node.exe" "D:\4-MyProject\EasyRag\frontend\node_modules\vite\bin\vite.js" --port 3000 --host
