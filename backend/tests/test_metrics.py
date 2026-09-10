"""指标采集模块测试。

测试应用层指标采集功能。
"""
import os
import pytest
from unittest.mock import Mock, patch
from fastapi import FastAPI

from app.core.metrics import setup_app_metrics
from app.core.metrics.app_metrics import setup_app_metrics as setup_app_metrics_func


class TestAppMetrics:
    """应用层指标测试。"""

    def test_import_setup_app_metrics(self):
        """测试模块导入。"""
        from app.core.metrics import setup_app_metrics
        assert callable(setup_app_metrics)

    def test_setup_app_metrics_disabled(self):
        """测试 Prometheus 禁用时跳过配置。"""
        with patch("app.core.metrics.app_metrics.settings") as mock_settings:
            mock_settings.prometheus_enabled = False

            app = FastAPI()
            setup_app_metrics_func(app)

            # 验证没有添加 /metrics 路由
            routes = [route.path for route in app.routes]
            assert "/metrics" not in routes

    def test_setup_app_metrics_enabled(self):
        """测试 Prometheus 启用时正确配置。"""
        # 设置环境变量，因为 Instrumentator 会检查 PROMETHEUS_ENABLED
        os.environ["PROMETHEUS_ENABLED"] = "true"

        with patch("app.core.metrics.app_metrics.settings") as mock_settings:
            mock_settings.prometheus_enabled = True

            app = FastAPI()
            setup_app_metrics_func(app)

            # 验证添加了 /metrics 路由
            routes = [route.path for route in app.routes]
            assert "/metrics" in routes

        # 清理环境变量
        os.environ.pop("PROMETHEUS_ENABLED", None)

    def test_setup_app_metrics_instrumentation(self):
        """测试指标采集器配置。"""
        # 设置环境变量
        os.environ["PROMETHEUS_ENABLED"] = "true"

        with patch("app.core.metrics.app_metrics.settings") as mock_settings:
            mock_settings.prometheus_enabled = True

            app = FastAPI()
            initial_route_count = len(app.routes)

            setup_app_metrics_func(app)

            # 验证路由数量增加（/metrics 路由）
            assert len(app.routes) > initial_route_count

        # 清理环境变量
        os.environ.pop("PROMETHEUS_ENABLED", None)