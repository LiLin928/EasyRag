# DOC 文件解析问题调查报告

**日期**: 2026-09-11
**方法**: Systematic Debugging (Superpowers)
**调查人**: Claude Code Agent

---

## 📋 问题摘要

用户报告了两个问题：
1. **Markdown 文件按行显示元素** - 预期应该是按标题/段落分块
2. **DOC 文件解析失败** - 错误信息：`File is not a zip file`

---

## 🔬 Phase 1: Root Cause Investigation（根本原因调查）

### 问题 1: Markdown 按行显示

**调查步骤：**
1. ✅ 阅读 `markdown_parser.py` 源码
2. ✅ 发现段落合并逻辑（`current_paragraph_lines` + `flush_paragraph()`）
3. ✅ 实际测试验证

**测试结果：**
```
输入：3 行段落文本
输出：1 个 paragraph 元素（合并）

元素总数：8（非按行的 12+）
```

**根本原因：**
- **Markdown 解析器逻辑正确**，按段落合并
- 可能原因：
  1. 用户误解（看到元素列表，误以为"按行"）
  2. 前端显示问题
  3. 特定文档缺少空行分段

**建议：** 检查实际文档内容和前端显示逻辑

---

### 问题 2: DOC 文件解析失败 ⚠️

**调查步骤：**
1. ✅ 错误信息：`BadZipFile: File is not a zip file`
2. ✅ 查看 `dispatcher.py` 第 27 行
3. ✅ 文件格式分析（Magic Number）
4. ✅ 依赖库调研

**根本原因：**
```
┌─────────────────────────────────────────┐
│ dispatcher.py 第 27 行                  │
│ 'doc': DOCXParser, # 转换为 docx       │
│                                         │
│ 注释说"转换"，但转换代码未实现！        │
└─────────────────────────────────────────┘

错误链：
.doc (OLE 格式: D0 CF 11 E0)
  → dispatcher 选择 DOCXParser
  → DOCXParser 使用 python-docx
  → python-docx 期望 ZIP 格式
  → BadZipFile 错误 ❌
```

**技术细节：**
- `.doc` = Word 97-2003（OLE Compound Document）
- `.docx` = Office Open XML（ZIP 压缩的 XML）
- `python-docx` 只支持 `.docx`

---

## 🔍 Phase 2: Pattern Analysis（模式分析）

**现有解决方案调研：**

| 方案 | 库/工具 | 平台 | 格式保留 |
|------|---------|------|----------|
| textract | textract + antiword | 跨平台 | 纯文本 |
| pywin32 | Microsoft Word COM | Windows | 完整 |
| LibreOffice | unoconv | Linux | 完整 |

**项目现状：**
- 环境：Windows 本机 + Linux 虚拟机
- 部署目标：虚拟机（192.168.137.13）
- 当前依赖：`python-docx>=1.1`

---

## 💡 Phase 3: Hypothesis and Testing（假设与验证）

### 假设

**假设 1**: dispatcher.py 第 27 行是未实现的功能
- ✅ 已验证：通过诊断脚本确认

**假设 2**: 可以通过添加转换逻辑修复
- ⚠️ 需要评估方案

---

## 🎯 Phase 4: Implementation（解决方案）

### **推荐方案：分阶段实施**

#### **阶段 1: 立即修复（方案 A）**

**目标：** 快速修复，避免用户混淆

**操作：**
```python
# dispatcher.py
PARSER_MAP: Dict[str, Type[BaseParser]] = {
    'pdf': PDFParser,
    'docx': DOCXParser,
    # 移除 'doc': DOCXParser
    'xlsx': XLSXParser,
    # ...
}

# 添加友好的错误提示
def _get_parser_for_extension(self, ext: str) -> BaseParser:
    if ext == 'doc':
        raise ValueError(
            "不支持 Word 97-2003 格式（.doc），"
            "请转换为 .docx 格式后再上传"
        )
```

**优点：**
- ✓ 立即修复错误
- ✓ 清晰的用户提示
- ✓ 无需额外依赖

**实施时间：** 5 分钟

---

#### **阶段 2: 完整支持（方案 B - 推荐）**

**目标：** 在虚拟机上添加 .doc 支持

**操作：**
1. 安装依赖：
   ```bash
   # 虚拟机
   sudo apt-get install antiword
   ```

2. 添加 Python 依赖：
   ```toml
   # pyproject.toml
   dependencies = [
     # ...
     "textract>=1.6.5",
   ]
   ```

3. 创建 `doc_parser.py`（见 `solution_B_textract_support.md`）

4. 更新 `dispatcher.py`

**优点：**
- ✓ 完整支持 .doc
- ✓ 跨平台
- ✓ 适合服务器环境

**实施时间：** 1-2 小时

---

### **可选方案 C: Windows + Word COM**

**适用场景：** Windows 环境 + 已安装 Microsoft Word

**操作：** 见 `solution_C_win32_support.md`

**优点：**
- ✓ 最完整的 .doc 支持
- ✓ 保留格式

**缺点：**
- ✗ 仅 Windows
- ✗ 需要安装 Word
- ✗ 性能较低

---

## 📊 方案对比表

| 方案 | 复杂度 | 平台 | 格式保留 | 推荐度 |
|------|--------|------|----------|--------|
| A: 移除 .doc | 低 | 跨平台 | - | ⭐⭐⭐⭐⭐（临时）|
| B: textract | 中 | 跨平台 | 纯文本 | ⭐⭐⭐⭐（长期）|
| C: pywin32 | 中 | Windows | 完整 | ⭐⭐⭐（仅 Windows）|

---

## 🚀 实施建议

### **立即行动**

1. **执行方案 A**（立即修复）
   ```bash
   # 修改 dispatcher.py
   # 移除 'doc' 映射
   # 添加错误提示
   ```

2. **通知用户**
   - 更新 API 文档
   - 前端提示："仅支持 .docx，不支持 .doc"

### **后续优化**

3. **实施方案 B**（虚拟机上）
   - 安装 antiword
   - 添加 textract 依赖
   - 创建 DOCParser

4. **测试验证**
   - 准备测试用例
   - 验证解析结果

---

## 📁 相关文档

- 方案 A 详细实施：`backend/docs/solution_A_remove_doc_support.md`
- 方案 B 详细实施：`backend/docs/solution_B_textract_support.md`
- 方案 C 详细实施：`backend/docs/solution_C_win32_support.md`
- 诊断脚本：`backend/diagnose_doc_issue.py`

---

## 🎓 经验教训

1. **注释不是实现**：注释说"转换为 docx"，但代码未实现
2. **依赖库限制**：python-docx 只支持 .docx，不支持 .doc
3. **文件格式差异**：.doc (OLE) vs .docx (ZIP) 是完全不同的格式
4. **系统化调试**：遵循 Phase 1-4 流程，快速定位根本原因

---

## ✅ 验证清单

- [x] 根本原因已确认
- [x] 诊断脚本已创建
- [x] 解决方案已提供（A/B/C）
- [ ] 方案 A 已实施
- [ ] 测试用例已添加
- [ ] API 文档已更新
- [ ] 用户通知已发送

---

**报告完成时间**: 2026-09-11 14:30
**预计修复时间**: 方案 A（5 分钟） / 方案 B（1-2 小时）
**优先级**: 高（阻塞用户上传 .doc 文件）