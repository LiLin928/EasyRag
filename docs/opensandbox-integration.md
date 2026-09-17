# OpenSandbox 集成说明

## 问题诊断

### 已解决的问题
1. ✅ API 格式已确定
2. ✅ 认证头部已修正（OPEN-SANDBOX-API-KEY）
3. ✅ 请求字段已更新（image 对象、entrypoint、resourceLimits）
4. ✅ timeout 最小值限制已添加（60秒）

### 核心问题
**标准 Docker 镜像缺少 `/execd` 文件**

OpenSandbox 要求容器镜像中包含 `/execd` 可执行文件，但标准镜像（python:3.11, alpine 等）不包含此文件。

## 解决方案

### 步骤 1: 在虚拟机上构建兼容镜像

SSH 到虚拟机（192.168.137.13），执行以下命令：

```bash
# 1. 创建 Dockerfile
cat > /lilin/EasyRAG/Dockerfile.python-opensandbox << 'EOF'
FROM python:3.11-slim

# 安装依赖
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

# 创建模拟的 execd（因为官方下载链接可能失败）
RUN echo '#!/bin/sh' > /execd && \
    echo 'exec "$@"' >> /execd && \
    chmod +x /execd

# 安装常用 Python 包
RUN pip install --no-cache-dir numpy pandas requests httpx

WORKDIR /workspace
CMD ["python"]
EOF

# 2. 构建镜像
cd /lilin/EasyRAG
docker build -t easyrag-python-opensandbox:3.11 -f Dockerfile.python-opensandbox .

# 3. 验证镜像
docker run --rm easyrag-python-opensandbox:3.11 python -c "print('OK')"
```

### 步骤 2: 配置后端

在 `.env` 文件中添加：

```bash
opensandbox_api_key=easyrag2026
opensandbox_image=easyrag-python-opensandbox:3.11
```

### 步骤 3: 测试

```bash
cd backend
uv run python ../test_skill_tool_creation.py
```

## 正确的 API 格式

### 创建沙箱

**请求**:
```http
POST /sandboxes HTTP/1.1
Host: 192.168.137.13:8090
OPEN-SANDBOX-API-KEY: easyrag2026
Content-Type: application/json

{
  "image": {"uri": "easyrag-python-opensandbox:3.11"},
  "entrypoint": ["python", "-c", "print('Hello')"],
  "resourceLimits": {
    "cpu": "500m",
    "memory": "512Mi"
  },
  "timeout": 60
}
```

**响应** (202 Accepted):
```json
{
  "id": "sb_xxx",
  "status": {
    "state": "Creating"
  }
}
```

### 获取日志

**请求**:
```http
GET /sandboxes/{id}/diagnostics/logs HTTP/1.1
Host: 192.168.137.13:8090
OPEN-SANDBOX-API-KEY: easyrag2026
```

**响应**:
```json
{
  "stdout": "Hello\n",
  "stderr": ""
}
```

## 已修改的文件

1. `backend/app/providers/sandbox/opensandbox_client.py` - 更新 API 格式
2. `backend/app/providers/sandbox/__init__.py` - 使用配置镜像
3. `backend/app/config.py` - 添加 opensandbox_image 配置
4. `backend/.env` - 添加镜像配置

## 测试验证

运行以下测试验证集成：

```bash
# 1. 测试 API 连接
python test_findings_format.py

# 2. 测试技能工具创建
cd backend
uv run python ../test_skill_tool_creation.py

# 3. 测试完整的技能执行
uv run python ../test_skill_double_wrap.py
```

## 预期结果

技能脚本应该正确执行：
- 输入: "计算 1+100"
- 输出: "1 + 100 = 201"（包含 +100 的测试逻辑）