# PostgreSQL 持久化工作流队列 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将工作流执行从 Redis ARQ 迁移到 PostgreSQL 持久化队列，解决 Redis 重启数据丢失问题。

**Architecture:** 使用 PostgreSQL `job_queue` 表替代 Redis ARQ，`execution_events` 表替代 Redis Stream，Worker 采用混合轮询（100ms/5000ms 自适应）。

**Tech Stack:** PostgreSQL 14+, SQLAlchemy 2.0 async, FastAPI

**Spec:** `docs/superpowers/specs/2026-08-31-postgresql-queue-design.md`

---

## Global Constraints

- **前端契约不变** — API 接口和 SSE 事件名保持不变
- **Python 3.10+** + FastAPI + SQLAlchemy 2.0 async
- **DB 会话** — `from app.db.session import async_session`
- **TDD 流程** — 先写失败测试，再实现代码

---

## 文件结构

```
backend/app/
├── core/engine/
│   ├── pg_queue.py              # Task 1-3: PostgreSQL 队列客户端
│   ├── sse_bus_pg.py            # Task 4-5: 基于 DB 的 SSE 事件总线
│   └── arq_client.py            # Task 6: 修改为使用 pg_queue
├── worker/
│   ├── pg_worker.py             # Task 7-8: PostgreSQL Worker
│   └── pg_worker_main.py        # Task 9: Worker 启动入口
├── api/v2/
│   ├── workflows.py             # Task 10: execute 端点改造
│   ├── executions.py            # Task 11: stream/resume/cancel 改造
│   └── health.py                # Task 12: Worker 健康检查
└── core/agent/
    └── tool_registry.py         # Task 13: 改用 pg_queue
```

---

## Task 清单

- [ ] **Task 1**: 数据库表初始化 (`scripts/init_pg_queue.sql`)
- [ ] **Task 2-3**: PostgreSQL 队列客户端 (`app/core/engine/pg_queue.py`)
- [ ] **Task 4-5**: SSE 事件总线 (`app/core/engine/sse_bus_pg.py`)
- [ ] **Task 6**: ARQ 兼容层 (`app/core/engine/arq_client.py`)
- [ ] **Task 7-9**: PostgreSQL Worker (`app/worker/pg_worker.py`, `pg_worker_main.py`)
- [ ] **Task 10**: Workflows API (`app/api/v2/workflows.py`)
- [ ] **Task 11**: Executions API (`app/api/v2/executions.py`)
- [ ] **Task 12**: Health API (`app/api/v2/health.py`)
- [ ] **Task 13**: Agent Tool (`app/core/agent/tool_registry.py`)

---

## 执行选项

**1. Subagent-Driven (推荐)** - 每个 Task 使用子代理执行，我在中间审查

**2. Inline Execution** - 在当前会话批量执行

---

*— 计划结束 —*
