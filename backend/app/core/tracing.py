"""Langfuse 追踪集成

提供任务执行的完整链路追踪
"""
import os
import functools
import logging
from typing import Optional, Dict, Any, Callable
from contextlib import contextmanager
from datetime import datetime

from celery.signals import task_prerun, task_postrun, task_failure

logger = logging.getLogger(__name__)

# Langfuse 配置
LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")


class TracingManager:
    """追踪管理器"""
    
    _client = None
    
    @classmethod
    def get_client(cls):
        """获取 Langfuse 客户端"""
        if not LANGFUSE_ENABLED:
            return None
        
        if cls._client is None:
            try:
                from langfuse import Langfuse
                cls._client = Langfuse(
                    public_key=LANGFUSE_PUBLIC_KEY,
                    secret_key=LANGFUSE_SECRET_KEY,
                    host=LANGFUSE_HOST
                )
                logger.info("Langfuse client initialized")
            except ImportError:
                logger.warning("langfuse package not installed, tracing disabled")
                return None
            except Exception as e:
                logger.error(f"Failed to initialize Langfuse: {e}")
                return None
        
        return cls._client
    
    @classmethod
    def is_enabled(cls) -> bool:
        """检查追踪是否启用"""
        return LANGFUSE_ENABLED and cls.get_client() is not None


class TaskTracer:
    """任务追踪器"""
    
    def __init__(self, task_name: str, task_id: str):
        self.task_name = task_name
        self.task_id = task_id
        self.trace = None
        self.span = None
        self.start_time = None
    
    def start(self, **metadata):
        """开始追踪"""
        if not TracingManager.is_enabled():
            return
        
        try:
            client = TracingManager.get_client()
            
            # 创建 trace
            self.trace = client.trace(
                name=self.task_name,
                id=self.task_id,
                metadata={
                    "celery_task_id": self.task_id,
                    "task_name": self.task_name,
                    **metadata
                }
            )
            
            # 创建 span
            self.span = self.trace.span(
                name="execute",
                start_time=datetime.utcnow()
            )
            
            self.start_time = datetime.utcnow()
            logger.debug(f"Trace started: {self.task_name}[{self.task_id}]")
            
        except Exception as e:
            logger.error(f"Failed to start trace: {e}")
    
    def update(self, **updates):
        """更新追踪信息"""
        if not self.span:
            return
        
        try:
            for key, value in updates.items():
                self.span.update(metadata={key: value})
        except Exception as e:
            logger.error(f"Failed to update trace: {e}")
    
    def score(self, name: str, value: float, comment: Optional[str] = None):
        """添加评分"""
        if not TracingManager.is_enabled() or not self.trace:
            return
        
        try:
            self.trace.score(
                name=name,
                value=value,
                comment=comment
            )
        except Exception as e:
            logger.error(f"Failed to add score: {e}")
    
    def complete(self, status: str = "success", output: Optional[Dict] = None):
        """完成追踪"""
        if not self.span:
            return
        
        try:
            end_time = datetime.utcnow()
            duration = (end_time - self.start_time).total_seconds() if self.start_time else None
            
            self.span.end(
                end_time=end_time,
                status=status,
                output=output,
                metadata={"duration_seconds": duration}
            )
            
            if self.trace:
                self.trace.update(metadata={"status": status})
            
            logger.debug(f"Trace completed: {self.task_name}[{self.task_id}] in {duration}s")
            
        except Exception as e:
            logger.error(f"Failed to complete trace: {e}")
    
    def fail(self, error: Exception):
        """标记失败"""
        if not self.span:
            return
        
        try:
            self.complete(
                status="error",
                output={"error": str(error), "error_type": type(error).__name__}
            )
        except Exception as e:
            logger.error(f"Failed to mark trace as failed: {e}")


# Celery 信号集成
@task_prerun.connect
def on_task_prerun(sender, task_id, task, args, kwargs, **extra):
    """任务开始前"""
    if not TracingManager.is_enabled():
        return
    
    try:
        tracer = TaskTracer(sender.name, task_id)
        
        # 存储到 task request
        sender.request.tracer = tracer
        
        tracer.start(
            args=str(args)[:1000],  # 截断避免过长
            kwargs=str(kwargs)[:1000]
        )
        
    except Exception as e:
        logger.error(f"Failed to start task trace: {e}")


@task_postrun.connect
def on_task_postrun(sender, task_id, task, retval, state, **extra):
    """任务完成后"""
    if not TracingManager.is_enabled():
        return
    
    try:
        tracer = getattr(sender.request, "tracer", None)
        if tracer:
            tracer.complete(status=state, output={"result": str(retval)[:1000]})
    except Exception as e:
        logger.error(f"Failed to complete task trace: {e}")


@task_failure.connect
def on_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **extra):
    """任务失败"""
    if not TracingManager.is_enabled():
        return
    
    try:
        tracer = getattr(sender.request, "tracer", None)
        if tracer:
            tracer.fail(exception)
    except Exception as e:
        logger.error(f"Failed to mark task trace as failed: {e}")


# 装饰器
def traced_task(func: Callable) -> Callable:
    """
    追踪任务装饰器
    
    手动追踪任务执行
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not TracingManager.is_enabled():
            return func(self, *args, **kwargs)
        
        task_id = self.request.id
        task_name = self.name
        
        tracer = TaskTracer(task_name, task_id)
        tracer.start()
        
        try:
            result = func(self, *args, **kwargs)
            tracer.complete(output={"result": str(result)[:500]})
            return result
        except Exception as e:
            tracer.fail(e)
            raise
    
    return wrapper


class MetricsCollector:
    """指标收集器"""
    
    _metrics: Dict[str, Any] = {}
    
    @classmethod
    def record(cls, metric_name: str, value: float, task_name: str = None):
        """记录指标"""
        key = f"{task_name}:{metric_name}" if task_name else metric_name
        
        if key not in cls._metrics:
            cls._metrics[key] = []
        
        cls._metrics[key].append({
            "value": value,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    @classmethod
    def get_stats(cls, metric_name: str, task_name: str = None) -> Dict:
        """获取统计"""
        key = f"{task_name}:{metric_name}" if task_name else metric_name
        values = [m["value"] for m in cls._metrics.get(key, [])]
        
        if not values:
            return {}
        
        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }


# 便捷函数
def trace_span(name: str, **kwargs):
    """
    上下文管理器追踪 span
    
    示例:
        with trace_span("embedding"):
            await embed_chunks(chunks)
    """
    class SpanContext:
        def __enter__(self):
            if TracingManager.is_enabled():
                # TODO: 实现嵌套 span
                pass
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if TracingManager.is_enabled():
                pass
    
    return SpanContext()
