"""业务层指标采集。

提供业务相关的 Prometheus 指标，包括：
- 文档解析指标
- 工作流指标
- Agent 指标
- 检索测试指标
"""
from prometheus_client import Counter, Histogram
from typing import Optional

from app.config import settings


# ============================================================
# 文档解析指标
# ============================================================

PARSE_DOCUMENTS_TOTAL = Counter(
    f"{settings.metrics_namespace}_parse_documents_total",
    "Total number of document parse tasks",
    ["status"]
)

PARSE_DOCUMENT_DURATION = Histogram(
    f"{settings.metrics_namespace}_parse_document_duration_seconds",
    "Document parsing duration in seconds",
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

PARSE_CHUNKS_CREATED_TOTAL = Counter(
    f"{settings.metrics_namespace}_parse_chunks_created_total",
    "Total number of chunks created during parsing",
    []
)


# ============================================================
# 工作流指标
# ============================================================

WORKFLOW_EXECUTIONS_TOTAL = Counter(
    f"{settings.metrics_namespace}_workflow_executions_total",
    "Total number of workflow executions",
    ["workflow_id", "status"]
)

WORKFLOW_EXECUTION_DURATION = Histogram(
    f"{settings.metrics_namespace}_workflow_execution_duration_seconds",
    "Workflow execution duration in seconds",
    ["workflow_id"],
    buckets=[0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0]
)

WORKFLOW_STEPS_TOTAL = Counter(
    f"{settings.metrics_namespace}_workflow_steps_total",
    "Total number of workflow steps executed",
    ["workflow_id", "step_type"]
)


# ============================================================
# Agent 指标
# ============================================================

AGENT_CONVERSATIONS_TOTAL = Counter(
    f"{settings.metrics_namespace}_agent_conversations_total",
    "Total number of agent conversations",
    ["agent_id"]
)

AGENT_MESSAGES_TOTAL = Counter(
    f"{settings.metrics_namespace}_agent_messages_total",
    "Total number of agent messages",
    ["agent_id", "role"]
)

AGENT_TOOL_CALLS_TOTAL = Counter(
    f"{settings.metrics_namespace}_agent_tool_calls_total",
    "Total number of agent tool calls",
    ["agent_id", "tool_name", "status"]
)


# ============================================================
# 检索测试指标
# ============================================================

RETRIEVAL_TESTS_TOTAL = Counter(
    f"{settings.metrics_namespace}_retrieval_tests_total",
    "Total number of retrieval tests",
    ["status"]
)

RETRIEVAL_TEST_DURATION = Histogram(
    f"{settings.metrics_namespace}_retrieval_test_duration_seconds",
    "Retrieval test duration in seconds",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
)


class BusinessMetrics:
    """业务指标采集工具类。

    提供静态方法记录业务层指标，包括：
    - 文档解析任务
    - 工作流执行
    - Agent 对话和消息
    - 检索测试
    """

    @staticmethod
    def record_parse(status: str, duration: float, chunks_count: int = 0):
        """记录文档解析任务。

        Args:
            status: 解析状态（success, failed, timeout）
            duration: 解析耗时（秒）
            chunks_count: 生成的 chunk 数量
        """
        # 记录解析任务计数
        PARSE_DOCUMENTS_TOTAL.labels(status=status).inc()

        # 记录解析耗时
        PARSE_DOCUMENT_DURATION.observe(duration)

        # 记录生成的 chunk 数量
        if chunks_count > 0:
            PARSE_CHUNKS_CREATED_TOTAL.inc(chunks_count)

    @staticmethod
    def record_workflow(workflow_id: str, status: str, duration: float = 0):
        """记录工作流执行。

        Args:
            workflow_id: 工作流 ID
            status: 执行状态（success, failed, timeout）
            duration: 执行耗时（秒）
        """
        # 记录工作流执行计数
        WORKFLOW_EXECUTIONS_TOTAL.labels(
            workflow_id=workflow_id,
            status=status
        ).inc()

        # 记录执行耗时
        if duration > 0:
            WORKFLOW_EXECUTION_DURATION.labels(
                workflow_id=workflow_id
            ).observe(duration)

    @staticmethod
    def record_workflow_step(workflow_id: str, step_type: str, count: int = 1):
        """记录工作流步骤执行。

        Args:
            workflow_id: 工作流 ID
            step_type: 步骤类型（node, edge, condition, tool, agent）
            count: 步骤数量
        """
        WORKFLOW_STEPS_TOTAL.labels(
            workflow_id=workflow_id,
            step_type=step_type
        ).inc(count)

    @staticmethod
    def record_agent_conversation(agent_id: str):
        """记录 Agent 对话。

        Args:
            agent_id: Agent ID
        """
        AGENT_CONVERSATIONS_TOTAL.labels(agent_id=agent_id).inc()

    @staticmethod
    def record_agent_message(agent_id: str, role: str):
        """记录 Agent 消息。

        Args:
            agent_id: Agent ID
            role: 消息角色（user, assistant, system, tool）
        """
        AGENT_MESSAGES_TOTAL.labels(
            agent_id=agent_id,
            role=role
        ).inc()

    @staticmethod
    def record_agent_tool_call(agent_id: str, tool_name: str, status: str):
        """记录 Agent 工具调用。

        Args:
            agent_id: Agent ID
            tool_name: 工具名称
            status: 调用状态（success, failed）
        """
        AGENT_TOOL_CALLS_TOTAL.labels(
            agent_id=agent_id,
            tool_name=tool_name,
            status=status
        ).inc()

    @staticmethod
    def record_retrieval_test(status: str, duration: float = 0):
        """记录检索测试。

        Args:
            status: 测试状态（success, failed）
            duration: 测试耗时（秒）
        """
        # 记录测试计数
        RETRIEVAL_TESTS_TOTAL.labels(status=status).inc()

        # 记录测试延迟
        if duration > 0:
            RETRIEVAL_TEST_DURATION.observe(duration)