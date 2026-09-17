"""
简化版 OpenSandbox 测试（使用标准镜像）
"""
import asyncio
import sys
import os

# 添加后端路径
sys.path.insert(0, 'D:/4-MyProject/EasyRag/backend')

from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig
from datetime import timedelta


async def test_opensandbox_simple():
    """使用标准 Python 镜像测试"""

    domain = "192.168.137.13:8090"
    api_key = "easyrag2026"
    image = "python:3.11-slim"  # 使用标准镜像

    print("=" * 80)
    print("OpenSandbox 简化测试")
    print("=" * 80)
    print(f"Server: {domain}")
    print(f"镜像: {image}")

    config = ConnectionConfig(
        domain=domain,
        api_key=api_key,
        request_timeout=timedelta(seconds=180),  # 增加超时时间
    )

    sandbox = None
    try:
        print("\n[1/3] 创建沙箱...")
        sandbox = await Sandbox.create(
            image,
            connection_config=config,
            entrypoint=["python", "-c", "print('Hello')"],
        )
        print(f"沙箱 ID: {sandbox.id}")

        print("\n[2/3] 执行命令...")
        result = await sandbox.commands.run("python -c \"print('Test OK')\"")
        print(f"输出: {result.logs.stdout}")

        print("\n[3/3] 文件操作...")
        content = "test-content"
        await sandbox.files.write_file("/tmp/test.txt", content)
        data = await sandbox.files.read_file("/tmp/test.txt")
        print(f"写入: {content}, 读取: {data}, 一致: {data == content}")

        print("\n" + "=" * 80)
        print("[成功] OpenSandbox 正常工作")
        print("=" * 80)
        return True

    except Exception as e:
        print(f"\n[失败] {type(e).__name__}: {e}")
        return False
    finally:
        if sandbox:
            try:
                await sandbox.close()
                print("\n沙箱已清理")
            except:
                pass


if __name__ == "__main__":
    result = asyncio.run(test_opensandbox_simple())
    sys.exit(0 if result else 1)