# OpenSandbox 技能脚本执行 - 快速启动指南

## 当前状态

### ✅ 已完成
- 代码修复完成
- API 格式正确
- 认证配置完成
- 测试脚本准备就绪

### ❌ 待解决
- OpenSandbox 镜像缺少 `/execd` 文件
- 需要在虚拟机上构建兼容镜像

## 立即操作步骤

### 步骤 1: SSH 到虚拟机

```bash
ssh lilin@192.168.137.13
```

### 步骤 2: 创建并构建镜像

```bash
# 进入工作目录
cd /lilin/EasyRAG

# 创建 Dockerfile
cat > Dockerfile.python-opensandbox << 'EOF'
FROM python:3.11-slim

# 安装 wget
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

# 创建 execd（OpenSandbox 要求）
RUN echo '#!/bin/sh' > /execd && \
    echo 'exec "$@"' >> /execd && \
    chmod +x /execd

# 安装常用 Python 包
RUN pip install --no-cache-dir numpy pandas requests httpx

WORKDIR /workspace
CMD ["python"]
EOF

# 构建镜像
docker build -t easyrag-python-opensandbox:3.11 -f Dockerfile.python-opensandbox .

# 验证镜像
docker run --rm easyrag-python-opensandbox:3.11 python -c "print('镜像构建成功')"
```

### 步骤 3: 验证 OpenSandbox

```bash
# 测试创建沙箱
curl -X POST http://localhost:8090/sandboxes \
  -H "OPEN-SANDBOX-API-KEY: easyrag2026" \
  -H "Content-Type: application/json" \
  -d '{
    "image": {"uri": "easyrag-python-opensandbox:3.11"},
    "entrypoint": ["python", "-c", "print(\"Hello OpenSandbox\")"],
    "resourceLimits": {"cpu": "500m", "memory": "512Mi"},
    "timeout": 60
  }'
```

预期返回：
```json
{
  "id": "sb_xxx",
  "status": {"state": "Creating"}
}
```

### 步骤 4: 在本机运行测试

```bash
cd D:/4-MyProject/EasyRag/backend
uv run python ../test_skill_complete_flow.py
```

预期结果：
```
[OK] 服务健康
[OK] 工具创建成功: skill_unnamed
[结果]
[SKILL 数字相加计算]
...

脚本执行结果:
✓ 数字相加.py: {"numbers": [1.0, 100.0], "total": 201.0, "result": "1.0 + 100.0 = 201"}

[OK] 测试通过：正确计算了 1+100+100=201
```

## 故障排查

### 问题 1: 镜像构建失败
```bash
# 检查 Docker 是否运行
docker ps

# 检查磁盘空间
df -h

# 查看构建日志
docker build -t easyrag-python-opensandbox:3.11 -f Dockerfile.python-opensandbox . --no-cache
```

### 问题 2: OpenSandbox 返回 500
```bash
# 查看 OpenSandbox 日志
docker logs easyrag-opensandbox-server

# 重启 OpenSandbox
docker restart easyrag-opensandbox-server
```

### 问题 3: 测试失败
```bash
# 检查网络连接
curl http://192.168.137.13:8090/health

# 检查 API Key
grep opensandbox_api_key backend/.env
```

## 成功标志

当看到以下输出时，表示所有问题已解决：

```
================================================================================
测试总结
================================================================================
OpenSandbox 服务: OK
技能脚本执行: OK

所有测试通过！技能脚本执行正常工作。
```

## 下一步

1. ✅ 前端测试：在前端界面测试"计算 1+100"
2. ✅ 添加更多技能脚本
3. ✅ 性能优化和监控

## 联系支持

如遇到问题，请查看：
- 完整文档：`docs/opensandbox-integration.md`
- 修复报告：`SKILL_SCRIPT_FIX_REPORT.md`
- 测试脚本：`test_skill_complete_flow.py`