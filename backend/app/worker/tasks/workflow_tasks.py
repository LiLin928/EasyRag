"""工作流 Celery 任务"""
import asyncio
from typing import List, Dict, Any
from celery import chain, group, chord
from celery.exceptions import MaxRetriesExceededError
import logging

from app.core.celery_app import celery_app
from app.core.redis_streams import publish_event

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def execute_workflow(self, execution_id: str, definition: Dict[str, Any], debug: bool = False) -> dict:
    """
    工作流执行任务
    
    解析工作流定义，构建依赖图，使用 Celery Chain/Group 执行
    
    Args:
        execution_id: 执行 ID
        definition: 工作流定义 {nodes: [...], edges: [...]}
        debug: 是否调试模式
        
    Returns:
        执行结果
    """
    stream_key = f"workflow:{execution_id}"
    
    try:
        # 1. 发送开始事件
        _publish_sync(stream_key, "execution_started", {
            "execution_id": execution_id,
            "debug": debug
        })
        
        nodes = definition.get("nodes", [])
        edges = definition.get("edges", [])
        
        if not nodes:
            raise ValueError("Workflow definition has no nodes")
        
        # 2. 拓扑排序构建执行链
        sorted_nodes = _topological_sort(nodes, edges)
        
        # 3. 构建 Celery Chain
        # 注意：实际工作流可能包含并行分支，需要更复杂的构建逻辑
        # 这里简化处理为串行执行
        node_tasks = []
        for node in sorted_nodes:
            node_tasks.append(execute_node_task.s(execution_id, node))
        
        if not node_tasks:
            raise ValueError("No executable nodes found")
        
        # 4. 发布构建完成事件
        _publish_sync(stream_key, "execution_chain_built", {
            "execution_id": execution_id,
            "node_count": len(node_tasks)
        })
        
        # 5. 执行工作流链
        # 实际应该使用 workflow_chain.apply_async() 并等待结果
        # 这里为了示例，直接串行执行
        result = {"execution_id": execution_id, "completed_nodes": []}
        
        for task_sig in node_tasks:
            # 同步调用子任务
            node_result = task_sig.apply().get()
            result["completed_nodes"].append(node_result)
        
        # 6. 完成事件
        _publish_sync(stream_key, "execution_completed", {
            "execution_id": execution_id,
            "result": result
        })
        
        logger.info(f"Workflow execution completed: {execution_id}")
        return result
        
    except Exception as exc:
        logger.error(f"Workflow execution failed: {execution_id}, error={exc}")
        
        _publish_sync(stream_key, "execution_failed", {
            "execution_id": execution_id,
            "error": str(exc)
        })
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)
        
        raise


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def execute_node_task(self, execution_id: str, node: Dict[str, Any]) -> dict:
    """
    执行单个工作流节点
    
    Args:
        execution_id: 执行 ID
        node: 节点定义 {id, type, config, ...}
        
    Returns:
        节点执行结果
    """
    stream_key = f"workflow:{execution_id}"
    node_id = node.get("id", "unknown")
    node_type = node.get("type", "unknown")
    
    try:
        # 1. 节点开始事件
        _publish_sync(stream_key, "node_started", {
            "execution_id": execution_id,
            "node_id": node_id,
            "node_type": node_type
        })
        
        # 2. 根据节点类型执行不同逻辑
        result = _execute_node_by_type(node_type, node, execution_id)
        
        # 3. 节点完成事件
        _publish_sync(stream_key, "node_completed", {
            "execution_id": execution_id,
            "node_id": node_id,
            "node_type": node_type,
            "result": result
        })
        
        return {
            "node_id": node_id,
            "node_type": node_type,
            "status": "completed",
            "result": result
        }
        
    except Exception as exc:
        logger.error(f"Node execution failed: {execution_id}/{node_id}, error={exc}")
        
        _publish_sync(stream_key, "node_failed", {
            "execution_id": execution_id,
            "node_id": node_id,
            "node_type": node_type,
            "error": str(exc)
        })
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)
        
        raise


def _execute_node_by_type(node_type: str, node: Dict[str, Any], execution_id: str) -> Any:
    """根据节点类型执行相应逻辑"""
    config = node.get("config", {})
    
    if node_type == "llm":
        # LLM 节点
        # TODO: 调用 LLM 服务
        # from app.services.llm_service import call_llm
        # return call_llm(config)
        return {"content": "LLM response placeholder", "tokens": 100}
    
    elif node_type == "retrieval":
        # 检索节点
        # TODO: 调用检索服务
        # from app.core.retrieval.pipeline import retrieve
        # return retrieve(config)
        return {"chunks": [], "sources": []}
    
    elif node_type == "code":
        # 代码执行节点
        # TODO: 调用代码沙箱
        # from app.providers.sandbox import run_in_sandbox
        # return run_in_sandbox(config.get("code"))
        return {"output": "Code execution placeholder"}
    
    elif node_type == "condition":
        # 条件分支节点
        # 返回分支决策，由工作流引擎处理
        condition = config.get("condition", "")
        return {"_branch": "true" if condition else "false"}
    
    elif node_type == "variable_assign":
        # 变量赋值节点
        return {"variables": config.get("variables", {})}
    
    elif node_type == "http":
        # HTTP 请求节点
        # TODO: 调用 HTTP 工具
        return {"status": 200, "data": {}}
    
    elif node_type == "human":
        # 人工审核节点
        # 创建待办，暂停工作流
        return {"_status": "paused", "_todo_id": f"todo-{execution_id}"}
    
    else:
        logger.warning(f"Unknown node type: {node_type}")
        return {"output": f"Unknown node type: {node_type}"}


def _topological_sort(nodes: List[Dict], edges: List[Dict]) -> List[Dict]:
    """
    拓扑排序工作流节点
    
    根据 edges 定义的依赖关系，对 nodes 进行排序
    """
    # 构建节点映射
    node_map = {n["id"]: n for n in nodes}
    
    # 构建依赖图
    in_degree = {n["id"]: 0 for n in nodes}
    adjacency = {n["id"]: [] for n in nodes}
    
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source in in_degree and target in in_degree:
            adjacency[source].append(target)
            in_degree[target] += 1
    
    # Kahn 算法
    queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
    sorted_ids = []
    
    while queue:
        node_id = queue.pop(0)
        sorted_ids.append(node_id)
        
        for neighbor in adjacency[node_id]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    if len(sorted_ids) != len(nodes):
        raise ValueError("Workflow has circular dependencies")
    
    return [node_map[node_id] for node_id in sorted_ids]


def _publish_sync(stream: str, event_type: str, payload: dict):
    """同步发布事件"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(publish_event(stream, event_type, payload))
        loop.close()
    except Exception as e:
        logger.warning(f"Failed to publish event: {e}")
