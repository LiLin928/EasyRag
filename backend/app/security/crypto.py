"""模型 API Key 加解密模块。

基于 Fernet 对称加密，密钥由全局 SECRET_KEY 经 PBKDF2 派生，
用于持久化 model_configs.api_key_enc（API key 落库前加密，读取时解密）。
"""
import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings

# 固定盐；密钥仍由 SECRET_KEY 派生，更换 SECRET_KEY 即完成密钥轮换。
_SALT = b"easyrag-model-key-v1"


def _fernet() -> Fernet:
    """由 SECRET_KEY 派生 Fernet 实例。

    使用 PBKDF2HMAC(SHA256, 10 万次迭代) 从全局 secret_key 派生 32 字节密钥，
    再 urlsafe-base64 编码为 Fernet 所需的格式。
    """
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_SALT, iterations=100_000)
    key = base64.urlsafe_b64encode(kdf.derive(settings.secret_key.encode()))
    return Fernet(key)


def encrypt(plain: str) -> str:
    """加密明文，返回 Fernet 密文字符串。

    Args:
        plain: 待加密的明文（如 API key）。None 直接返回 None（用于空值兼容）。

    Returns:
        加密后的密文字符串，每次调用结果不同（Fernet 含随机 IV 与时间戳）。
    """
    if plain is None:
        return None
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    """解密 Fernet 密文，返回明文。

    Args:
        token: 加密后的密文字符串。

    Returns:
        原始明文。

    Raises:
        ValueError: 密文已损坏或 SECRET_KEY 不匹配（轮换密钥后旧密文不可解）。
    """
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        raise ValueError("密文已损坏或密钥不匹配")
