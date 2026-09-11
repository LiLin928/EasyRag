"""
诊断脚本：验证 DOC 文件解析问题

目的：通过添加诊断日志，确认文件格式和解析器选择
"""
import sys
sys.path.insert(0, '.')
from app.core.parser.dispatcher import DocumentDispatcher
from app.core.file_validator import detect_file_type
import asyncio

async def diagnose_doc_parsing():
    """诊断 DOC 文件解析"""

    # 模拟 .doc 文件（OLE 格式）
    # Magic number: D0 CF 11 E0
    fake_doc_content = bytes([
        0xD0, 0xCF, 0x11, 0xE0,  # OLE magic
        0xA1, 0xB1, 0x1A, 0xE1,
    ]) + b'\x00' * 100  # 填充

    # 模拟 .docx 文件（ZIP 格式）
    # Magic number: 50 4B 03 04
    fake_docx_content = bytes([
        0x50, 0x4B, 0x03, 0x04,  # ZIP magic
    ]) + b'\x00' * 100

    print("=" * 60)
    print("诊断测试：文件格式检测")
    print("=" * 60)

    # 测试 1: 检测 .doc 文件
    print("\n测试 1: .doc 文件")
    print(f"文件名: test.doc")
    print(f"Magic bytes: {fake_doc_content[:8].hex().upper()}")

    detected_type = detect_file_type(fake_doc_content)
    print(f"检测到的类型: {detected_type}")

    dispatcher = DocumentDispatcher()

    # 尝试获取解析器
    print("\n尝试获取解析器:")
    try:
        parser = dispatcher._get_parser_for_extension('doc')
        print(f"[OK] 解析器: {parser.__class__.__name__}")
        print(f"  问题: DOCXParser 不能处理 OLE 格式!")
    except Exception as e:
        print(f"[ERROR] 错误: {e}")

    # 测试 2: 检测 .docx 文件
    print("\n" + "-" * 60)
    print("\n测试 2: .docx 文件")
    print(f"文件名: test.docx")
    print(f"Magic bytes: {fake_docx_content[:8].hex().upper()}")

    detected_type = detect_file_type(fake_docx_content)
    print(f"检测到的类型: {detected_type}")

    print("\n尝试获取解析器:")
    try:
        parser = dispatcher._get_parser_for_extension('docx')
        print(f"[OK] 解析器: {parser.__class__.__name__}")
        print(f"  正确: DOCXParser 可以处理 ZIP 格式")
    except Exception as e:
        print(f"[ERROR] 错误: {e}")

    print("\n" + "=" * 60)
    print("根本原因:")
    print("=" * 60)
    print("dispatcher.py 第 27 行:")
    print("  'doc': DOCXParser,  # 转换为 docx")
    print("\n问题:")
    print("  1. 注释说'转换为 docx'，但转换代码并未实现")
    print("  2. DOCXParser 只能处理 .docx (ZIP)，不能处理 .doc (OLE)")
    print("\n解决方案:")
    print("  A. 添加 .doc → .docx 转换逻辑")
    print("  B. 使用 textract 库（支持 .doc）")
    print("  C. 移除 'doc' 映射，明确告知用户只支持 .docx")

if __name__ == "__main__":
    asyncio.run(diagnose_doc_parsing())