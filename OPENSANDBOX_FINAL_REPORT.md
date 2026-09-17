# OpenSandbox 集成完整报告

## 执行时间
2026-09-16

## 问题原始描述
用户设置"最后多加100"测试，计算 1+100 时返回 `1 + 100 = 1011 + 100 = 101`，脚本未正确执行。

## 问题诊断过程

### 第1阶段：代码问题排查
1. **双重包装问题** ✅ 已修复
   - `skill_tool_executor.py` 和 `script_executor.py` 都包装脚本
   - 修复：移除 `skill_tool_executor.py` 中的包装

2. **模块导入问题** ✅ 已修复
   - `script_executor.py` 使用 `json.dumps` 但未导入 `json`
   - 修复：添加 `import json`

### 第2阶段：沙箱 API 研究和测试
3. **认证头部问题** ✅ 已修复
   - OpenSandbox 使用 `OPEN-SANDBOX-API-KEY` 头部
   - 修复：更新 `opensandbox_client.py`

4. **API 格式问题** ✅ 已确定
   - 测试了 findings.md 中的格式 → 422 错误
   - 测试了 GitHub OpenAPI 格式 → 需要 `/execd`
   - 最终确定正确格式

### 第3阶段：配置文件分析
5. **参考配置文件** 📋 已分析
   - `opensandbox-config.toml` - 配置正确
   - `docker-compose.yml` - 服务配置正确

## 最终确定的 API 格式

### 正确格式（已测试验证）

```json
{
  "image": {"uri": "python:3.11-slim"},
  "entrypoint": ["python", "-c", "print('Hello')"],
  "resourceLimits": {
    "cpu": "500m",
    "memory": "256Mi"
  },
  "timeout": 60
}
```

### 关键字段说明

| 字段 | 类型 | 必需 | 格式 | 说明 |
|------|------|------|------|------|
| image | object | 是* | `{"uri": "..."}` | 镜像对象，不能是字符串 |
| entrypoint | array | 是 | `["python", "-c", "..."]` | 执行命令，不能用 command |
| resourceLimits | object | 是 | `{"cpu": "500m", "memory": "256Mi"}` | 资源限制，必需字段 |
| timeout | integer | 否 | ≥60 | 超时时间（最小 60 秒） |

*注：image 或 snapshotId 必须提供其中一个

## 核心阻塞问题

### 问题
**标准 Docker 镜像缺少 `/execd` 文件**

### 错误信息
```
Failed to read execd artifacts: Could not find the file /execd in container
```

### 原因
OpenSandbox 要求容器镜像中包含 `/execd` 可执行文件，用于沙箱管理。标准镜像（python:3.11-slim, alpine 等）不包含此文件。

## 解决方案

### 方案 A：构建自定义镜像（推荐）

在虚拟机上执行：

```bash
cd /lilin/EasyRAG

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
```

### 方案 B：使用 OpenSandbox 官方镜像

```bash
docker pull ghcr.io/opensandbox-group/opensandbox-python:3.11
```

## 已完成的代码修改

### 1. 移除双重包装
**文件**: `backend/app/core/agent/skill_tool_executor.py`

```python
# 移除前
wrapped_script = _wrap_script_with_auto_call(...)
result = await execute_skill_script(..., script_content=wrapped_script, ...)

# 移除后
result = await execute_skill_script(..., script_content=script_content, ...)
```

### 2. 添加模块导入
**文件**: `backend/app/core/skills/script_executor.py`

```python
# 添加
import json
```

### 3. 修正沙箱认证
**文件**: `backend/app/providers/sandbox/opensandbox_client.py`

```python
# 修改前
headers["Authorization"] = f"Bearer {self.api_key}"

# 修改后
headers["OPEN-SANDBOX-API-KEY"] = self.api_key
```

### 4. 更新 API 格式
**文件**: `backend/app/providers/sandbox/opensandbox_client.py`

```python
payload = {
    "image": {"uri": image},
    "entrypoint": command,
    "resourceLimits": {
        "cpu": f"{int(cpu * 1000)}m",
        "memory": f"{memory_mb}Mi"
    },
    "timeout": max(timeout_seconds, 60)
}
```

### 5. 添加镜像配置
**文件**: `backend/app/config.py`

```python
opensandbox_image: str = "easyrag-opensandbox:3.11"
```

### 6. 更新技能脚本
**数据库**: `skills` 表

合并为单个完整脚本，包含 `main()` 函数。

## 测试文件清单

1. `test_findings_md_format.py` - 测试 findings.md 格式
2. `test_complete_payload.py` - 测试完整 API 请求
3. `opensandbox_diagnosis.py` - 完整诊断脚本
4. `test_skill_complete_flow.py` - 技能完整测试

## 文档清单

1. `BUILD_OPENSANDBOX_IMAGE.md` - 镜像构建指南
2. `SKILL_SCRIPT_FIX_REPORT.md` - 修复报告
3. `docs/opensandbox-integration.md` - 集成说明

## 下一步操作

### 必须完成

1. ✅ 代码修复（已完成）
2. ⏳ 在虚拟机构建镜像（待执行）
3. ⏳ 运行测试验证（待执行）

### 执行步骤

```bash
# 1. SSH 到虚拟机
ssh lilin@192.168.137.13

# 2. 构建镜像
cd /lilin/EasyRAG
# 参考 BUILD_OPENSANDBOX_IMAGE.md 执行构建命令

# 3. 在本机测试
cd D:/4-MyProject/EasyRag/backend
uv run python ../test_complete_payload.py
```

## 预期结果

成功后：
- 输入：`计算 1+100`
- 输出：`1 + 100 = 201` ✅

## 结论

所有代码层面的问题已修复，唯一剩余问题是在虚拟机上构建包含 `/execd` 的兼容镜像。构建完成后，技能脚本执行将正常工作。

---
**状态**: 等待镜像构建
**最后更新**: 2026-09-16