# DOCX 文档结构缺失问题分析报告

**文档 ID**: 84951e54-b1d5-41a1-82d8-9b1d1fafb2b2
**文档名称**: 招标文件-某某医院直流电源采购项目.docx
**调查时间**: 2026-09-11

---

## 📊 文档状态

| 项目 | 值 | 状态 |
|------|------|------|
| 文件大小 | 453.6 KB | - |
| 解析状态 | done | ✓ |
| 元素数量 | 22 | ⚠️ |
| 分块数量 | 67 | ✓ |
| 元素类型 | 全部 paragraph | ❌ |
| 树节点数量 | 20+ | ⚠️ |
| 树节点层级 | 全部 Level 1 | ❌ |

---

## 🚨 问题表现

### 1. 元素类型错误

**实际元素**:
```
1. [paragraph] 中国石化销售有限公司
2. [paragraph] 某某医院直流电源采购项目
3. [paragraph] 招标文件
4. [paragraph] 项目编号：XDGY-1732-2026-0092
...
```

**期望元素**:
```
1. [heading] 中国石化销售有限公司
2. [heading] 某某医院直流电源采购项目
3. [heading] 招标文件
...
```

### 2. 树节点层级错误

**实际树节点**:
```
[Level 1] 第一章 招标公告	2
[Level 1] 第二章 投标人须知	6
[Level 1] 第三章 评标办法（综合评估法）	26
```

**问题**:
- ❌ 所有节点都是 Level 1
- ❌ 没有层级结构
- ❌ 标题包含页码（\t2）

---

## 🔍 根本原因

### 原因 1: DOCX 解析器标题识别不完整

**当前识别逻辑**（`docx_parser.py` 第 98-110 行）:

```python
def _determine_element_type(self, para) -> str:
    """判断段落类型"""
    style_name = para.style.name if para.style else ''

    # 标题样式判断
    if 'Heading' in style_name or 'Title' in style_name:
        return 'heading'

    # 列表判断
    if para.style and 'List' in style_name:
        return 'list'

    return 'paragraph'
```

**问题**:
- ❌ 只识别英文样式名 `Heading`、`Title`
- ❌ 不识别中文样式名 `标题`、`标题 1`
- ❌ 不识别其他常见标题样式

### 原因 2: 文档可能使用自定义样式

**可能情况**:
1. 文档使用中文 Word 样式（如"标题 1"、"标题 2"）
2. 文档使用自定义样式（如"章标题"、"节标题"）
3. 文档通过格式（字体大小、加粗）而非样式来表示标题

---

## 💡 解决方案

### 方案 A: 增强样式识别（推荐）

**修改 `docx_parser.py`**:

```python
def _determine_element_type(self, para) -> str:
    """判断段落类型

    增强标题识别，支持：
    1. 英文样式：Heading 1, Heading 2, Title
    2. 中文样式：标题, 标题 1, 标题 2
    3. 编号标题：第一章, 一、, 1. 等（通过正则）
    """
    style_name = para.style.name if para.style else ''

    # 标题样式判断（增强版）
    heading_keywords = [
        'Heading', 'Title',  # 英文
        '标题', '标题 1', '标题 2', '标题 3',  # 中文
        'Heading 1', 'Heading 2', 'Heading 3',  # 标准英文
        'TOC Heading',  # 目录标题
    ]

    for keyword in heading_keywords:
        if keyword.lower() in style_name.lower():
            return 'heading'

    # 列表判断
    if para.style and 'List' in style_name:
        return 'list'

    # 基于内容的标题识别（新增）
    text = para.text.strip()
    if self._is_heading_by_content(text):
        return 'heading'

    return 'paragraph'


def _is_heading_by_content(self, text: str) -> bool:
    """基于内容判断是否为标题

    识别模式：
    1. 中文编号：第一章、第二章...
    2. 数字编号：一、二、三...
    3. 阿拉伯编号：1. 2. 3.（独立行）
    """
    import re

    if not text or len(text) > 100:
        return False

    # 第一章、第二章
    if re.match(r'^第[一二三四五六七八九十百]+[章节条款]', text):
        return True

    # 一、二、三、
    if re.match(r'^[一二三四五六七八九十]+、', text):
        return True

    # 1. 2. 3.（独立数字编号）
    if re.match(r'^\d+\.\s+\S', text) and len(text.split()) <= 10:
        return True

    return False
```

**优点**:
- ✓ 支持中英文样式
- ✓ 支持内容识别
- ✓ 提高标题识别率

**实施时间**: 30 分钟

---

### 方案 B: 使用格式分析（进阶）

**基于字体格式判断标题**:

```python
def _determine_element_type_by_format(self, para) -> str:
    """基于格式判断段落类型

    分析：
    - 字体大小（大字号可能是标题）
    - 是否加粗
    - 是否居中
    - 段落间距
    """
    if not para.runs:
        return 'paragraph'

    # 检查第一个 run 的格式
    first_run = para.runs[0]

    # 字体大小检测
    if first_run.font.size and first_run.font.size.pt >= 16:
        return 'heading'

    # 加粗检测
    if first_run.font.bold and len(para.text.strip()) <= 50:
        return 'heading'

    # ... 其他规则

    return 'paragraph'
```

**优点**:
- ✓ 不依赖样式
- ✓ 适用于无样式文档

**缺点**:
- ✗ 可能误判
- ✗ 需要调优参数

---

## 📝 推荐行动计划

### 立即行动（方案 A）

1. **修改 `docx_parser.py`**
   - 增强标题样式识别
   - 添加内容识别逻辑

2. **测试验证**
   - 使用实际文档测试
   - 验证标题识别率

3. **重新解析**
   - 删除现有解析结果
   - 重新上传文档

### 后续优化

4. **添加更多识别规则**
   - 支持更多样式名
   - 优化正则匹配

5. **考虑格式分析**
   - 实施方案 B
   - 作为样式识别的补充

---

## 🎯 预期效果

**修复前**:
```
元素类型：22 个 paragraph
树节点层级：全部 Level 1
文档结构：无
```

**修复后**:
```
元素类型：5-10 个 heading + 12-17 个 paragraph
树节点层级：多层级（Level 1-3）
文档结构：完整
```

---

## 📁 相关文件

- 解析器：`backend/app/core/parser/docx_parser.py`
- 树构建器：`backend/app/core/parser/tree_builder.py`
- 测试：`backend/tests/test_parser/test_docx_parser.py`

---

**结论**：DOCX 解析器的标题识别逻辑不完整，导致无法正确识别标题，进而导致文档结构缺失。

**优先级**：高（影响文档检索和用户体验）

**实施时间**：30 分钟（方案 A）