"""Celery 任务优先级支持

支持任务优先级：HIGH > NORMAL > LOW
"""
from enum import IntEnum
from typing import Optional, Dict, Any
from functools import wraps

from celery import Task
from celery.exceptions import Ignore

from app.core.celery_app import celery_app


class TaskPriority(IntEnum):
    """任务优先级"""
    CRITICAL = 0   # 关键任务，立即执行
    HIGH = 3       # 高优先级
    NORMAL = 6     # 普通优先级 (默认)
    LOW = 9        # 低优先级


# 优先级配置
PRIORITY_QUEUES = {
    "critical": {"priority": TaskPriority.CRITICAL, "concurrency": 4},
    "high": {"priority": TaskPriority.HIGH, "concurrency": 4},
    "default": {"priority": TaskPriority.NORMAL, "concurrency": 4},
    "low": {"priority": TaskPriority.LOW, "concurrency": 2},
}


# 更新 Celery 配置支持优先级
celery_app.conf.task_queue_max_priority = 10
celery_app.conf.task_default_priority = TaskPriority.NORMAL
celery_app.conf.broker_transport_options = {
    "priority_steps": list(range(10)),
    "sep": ":",
    "queue_order_strategy": "priority",
}


class PriorityTask(Task):
    """
    支持优先级的 Celery Task
    
    使用示例:
        @app.task(base=PriorityTask, bind=True)
        def my_task(self, ...):
            pass
    """
    
    def apply_async(self, args=None, kwargs=None, **options):
        """重写 apply_async 支持优先级"""
        # 从 kwargs 中提取 priority
        priority = options.pop("priority", None)
        
        if priority is not None:
            options["priority"] = self._validate_priority(priority)
        
        return super().apply_async(args=args, kwargs=kwargs, **options)
    
    def _validate_priority(self, priority) -> int:
        """验证优先级"""
        if isinstance(priority, TaskPriority):
            return priority.value
        if isinstance(priority, int) and 0 <= priority <= 9:
            return priority
        raise ValueError(f"Invalid priority: {priority}. Must be 0-9 or TaskPriority enum")


def priority_task(priority: TaskPriority = TaskPriority.NORMAL, **kwargs):
    """
    优先级任务装饰器
    
    使用示例:
        @priority_task(priority=TaskPriority.HIGH)
        def urgent_task(...):
            pass
    """
    def decorator(func):
        @wraps(func)
        @celery_app.task(base=PriorityTask, bind=True, **kwargs)
        def wrapper(self, *args, **func_kwargs):
            return func(self, *args, **func_kwargs)
        
        # 设置默认优先级
        wrapper.default_priority = priority
        return wrapper
    
    if callable(priority):
        # 无参数调用: @priority_task
        func = priority
        priority = TaskPriority.NORMAL
        return decorator(func)
    
    return decorator


# 便捷函数
def submit_critical_task(task_name: str, *args, **kwargs) -> Any:
    """提交关键优先级任务"""
    return celery_app.send_task(
        task_name,
        args=args,
        kwargs=kwargs,
        priority=TaskPriority.CRITICAL,
        queue="critical"
    )


def submit_high_priority_task(task_name: str, *args, **kwargs) -> Any:
    """提交高优先级任务"""
    return celery_app.send_task(
        task_name,
        args=args,
        kwargs=kwargs,
        priority=TaskPriority.HIGH,
        queue="high"
    )


def submit_normal_task(task_name: str, *args, **kwargs) -> Any:
    """提交普通优先级任务"""
    return celery_app.send_task(
        task_name,
        args=args,
        kwargs=kwargs,
        priority=TaskPriority.NORMAL,
        queue="default"
    )


def submit_low_priority_task(task_name: str, *args, **kwargs) -> Any:
    """提交低优先级任务"""
    return celery_app.send_task(
        task_name,
        args=args,
        kwargs=kwargs,
        priority=TaskPriority.LOW,
        queue="low"
    )


class PriorityQueueManager:
    """优先级队列管理器"""
    
    @staticmethod
    def get_queue_by_priority(priority: TaskPriority) -> str:
        """根据优先级获取队列名"""
        mapping = {
            TaskPriority.CRITICAL: "critical",
            TaskPriority.HIGH: "high",
            TaskPriority.NORMAL: "default",
            TaskPriority.LOW: "low",
        }
        return mapping.get(priority, "default")
    
    @staticmethod
    def get_priority_by_queue(queue: str) -> TaskPriority:
        """根据队列名获取优先级"""
        mapping = {
            "critical": TaskPriority.CRITICAL,
            "high": TaskPriority.HIGH,
            "default": TaskPriority.NORMAL,
            "low": TaskPriority.LOW,
        }
        return mapping.get(queue, TaskPriority.NORMAL)
    
    @staticmethod
    def get_queue_stats() -> Dict[str, Any]:
        """获取队列统计"""
        # TODO: 从 Redis 获取队列长度
        return {
            "critical": 0,
            "high": 0,
            "default": 0,
            "low": 0,
        }
    
    @staticmethod
    def auto_scale_workers() -> Dict[str, int]:
        """
        根据队列长度自动调整 Worker 并发
        
        返回: {queue: recommended_concurrency}
        """
        stats = PriorityQueueManager.get_queue_stats()
        recommendations = {}
        
        for queue, length in stats.items():
            base_concurrency = PRIORITY_QUEUES.get(queue, {}).get("concurrency", 2)
            
            # 根据队列长度调整
            if length > 100:
                recommendations[queue] = base_concurrency * 2
            elif length > 50:
                recommendations[queue] = int(base_concurrency * 1.5)
            elif length < 10:
                recommendations[queue] = max(1, base_concurrency // 2)
            else:
                recommendations[queue] = base_concurrency
        
        return recommendations
