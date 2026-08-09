"""Fernet 加解密单元测试。"""
from app.security.crypto import encrypt, decrypt


def test_roundtrip():
    """加密后再解密应还原原文，且密文与原文不同。"""
    t = encrypt("sk-abcdef")
    assert t != "sk-abcdef"
    assert decrypt(t) == "sk-abcdef"


def test_unique_tokens():
    """同一明文两次加密应产生不同密文（Fernet 含随机 IV/时间戳）。"""
    assert encrypt("x") != encrypt("x")


def test_decrypt_tamper_raises():
    """密文被篡改后解密应抛异常。"""
    import pytest
    t = encrypt("secret")
    with pytest.raises(Exception):
        decrypt(t[:-4] + "AAAA")
