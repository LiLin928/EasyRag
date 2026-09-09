-- =====================================================
-- EasyRAG PostgreSQL 队列初始化脚本
-- 文件: scripts/init_pg_queue.sql
-- 日期: 2026-08-31
-- 功能: 创建工作流执行队列相关表和索引
-- =====================================================

-- 检查表是否存在，如存在则删除（用于重新初始化）
-- 警告: 生产环境请谨慎使用

-- 删除现有索引（如果存在）
DROP INDEX IF EXISTS idx_job_queue_status_priority;
DROP INDEX IF EXISTS idx_job_queue_worker;
DROP INDEX IF EXISTS idx_events_exec_seq;
DROP INDEX IF EXISTS idx_events_exec_time;

-- 删除现有表（如果存在）
DROP TABLE IF EXISTS execution_events;
DROP TABLE IF EXISTS job_queue;

-- =====================================================
-- 1. job_queue 表 - 工作流执行队列
-- =====================================================
CREATE TABLE job_queue (
    -- 主键
    id BIGSERIAL PRIMARY KEY,
    
    -- 执行唯一标识
    execution_id UUID NOT NULL UNIQUE,
    
    -- 任务状态
    -- pending: 等待执行
    -- running: 正在执行
    -- completed: 成功完成
    -- failed: 执行失败
    -- cancelled: 已取消
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    
    -- 执行该任务的 Worker 标识
    worker_id VARCHAR(100),
    
    -- 任务优先级（高值优先执行）
    priority INT DEFAULT 0,
    
    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- 重试机制
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    
    -- 错误信息
    error_msg TEXT,
    
    -- 超时设置（秒）
    timeout_seconds INT DEFAULT 600
);

-- 添加注释
COMMENT ON TABLE job_queue IS '工作流执行队列 - 存储待执行和正在执行的工作流任务';
COMMENT ON COLUMN job_queue.id IS '自增主键';
COMMENT ON COLUMN job_queue.execution_id IS '执行唯一标识 (UUID)，关联 workflow_executions 表';
COMMENT ON COLUMN job_queue.status IS '任务状态: pending/running/completed/failed/cancelled';
COMMENT ON COLUMN job_queue.worker_id IS '执行该任务的 Worker 标识';
COMMENT ON COLUMN job_queue.priority IS '任务优先级，数值越高优先级越高';
COMMENT ON COLUMN job_queue.created_at IS '任务创建时间';
COMMENT ON COLUMN job_queue.started_at IS '任务开始执行时间';
COMMENT ON COLUMN job_queue.completed_at IS '任务完成时间';
COMMENT ON COLUMN job_queue.retry_count IS '已重试次数';
COMMENT ON COLUMN job_queue.max_retries IS '最大重试次数';
COMMENT ON COLUMN job_queue.error_msg IS '失败时的错误信息';
COMMENT ON COLUMN job_queue.timeout_seconds IS '任务超时时间（秒）';

-- =====================================================
-- 2. execution_events 表 - 执行事件流
-- =====================================================
CREATE TABLE execution_events (
    -- 自增序列主键
    seq BIGSERIAL PRIMARY KEY,
    
    -- 关联的执行 ID
    execution_id UUID NOT NULL,
    
    -- 事件类型
    -- execution_start: 执行开始
    -- node_start: 节点开始
    -- node_complete: 节点完成
    -- execution_complete: 执行完成
    -- execution_paused: 执行暂停
    -- execution_resumed: 执行恢复
    -- execution_cancelled: 执行取消
    -- error: 执行错误
    event_type VARCHAR(50) NOT NULL,
    
    -- 事件数据（JSON 格式）
    data JSONB,
    
    -- 创建时间
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 添加注释
COMMENT ON TABLE execution_events IS '工作流执行事件流 - 记录执行过程中的所有事件';
COMMENT ON COLUMN execution_events.seq IS '全局序列号，用于事件排序';
COMMENT ON COLUMN execution_events.execution_id IS '关联的执行 ID';
COMMENT ON COLUMN execution_events.event_type IS '事件类型';
COMMENT ON COLUMN execution_events.data IS '事件数据（JSONB 格式）';
COMMENT ON COLUMN execution_events.created_at IS '事件创建时间';

-- =====================================================
-- 3. 创建索引
-- =====================================================

-- 3.1 job_queue 索引

-- 用于出队查询：按状态和优先级排序取任务
CREATE INDEX idx_job_queue_status_priority 
    ON job_queue (status, priority DESC, created_at ASC);

-- 用于 Worker 健康检查：查找运行中的任务及其 Worker
CREATE INDEX idx_job_queue_worker 
    ON job_queue (worker_id) 
    WHERE status = 'running';

-- 3.2 execution_events 索引

-- 用于按执行 ID 和序列号查询事件
CREATE INDEX idx_events_exec_seq 
    ON execution_events (execution_id, seq);

-- 用于按执行 ID 和时间查询事件
CREATE INDEX idx_events_exec_time 
    ON execution_events (execution_id, created_at);

-- =====================================================
-- 4. 可选：创建事件清理函数（自动清理旧数据）
-- =====================================================

-- 清理已完成任务的函数
CREATE OR REPLACE FUNCTION cleanup_completed_jobs(older_than_days INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- 删除已完成超过指定天数的任务
    DELETE FROM job_queue
    WHERE status IN ('completed', 'failed', 'cancelled')
      AND completed_at < NOW() - INTERVAL '1 day' * older_than_days;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 清理旧事件的函数
CREATE OR REPLACE FUNCTION cleanup_old_events(older_than_days INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- 删除超过指定天数的事件
    DELETE FROM execution_events
    WHERE created_at < NOW() - INTERVAL '1 day' * older_than_days;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 添加函数注释
COMMENT ON FUNCTION cleanup_completed_jobs IS '清理已完成超过指定天数的任务';
COMMENT ON FUNCTION cleanup_old_events IS '清理超过指定天数的事件记录';

-- =====================================================
-- 5. 验证初始化结果
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE 'PostgreSQL 队列表初始化完成';
    RAISE NOTICE '============================================';
    RAISE NOTICE '表: job_queue - 工作流执行队列';
    RAISE NOTICE '表: execution_events - 执行事件流';
    RAISE NOTICE '索引: idx_job_queue_status_priority';
    RAISE NOTICE '索引: idx_job_queue_worker';
    RAISE NOTICE '索引: idx_events_exec_seq';
    RAISE NOTICE '索引: idx_events_exec_time';
    RAISE NOTICE '函数: cleanup_completed_jobs()';
    RAISE NOTICE '函数: cleanup_old_events()';
    RAISE NOTICE '============================================';
END $$;

-- 显示创建的表信息
SELECT 
    'job_queue' AS table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'job_queue') AS column_count
UNION ALL
SELECT 
    'execution_events' AS table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'execution_events') AS column_count;


-- Task type extension for non-workflow tasks
ALTER TABLE job_queue ADD COLUMN IF NOT EXISTS task_type VARCHAR(50) DEFAULT 'workflow';
ALTER TABLE job_queue ADD COLUMN IF NOT EXISTS task_payload JSONB DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_job_queue_task_type ON job_queue(task_type, status, priority DESC);

COMMENT ON COLUMN job_queue.task_type IS 'Task type: workflow, parse_document, reembed_chunks, retrieval_test';
COMMENT ON COLUMN job_queue.task_payload IS 'Task-specific payload as JSON';
