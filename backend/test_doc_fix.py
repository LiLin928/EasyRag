"""
测试方案 A：验证 .doc 文件错误提示

目的：
1. 确认 .doc 文件会抛出友好的错误信息
2. 确认 .docx 文件正常工作
"""
import sys
sys.path.insert(0, '.')
from app.core.parser.dispatcher import DocumentDispatcher
import asyncio


async def test_doc_file_error():
    """测试 .doc 文件会抛出正确的错误"""

    print("=" * 60)
    print("测试 1: 验证 .doc 文件错误提示")
    print("=" * 60)

    dispatcher = DocumentDispatcher()

    # 测试 .doc 文件
    try:
        parser = dispatcher._get_parser_for_extension('doc')
        print("[失败] 不应该执行到这里")
    except ValueError as e:
        error_msg = str(e)
        print(f"[成功] 捕获到预期的错误:")
        print(f"  错误信息: {error_msg}")

        # 验证错误信息是否友好
        if "Word 97-2003" in error_msg and ".docx" in error_msg:
            print("  [验证通过] 错误信息包含转换建议")
        else:
            print("  [验证失败] 错误信息不够友好")

    print("\n" + "=" * 60)
    print("测试 2: 验证 .docx 文件正常工作")
    print("=" * 60)

    # 测试 .docx 文件
    try:
        parser = dispatcher._get_parser_for_extension('docx')
        print(f"[成功] 获取到解析器: {parser.__class__.__name__}")
        print("  [验证通过] .docx 文件正常支持")
    except Exception as e:
        print(f"[失败] 意外错误: {e}")

    print("\n" + "=" * 60)
    print("测试 3: 验证其他文件类型")
    print("=" * 60)

    # 测试其他支持的格式
    supported_formats = ['pdf', 'xlsx', 'xls', 'md', 'markdown', 'txt']

    for ext in supported_formats:
        try:
            parser = dispatcher._get_parser_for_extension(ext)
            print(f"  {ext:10} -> {parser.__class__.__name__}")
        except Exception as e:
            print(f"  {ext:10} -> [错误] {e}")

    print("\n" + "=" * 60)
    print("测试 4: 验证完整调度流程")
    print("=" * 60)

    # 模拟 .doc 文件上传
    fake_doc_content = bytes([
        0xD0, 0xCF, 0x11, 0xE0,  # OLE magic
        0xA1, 0xB1, 0x1A, 0xE1,
    ]) + b'\x00' * 100

    try:
        result = await dispatcher._dispatch_from_data(
            fake_doc_content,
            'test.doc',
            'test-doc-id'
        )
        print("[失败] 不应该执行到这里")
    except ValueError as e:
        print(f"[成功] 调度器正确拒绝 .doc 文件:")
        print(f"  错误信息: {e}")

    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_doc_file_error())