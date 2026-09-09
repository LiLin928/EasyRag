-- EasyRAG PostgreSQL 完整初始化脚本
-- 使用超级用户（postgres）执行此脚本
-- 用法: psql -U postgres -h 192.168.137.13 -f init-databases.sql

-- ========================================
-- 1. 创建用户
-- ========================================

-- EasyRAG 应用用户
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'easyrag') THEN
        CREATE USER easyrag WITH PASSWORD 'easyrag2026';
    END IF;
END
$$;

-- Langfuse 用户
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'langfuse') THEN
        CREATE USER langfuse WITH PASSWORD 'easyrag2026';
    END IF;
END
$$;

-- ========================================
-- 2. 创建数据库
-- ========================================

-- EasyRAG V1 数据库（保留，勿动）
SELECT 'CREATE DATABASE easyrag OWNER easyrag'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'easyrag')\gexec

-- EasyRAG V2 数据库（当前使用）
SELECT 'CREATE DATABASE easyrag_v2 OWNER easyrag'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'easyrag_v2')\gexec

-- Langfuse 数据库
SELECT 'CREATE DATABASE langfuse OWNER langfuse'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec

-- ========================================
-- 3. 启用扩展（在各个数据库中）
-- ========================================

-- 在 easyrag_v2 中启用扩展
\c easyrag_v2

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 在 langfuse 中启用扩展
\c langfuse

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ========================================
-- 4. 授权
-- ========================================

-- 授予 easyrag 用户权限
\c easyrag_v2
GRANT ALL PRIVILEGES ON DATABASE easyrag_v2 TO easyrag;
GRANT ALL PRIVILEGES ON SCHEMA public TO easyrag;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO easyrag;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO easyrag;

-- 授予 langfuse 用户权限
\c langfuse
GRANT ALL PRIVILEGES ON DATABASE langfuse TO langfuse;
GRANT ALL PRIVILEGES ON SCHEMA public TO langfuse;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO langfuse;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO langfuse;

-- ========================================
-- 5. 验证
-- ========================================

\echo '==================== 初始化完成 ===================='
\echo '已创建用户: easyrag, langfuse'
\echo '已创建数据库: easyrag, easyrag_v2, langfuse'
\echo '已启用扩展: vector, pg_trgm, uuid-ossp'
\echo '================================================'

-- 显示数据库列表
\l

-- 显示用户列表
\du