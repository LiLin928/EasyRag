"""密码哈希模块。

基于 passlib + bcrypt 提供密码哈希与校验。
"""
from passlib.context import CryptContext

from app.exceptions import BizException, ErrorCode

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """对明文密码做 bcrypt 哈希，返回哈希字符串。"""
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码是否与哈希值匹配，匹配返回 True。"""
    return _pwd.verify(plain, hashed)


def validate_password(plain: str) -> None:
    """校验密码复杂度：>= 8 字符，含字母+数字。不通过抛 BizException。"""
    if len(plain) < 8:
        raise BizException(ErrorCode.PARAM_ERROR, "密码至少 8 位")
    if not any(c.isalpha() for c in plain) or not any(c.isdigit() for c in plain):
        raise BizException(ErrorCode.PARAM_ERROR, "密码需包含字母和数字")
