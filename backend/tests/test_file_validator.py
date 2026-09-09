"""文件 magic number 校验测试。"""
import pytest
from app.core.file_validator import detect_file_type, validate_file_magic
from app.exceptions import BizException, ErrorCode


def test_detect_pdf():
    assert detect_file_type(b"%PDF-1.4\n1 0 obj") == "application/pdf"


def test_detect_zip():
    assert detect_file_type(b"PK\x03\x04\x14\x00\x00\x00") == "application/zip"


def test_detect_png():
    assert detect_file_type(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR") == "image/png"


def test_detect_jpeg():
    assert detect_file_type(b"\xff\xd8\xff\xe0\x00\x10JFIF") == "image/jpeg"


def test_detect_unknown():
    assert detect_file_type(b"\x00\x01\x02\x03") is None


def test_validate_accepts_allowed():
    validate_file_magic(b"%PDF-1.4", {"application/pdf"})  # should not raise


def test_validate_rejects_mismatch():
    with pytest.raises(BizException) as exc:
        validate_file_magic(b"PK\x03\x04", {"application/pdf"})
    assert exc.value.code == ErrorCode.UNSUPPORTED_FILE
