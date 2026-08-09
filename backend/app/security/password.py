"""密码哈希模块。

基于 passlib + bcrypt 提供密码哈希与校验。
"""
from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """对明文密码做 bcrypt 哈希，返回哈希字符串。"""
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码是否与哈希值匹配，匹配返回 True。"""
    return _pwd.verify(plain, hashed)
