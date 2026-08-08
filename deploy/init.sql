-- EasyRAG PostgreSQL 初始化扩展（在 easyrag 库执行，需 superuser）
-- VM 已通过 docker-compose.yml.bak 跑起 pgvector/pgvector:pg16，这里仅确保扩展启用
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
