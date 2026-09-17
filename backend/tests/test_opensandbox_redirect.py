"""测试 OpenSandbox 客户端重定向处理。"""
import asyncio

import pytest

from app.providers.sandbox.opensandbox_client import OpenSandboxClient


@pytest.mark.asyncio
async def test_opensandbox_redirect_handling():
    """测试客户端能正确处理 301 重定向。"""
    client = OpenSandboxClient()

    try:
        # 测试健康检查（可能会触发重定向）
        health = await client.health_check()

        # 如果返回 unhealthy，检查是否是连接问题而非重定向问题
        if health["status"] == "unhealthy":
            # 如果错误中包含 "301" 或 "Redirect"，说明重定向处理有问题
            error_msg = health.get("error", "")
            assert "301" not in error_msg, f"未正确处理 301 重定向: {error_msg}"
            assert "Redirect" not in error_msg, f"未正确处理重定向: {error_msg}"

            # 如果是连接问题（网络不可达等），跳过测试
            if "Connection" in error_msg or "connect" in error_msg.lower():
                pytest.skip(f"OpenSandbox 服务不可达: {error_msg}")

        print(f"✅ 健康检查结果: {health}")

    finally:
        await client.close()


@pytest.mark.asyncio
async def test_opensandbox_create_sandbox():
    """测试创建沙箱（会自动处理重定向）。"""
    client = OpenSandboxClient()

    try:
        # 尝试创建一个简单的沙箱
        sandbox = await client.create_sandbox(
            image="python:3.10-alpine",
            command=["python", "-c", "print('Hello, World!')"],
            memory_mb=256,
            timeout_seconds=60,
        )

        print(f"✅ 沙箱创建成功: {sandbox.sandbox_id}, 状态: {sandbox.status}")

        # 等待完成
        info = await client.wait_for_completion(sandbox.sandbox_id, timeout=60)
        print(f"✅ 沙箱执行完成: {info.status}, 退出码: {info.exit_code}")

        # 获取日志
        logs = await client.get_logs(sandbox.sandbox_id)
        print(f"✅ 沙箱日志:\n{logs.stdout}")

        # 验证输出
        assert "Hello, World!" in logs.stdout, "沙箱执行结果不正确"

    except Exception as e:
        # 如果错误信息中包含 301，说明重定向处理失败
        error_msg = str(e)
        assert "301" not in error_msg, f"未正确处理 301 重定向: {error_msg}"
        raise

    finally:
        await client.close()


if __name__ == "__main__":
    # 直接运行测试
    asyncio.run(test_opensandbox_redirect_handling())
    asyncio.run(test_opensandbox_create_sandbox())