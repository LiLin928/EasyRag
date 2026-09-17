#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenSandbox Python 沙箱连通性测试脚本
====================================
用于验证你的 OpenSandbox Server 是否能正常创建沙箱并执行 Python 脚本。

依赖（在 client 容器或本机安装）:
    pip install opensandbox opensandbox-code-interpreter

用法:
    1) 直接运行（使用环境变量 OPEN_SANDBOX_DOMAIN / OPEN_SANDBOX_API_KEY）:
       python test_opensandbox.py
    2) 显式指定 server 地址 / api_key / 应用镜像:
       python test_opensandbox.py --domain 192.168.137.13:8090 --api-key easyrag2026

说明:
    - execd_image 必须是官方引导镜像（配置在 opensandbox-config.fixed.toml）
    - 应用镜像 code-interpreter 内置 Python 3.12 + Node.js
    - 脚本会自动创建沙箱 -> 执行 3 类测试（运行代码/读写文件/命令）-> 清理沙箱
"""
import argparse
import asyncio
import os
import sys
from datetime import timedelta

from code_interpreter import CodeInterpreter, SupportedLanguage
from opensandbox import Sandbox
from opensandbox.config import ConnectionConfig

# 国内网络可换成阿里云镜像仓库，与你的配置保持一致
DEFAULT_IMAGE = (
    "sandbox-registry.cn-zhangjiakou.cr.aliyuncs.com/opensandbox/code-interpreter:v1.1.0"
)
# 或用 Docker Hub:
# DEFAULT_IMAGE = "opensandbox/code-interpreter:v1.1.0"


async def test_python(interpreter) -> None:
    """测试 1：运行一段 Python 代码并取回结果。"""
    print("\n=== [1/3] Python 代码执行测试 ===")
    py = await interpreter.codes.run(
        "import platform, sys\n"
        "print('Hello from OpenSandbox!')\n"
        "info = {'python': platform.python_version(), 'os': platform.system(), 'sum': 2 + 2}\n"
        "info",
        language=SupportedLanguage.PYTHON,
    )
    for msg in py.logs.stdout:
        print(f"  [stdout] {msg.text}")
    if py.error:
        print(f"  [error] {py.error.name}: {py.error.value}")
        return False
    for r in py.result:
        print(f"  [result] {r.text}")
    return True


async def test_fs(sandbox) -> None:
    """测试 2：在沙箱内写入并回读文件（验证文件系统可用）。

    注意：顶层 Sandbox 暴露的是 .files（Filesystem），
    方法名为 write_file / read_file（不是 write / read）。
    """
    print("\n=== [2/3] 文件读写测试 ===")
    content = "opensandbox-file-test-ok"
    await sandbox.files.write_file("/tmp/hello.txt", content)
    data = await sandbox.files.read_file("/tmp/hello.txt")
    ok = data == content
    print(f"  写入 -> {content!r}，回读一致 = {ok}")
    return ok


async def test_command(sandbox) -> None:
    """测试 3：执行 shell 命令（验证 execd 通信链路）。"""
    print("\n=== [3/3] Shell 命令测试 ===")
    cmd = await sandbox.commands.run("echo sandbox-command-ok && python3 --version")
    joined = "\n".join(m.text for m in cmd.logs.stdout)
    print(f"  输出:\n{joined}")
    return "sandbox-command-ok" in joined


async def main() -> None:
    parser = argparse.ArgumentParser(description="OpenSandbox Python 沙箱连通性测试")
    parser.add_argument("--domain", default=None, help="Server 地址，如 192.168.137.13:8090")
    parser.add_argument("--api-key", default=None, help="Server api_key")
    parser.add_argument("--image", default=None, help="沙箱应用镜像")
    parser.add_argument("--timeout", type=int, default=90, help="请求超时（秒）")
    args = parser.parse_args()

    domain = args.domain or os.getenv("OPEN_SANDBOX_DOMAIN", "localhost:8090")
    api_key = args.api_key or os.getenv("OPEN_SANDBOX_API_KEY", "")
    image = args.image or os.getenv("OPEN_SANDBOX_IMAGE", DEFAULT_IMAGE)

    print(f"连接 Server: {domain}")
    print(f"应用镜像:   {image}")

    config = ConnectionConfig(
        domain=domain,
        api_key=api_key,
        request_timeout=timedelta(seconds=args.timeout),
    )

    sandbox = None
    try:
        print("\n>>> 正在创建沙箱 ...")
        sandbox = await Sandbox.create(
            image,
            connection_config=config,
            entrypoint=["/opt/code-interpreter/code-interpreter.sh"],
        )
        print(f">>> 沙箱创建成功: {sandbox.id}")

        interpreter = await CodeInterpreter.create(sandbox=sandbox)

        results = [
            await test_python(interpreter),
            await test_fs(sandbox),
            await test_command(sandbox),
        ]

        print("\n========== 汇总 ==========")
        names = ["Python 执行", "文件读写", "Shell 命令"]
        for name, ok in zip(names, results):
            print(f"  {name:<10} {'✓ 通过' if ok else '✗ 失败'}")
        if all(results):
            print("\n✅ 全部通过：OpenSandbox 可正常执行 Python 脚本！")
        else:
            print("\n⚠️ 存在失败项，请检查配置与日志。")

    except Exception as e:  # noqa: BLE001
        print(f"\n❌ 沙箱创建/执行失败: {type(e).__name__}: {e}")
        sys.exit(1)
    finally:
        if sandbox is not None:
            try:
                await sandbox.close()
                print("\n>>> 沙箱已清理。")
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    asyncio.run(main())
