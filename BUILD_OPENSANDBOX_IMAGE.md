# OpenSandbox 镜像构建指南

## 问题确认

- ✅ API 格式正确
- ✅ 认证正常
- ✅ 服务运行正常
- ❌ 镜像缺少 `/execd` 文件

## 解决方案：构建兼容镜像

### 步骤 1: SSH 到虚拟机

```bash
ssh lilin@192.168.137.13
```

### 步骤 2: 创建 Dockerfile

```bash
cd /lilin/EasyRAG

cat > Dockerfile.opensandbox << 'EOF'
FROM python:3.11-slim

# 安装 wget
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

# 创建 execd（OpenSandbox 要求）
# 方法1: 尝试下载官方 execd
RUN wget -O /execd https://github.com/opensandbox-group/OpenSandbox/releases/download/v0.1.0/execd-linux-amd64 || \
    # 方法2: 如果下载失败，创建简单的包装脚本
    (echo '#!/bin/sh' > /execd && echo 'exec "$@"' >> /execd)

RUN chmod +x /execd

# 安装常用 Python 包
RUN pip install --no-cache-dir \
    numpy \
    pandas \
    requests \
    httpx

WORKDIR /workspace
CMD ["python"]
EOF
```

### 步骤 3: 构建镜像

```bash
docker build -t easyrag-opensandbox:3.11 -f Dockerfile.opensandbox .
```

### 步骤 4: 验证镜像

```bash
# 测试镜像
docker run --rm easyrag-opensandbox:3.11 python -c "print('镜像构建成功')"

# 验证 execd 文件
docker run --rm easyrag-opensandbox:3.11 ls -la /execd
```

预期输出：
```
-rwxr-xr-x 1 root root 1234567 /execd
```

### 步骤 5: 更新后端配置

在 `.env` 文件中添加：

```bash
opensandbox_image=easyrag-opensandbox:3.11
```

### 步骤 6: 更新后端代码

在 `backend/app/providers/sandbox/__init__.py` 中：

```python
# 修改前
image = "python:3.10-alpine"

# 修改后
from app.config import settings
image = settings.opensandbox_image
```

### 步骤 7: 测试

```bash
cd D:/4-MyProject/EasyRag/backend
uv run python ../test_complete_payload.py
```

## 一键脚本

```bash
# 在虚拟机上执行此脚本
cd /lilin/EasyRAG

cat > build-opensandbox-image.sh << 'SCRIPT'
#!/bin/bash
set -e

echo "构建 OpenSandbox 兼容镜像..."

cat > Dockerfile.opensandbox << 'EOF'
FROM python:3.11-slim

RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

RUN wget -O /execd https://github.com/opensandbox-group/OpenSandbox/releases/download/v0.1.0/execd-linux-amd64 || \
    (echo '#!/bin/sh' > /execd && echo 'exec "\$@"' >> /execd)

RUN chmod +x /execd

RUN pip install --no-cache-dir numpy pandas requests httpx

WORKDIR /workspace
EOF

docker build -t easyrag-opensandbox:3.11 -f Dockerfile.opensandbox .

echo "验证镜像..."
docker run --rm easyrag-opensandbox:3.11 ls -la /execd

echo "构建完成！"
SCRIPT

chmod +x build-opensandbox-image.sh
./build-opensandbox-image.sh
```

## 预期结果

成功后，测试输出：

```
状态码: 202
[成功] 沙箱创建成功！
沙箱 ID: sb_xxx

输出:
  stdout: Hello from EasyRAG
  stderr:

沙箱已清理
```