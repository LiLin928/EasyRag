# 技能脚本执行修复完成报告

## 问题诊断

### 原始问题
用户设置"最后多加100"测试，但返回 `1 + 100 = 1011 + 100 = 101`，脚本未正确执行。

### 根本原因
1. **双重包装问题**：`skill_tool_executor.py` 和 `script_executor.py` 都包装脚本
2. **模块导入问题**：`script_executor.py` 使用 `json.dumps` 但未导入 `json`
3. **沙箱认证问题**：OpenSandbox 使用特定的头部名称
4. **API 格式问题**：请求格式与 OpenSandbox API 不匹配
5. **镜像问题**：标准 Docker 镜像缺少 `/execd` 文件

## 已完成的修复

### 1. 移除双重包装
- 文件：`backend/app/core/agent/skill_tool_executor.py`
- 修改：移除 `_wrap_script_with_auto_call()` 调用
- 效果：脚本只被包装一次

### 2. 修复模块导入
- 文件：`backend/app/core/skills/script_executor.py`
- 修改：添加 `import json`
- 效果：脚本可以正确序列化

### 3. 修复沙箱认证
- 文件：`backend/app/providers/sandbox/opensandbox_client.py`
- 修改：使用 `OPEN-SANDBOX-API-KEY` 头部
- 效果：认证通过

### 4. 修正 API 格式
- 文件：`backend/app/providers/sandbox/opensandbox_client.py`
- 修改：
  - `image` 从字符串改为对象：`{"uri": "..."}`
  - `command` 改为 `entrypoint`
  - `resources` 改为 `resourceLimits`
  - 添加 `timeout` 最小值 60 秒
  - 资源格式改为字符串：`"500m"`, `"512Mi"`
- 效果：符合 OpenSandbox API 规范

### 5. 添加镜像配置
- 文件：`backend/app/config.py`
- 新增：`opensandbox_image` 配置项
- 默认值：`easyrag-python-opensandbox:3.11`

### 6. 更新技能脚本
- 文件：数据库 `skills` 表
- 修改：合并为单个带 `main()` 函数的完整脚本
- 效果：脚本可以正确执行

## 待完成的操作

### 在虚拟机上构建镜像

**必须完成此步骤才能使用 OpenSandbox**

SSH 到虚拟机（192.168.137.13）：

```bash
# 1. 创建 Dockerfile
cat > /lilin/EasyRAG/Dockerfile.python-opensandbox << 'EOF'
FROM python:3.11-slim

RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

# 创建 execd（OpenSandbox 要求）
RUN echo '#!/bin/sh' > /execd && \
    echo 'exec "$@"' >> /execd && \
    chmod +x /execd

RUN pip install --no-cache-dir numpy pandas requests httpx

WORKDIR /workspace
CMD ["python"]
EOF

# 2. 构建镜像
cd /lilin/EasyRAG
docker build -t easyrag-python-opensandbox:3.11 -f Dockerfile.python-opensandbox .

# 3. 验证
docker run --rm easyrag-python-opensandbox:3.11 python -c "print('OK')"
```

## 测试验证

构建镜像后，运行测试：

```bash
cd backend
uv run python ../test_skill_complete_flow.py
```

**预期结果**：
- 输入：`计算 1+100`
- 输出：`1 + 100 = 201`（正确执行 +100 测试逻辑）

## 文件修改列表

### 后端文件
1. `backend/app/core/agent/skill_tool_executor.py` - 移除双重包装
2. `backend/app/core/skills/script_executor.py` - 添加 json 导入
3. `backend/app/providers/sandbox/opensandbox_client.py` - 修正 API 格式
4. `backend/app/providers/sandbox/__init__.py` - 使用配置镜像
5. `backend/app/config.py` - 添加镜像配置
6. `backend/.env` - 添加配置

### 新增文件
1. `deploy/Dockerfile.python-opensandbox` - OpenSandbox 兼容镜像
2. `docs/opensandbox-integration.md` - 集成说明文档
3. `test_skill_complete_flow.py` - 完整测试脚本

## 技术细节

### OpenSandbox API 正确格式

```json
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

### 技能脚本格式

```python
def main(inputs):
    # 处理逻辑
    return {"result": "..."}
```

## 下一步

1. ✅ 修复代码问题（已完成）
2. ⏳ 在虚拟机构建镜像（待执行）
3. ⏳ 运行测试验证（待执行）
4. ⏳ 前端集成测试（待执行）

## 参考

- OpenSandbox 官方文档：https://github.com/opensandbox-group/OpenSandbox
- 集成说明：`docs/opensandbox-integration.md`
- API 规范：OpenSandbox `/openapi.json` 端点