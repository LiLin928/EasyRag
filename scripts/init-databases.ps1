# EasyRAG 数据库初始化脚本 (Windows PowerShell)
# 用于快速执行数据库初始化
# 使用方法: .\scripts\init-databases.ps1

# 颜色函数
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Error { Write-Host $args -ForegroundColor Red }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }

# 配置
$PG_HOST = "192.168.137.13"
$PG_USER = "postgres"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$INIT_SQL = Join-Path $SCRIPT_DIR "..\deploy\init-databases.sql"

Write-Success "========================================"
Write-Success "EasyRAG 数据库初始化"
Write-Success "========================================"
Write-Host ""

# 检查脚本文件
if (-Not (Test-Path $INIT_SQL)) {
    Write-Error "错误: 找不到初始化脚本 $INIT_SQL"
    exit 1
}

Write-Warning "步骤 1/4: 检查 PostgreSQL 连接..."
try {
    $env:PGPASSWORD = "easyrag2026"
    & psql -U $PG_USER -h $PG_HOST -c "SELECT 1" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "连接失败"
    }
    Write-Success "✓ PostgreSQL 连接成功"
} catch {
    Write-Error "错误: 无法连接到 PostgreSQL ($PG_HOST)"
    Write-Warning "提示: 请确保 PostgreSQL 正在运行且允许远程连接"
    Write-Warning "提示: 如果没有安装 psql，请在虚拟机上执行此脚本"
    exit 1
}
Write-Host ""

Write-Warning "步骤 2/4: 执行数据库初始化脚本..."
try {
    & psql -U $PG_USER -h $PG_HOST -f $INIT_SQL
    if ($LASTEXITCODE -ne 0) {
        throw "初始化失败"
    }
    Write-Success "✓ 数据库初始化成功"
} catch {
    Write-Error "错误: 数据库初始化失败"
    exit 1
}
Write-Host ""

Write-Warning "步骤 3/4: 验证数据库创建..."
Write-Host "数据库列表:"
& psql -U $PG_USER -h $PG_HOST -c "\l" | Select-String -Pattern "easyrag|langfuse"
Write-Host ""

Write-Host "用户列表:"
& psql -U $PG_USER -h $PG_HOST -c "\du" | Select-String -Pattern "easyrag|langfuse"
Write-Host ""

Write-Warning "步骤 4/4: 验证扩展..."
Write-Host "easyrag_v2 扩展:"
& psql -U $PG_USER -h $PG_HOST -d easyrag_v2 -c "\dx"
Write-Host ""

Write-Success "========================================"
Write-Success "初始化完成！"
Write-Success "========================================"
Write-Host ""
Write-Host "已创建:"
Write-Host "  - 数据库: easyrag (V1), easyrag_v2 (V2), langfuse"
Write-Host "  - 用户: easyrag, langfuse"
Write-Host "  - 扩展: vector, pg_trgm, uuid-ossp"
Write-Host ""
Write-Host "下一步:"
Write-Host "  1. 验证后端配置: cd backend; uv run python -c 'from app.config import settings; print(settings.database_url)'"
Write-Host "  2. 运行测试: cd backend; uv run pytest tests/test_health.py -v"
Write-Host ""

# 清理密码环境变量
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue