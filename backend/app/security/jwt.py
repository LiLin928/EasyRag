"""JWT 令牌模块。

提供 access/refresh token 的签发与解码，使用 HS256 算法。
"""
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from app.config import settings
from app.exceptions import BizException, ErrorCode

_ALG = "HS256"


def _create(sub: str, expires: int, typ: str) -> str:
    """生成 JWT 的内部方法。

    Args:
        sub: 主题（用户 id 的字符串形式）。
        expires: 有效期（秒）。
        typ: token 类型，access 或 refresh。

    Returns:
        编码后的 JWT 字符串。
    """
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "typ": typ, "iat": int(now.timestamp()),
               "exp": int((now + timedelta(seconds=expires)).timestamp())}
    return jwt.encode(payload, settings.secret_key, algorithm=_ALG)


def create_access_token(user_id) -> str:
    """为指定用户签发 access token（短期有效）。"""
    return _create(str(user_id), settings.jwt_access_expire, "access")


def create_refresh_token(user_id) -> str:
    """为指定用户签发 refresh token（长期有效）。"""
    return _create(str(user_id), settings.jwt_refresh_expire, "refresh")


def decode_token(token: str) -> dict:
    """解码并校验 JWT，返回 claims 字典。

    Args:
        token: JWT 字符串。

    Returns:
        解码后的 claims 字典。

    Raises:
        BizException: token 无效或已过期时抛 UNAUTHORIZED。
    """
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[_ALG])
    except JWTError:
        raise BizException(ErrorCode.UNAUTHORIZED, "token 无效或已过期")
