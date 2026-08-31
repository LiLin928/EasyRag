"""文件 magic number 校验模块。"""
from app.exceptions import BizException, ErrorCode

MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF", "application/pdf"),
    (b"PK\x03\x04", "application/zip"),  # docx, xlsx
    (b"\xd0\xcf\x11\xe0", "application/msword"),  # .doc (OLE)
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
]


def detect_file_type(content: bytes) -> str | None:
    """根据文件头 magic number 检测 MIME 类型。"""
    for magic, mime in MAGIC_SIGNATURES:
        if content.startswith(magic):
            return mime
    return None


def validate_file_magic(content: bytes, allowed: set[str]) -> None:
    """校验文件 magic number 是否在允许列表内。"""
    detected = detect_file_type(content)
    if detected not in allowed:
        raise BizException(
            ErrorCode.UNSUPPORTED_FILE,
            f"不支持的文件类型: {detected or '未知'}"
        )
