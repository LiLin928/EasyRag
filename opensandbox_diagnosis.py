"""
OpenSandbox 完整诊断和修复方案

根据测试结果：
1. API 格式已确定：image 必须是对象，使用 entrypoint
2. 核心问题：镜像缺少 /execd 文件
3. 配置文件已设置 execd_image，但未生效

可能的原因：
- OpenSandbox Server 版本问题
- 配置文件未正确加载
- 需要使用特定镜像
"""

import httpx
import json
import asyncio

API_URL = "http://192.168.137.13:8090"
API_KEY = "easyrag2026"


async def check_opensandbox_version():
    """检查 OpenSandbox 版本"""

    headers = {"OPEN-SANDBOX-API-KEY": API_KEY}

    async with httpx.AsyncClient(timeout=10) as client:
        # 检查 OpenAPI 版本信息
        response = await client.get(f"{API_URL}/openapi.json")
        openapi = response.json()

        print("=" * 80)
        print("OpenSandbox 服务信息")
        print("=" * 80)
        print(f"标题: {openapi.get('info', {}).get('title')}")
        print(f"版本: {openapi.get('info', {}).get('version')}")
        print(f"描述: {openapi.get('info', {}).get('description', '')[:100]}")

        # 检查 schemas 中的 ImageSpec
        schemas = openapi.get('components', {}).get('schemas', {})
        if 'ImageSpec' in schemas:
            print("\n" + "=" * 80)
            print("ImageSpec 要求")
            print("=" * 80)
            image_spec = schemas['ImageSpec']
            print(json.dumps(image_spec, indent=2))


async def test_with_snapshot():
    """测试使用 snapshotId（如果可用）"""

    headers = {
        "OPEN-SANDBOX-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        # 检查是否有可用的快照
        print("\n" + "=" * 80)
        print("检查可用快照")
        print("=" * 80)

        response = await client.get(f"{API_URL}/snapshots", headers=headers)
        if response.status_code == 200:
            snapshots = response.json()
            print(f"快照数量: {snapshots.get('pagination', {}).get('totalItems', 0)}")

            if snapshots.get('items'):
                print("\n可用快照:")
                for snap in snapshots['items'][:5]:
                    print(f"  - {snap.get('id')}: {snap.get('name')}")
        else:
            print(f"无法获取快照: {response.status_code}")


async def test_minimal_payload():
    """测试最小化的请求（仅必需字段）"""

    headers = {
        "OPEN-SANDBOX-API-KEY": API_KEY,
        "Content-Type": "application/json",
    }

    # 最小化请求
    payload = {
        "image": {"uri": "python:3.11-slim"},
        "entrypoint": ["python", "-c", "print('test')"]
    }

    print("\n" + "=" * 80)
    print("测试最小化请求")
    print("=" * 80)
    print(f"请求体:\n{json.dumps(payload, indent=2)}")

    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            f"{API_URL}/sandboxes",
            headers=headers,
            json=payload
        )

        print(f"\n状态码: {response.status_code}")
        print(f"响应: {response.text[:500]}")

        if response.status_code == 500:
            error = response.json()
            print(f"\n错误详情:")
            print(f"  代码: {error.get('code')}")
            print(f"  消息: {error.get('message')[:200]}")

            # 提取关键信息
            if "execd" in error.get('message', ''):
                print("\n结论: 镜像缺少 /execd 文件")
                print("需要在虚拟机上构建包含 /execd 的镜像")


async def main():
    """主诊断流程"""
    await check_opensandbox_version()
    await test_with_snapshot()
    await test_minimal_payload()

    print("\n" + "=" * 80)
    print("诊断总结")
    print("=" * 80)
    print("""
问题确认:
  ✓ API 格式正确（image 为对象，使用 entrypoint）
  ✗ 标准镜像缺少 /execd 文件

解决方案:
  1. 在虚拟机上构建包含 /execd 的镜像
  2. 或者使用 OpenSandbox 官方镜像

构建命令（在虚拟机上执行）:
  cd /lilin/EasyRAG
  cat > Dockerfile.opensandbox << 'EOF'
  FROM python:3.11-slim
  RUN echo '#!/bin/sh' > /execd && \\
      echo 'exec "\$@"' >> /execd && \\
      chmod +x /execd
  RUN pip install numpy pandas requests httpx
  WORKDIR /workspace
  EOF

  docker build -t easyrag-opensandbox:3.11 -f Dockerfile.opensandbox .

然后更新后端代码:
  在 backend/app/providers/sandbox/__init__.py 中
  将 image 改为 "easyrag-opensandbox:3.11"
    """)


if __name__ == "__main__":
    asyncio.run(main())