"""节点执行器基类与工厂路由。

BaseNodeExecutor 是所有节点执行器的抽象基类。
NodeRouter 按 node type 查找对应执行器并实例化。
"""
from abc import ABC, abstractmethod


class BaseNodeExecutor(ABC):
    """节点执行器基类。"""

    def __init__(self, node_def: dict):
        self.node_id: str = node_def["id"]
        self.node_type: str = node_def["type"]
        data = node_def.get("data", {})
        self.config: dict = data.get("config", {})
        self.label: str = data.get("label", node_def["id"])

    @abstractmethod
    async def run(self, state: dict) -> dict:
        """执行节点逻辑，返回状态更新字典。"""
        ...


class NodeRouter:
    """按 node type 路由到对应执行器。"""

    _registry: dict[str, type[BaseNodeExecutor]] = {}

    @classmethod
    def register(cls, node_type: str, executor_cls: type[BaseNodeExecutor]):
        cls._registry[node_type] = executor_cls

    @classmethod
    def create(cls, node_def: dict) -> BaseNodeExecutor:
        node_type = node_def["type"]
        executor_cls = cls._registry.get(node_type)
        if not executor_cls:
            raise ValueError(f"不支持的节点类型: {node_type}")
        return executor_cls(node_def)
 
