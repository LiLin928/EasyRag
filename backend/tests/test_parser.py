"""Parser（dispatcher + md）单元测试。PDF/DOCX/XLSX 在端到端冒烟用真实文件验证。"""
import pytest

from app.core.parser import md_parser
from app.core.parser.dispatcher import parse


@pytest.mark.asyncio
async def test_md_parser(tmp_path):
    """md 解析应识别 heading（含 level）与 text。"""
    f = tmp_path / "t.md"
    f.write_text("# 标题一\n正文段落\n## 子标题\n更多正文", encoding="utf-8")
    elems = await md_parser.parse(str(f))
    types = [e.element_type for e in elems]
    assert "heading" in types and "text" in types
    headings = [e for e in elems if e.element_type == "heading"]
    assert headings[0].level == 1  # "# 标题一"


@pytest.mark.asyncio
async def test_dispatcher_unsupported():
    """不支持的扩展名应抛业务异常。"""
    with pytest.raises(Exception):
        await parse("pptx", "x.pptx")
