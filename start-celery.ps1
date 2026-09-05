# EasyRAG Celery 启动脚本
# 用于本地开发启动

param(
    [string]$Mode = "all",
    [switch]$Help
)

function Show-Help {
    Write-Host @"
EasyRAG Celery 启动脚本

用法:
    .\start-celery.ps1 [Mode]

模式:
    all     - 启动 Redis + API + Worker (默认)
    redis   - 仅启动 Redis
    api     - 仅启动 API
    worker  - 仅启动 Celery Worker
    flower  - 启动 Flower 监控

示例:
    .\start-celery.ps1 all      # 启动完整服务
    .\start-celery.ps1 redis    # 仅启动 Redis
    .\start-celery.ps1 worker   # 仅启动 Worker
"@
}

if ($Help) {
    Show-Help
    exit
}

# 检查 Redis 是否运行
function Test-Redis {
    try {
        $result = Invoke-RestMethod -Uri "http://localhost:6379" -Method GET -TimeoutSec 1 -ErrorAction SilentlyContinue
        return $true
    } catch {
        return $false
    }
}

# 启动 Redis
function Start-Redis {
    Write-Host "🔄 启动 Redis..." -ForegroundColor Cyan
    docker run -d \
        --name easyrag-redis-dev \
        -p 6379:6379 \
        redis:7-alpine redis-server --appendonly yes
    
    # 等待 Redis 就绪
    Write-Host "⏳ 等待 Redis 就绪..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
    Write-Host "✅ Redis 已启动" -ForegroundColor Green
}

# 启动 API
function Start-API {
    Write-Host "🚀 启动 FastAPI..." -ForegroundColor Cyan
    Push-Location backend
    try {
        $env:REDIS_URL = "redis://localhost:6379"
        $env:CELERY_BROKER_URL = "redis://localhost:6379/0"
        $env:CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
        uvicorn app.main:app --reload --port 8000
    } finally {
        Pop-Location
    }
}

# 启动 Worker
function Start-Worker {
    Write-Host "⚙️ 启动 Celery Worker..." -ForegroundColor Cyan
    Push-Location backend
    try {
        $env:REDIS_URL = "redis://localhost:6379"
        $env:CELERY_BROKER_URL = "redis://localhost:6379/0"
        $env:CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
        python celery_worker_main.py -Q default,parse,workflow,agent -c 4 -l info
    } finally {
        Pop-Location
    }
}

# 启动 Flower
function Start-Flower {
    Write-Host "📊 启动 Flower 监控..." -ForegroundColor Cyan
    Push-Location backend
    try {
        $env:CELERY_BROKER_URL = "redis://localhost:6379/0"
        $env:CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
        celery -A app.core.celery_app flower --port=5555
    } finally {
        Pop-Location
    }
}

# 主逻辑
switch ($Mode) {
    "all" {
        # 检查并启动 Redis
        if (-not (docker ps -q -f "name=easyrag-redis-dev")) {
            Start-Redis
        } else {
            Write-Host "✅ Redis 已在运行" -ForegroundColor Green
        }
        
        Write-Host ""
        Write-Host "==================================" -ForegroundColor Green
        Write-Host "EasyRAG Celery 服务已准备就绪" -ForegroundColor Green
        Write-Host "==================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "请手动启动以下服务（在新终端中）:" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "1. 启动 API:" -ForegroundColor Cyan
        Write-Host "   .\start-celery.ps1 api" -ForegroundColor White
        Write-Host ""
        Write-Host "2. 启动 Worker:" -ForegroundColor Cyan
        Write-Host "   .\start-celery.ps1 worker" -ForegroundColor White
        Write-Host ""
        Write-Host "3. 启动监控 (可选):" -ForegroundColor Cyan
        Write-Host "   .\start-celery.ps1 flower" -ForegroundColor White
        Write-Host ""
        Write-Host "或使用 Docker Compose:" -ForegroundColor Cyan
        Write-Host "   docker-compose -f docker-compose.celery.yml up" -ForegroundColor White
        Write-Host ""
    }
    "redis" {
        Start-Redis
    }
    "api" {
        Start-API
    }
    "worker" {
        Start-Worker
    }
    "flower" {
        Start-Flower
    }
    default {
        Write-Host "❌ 未知模式: $Mode" -ForegroundColor Red
        Show-Help
        exit 1
    }
}
