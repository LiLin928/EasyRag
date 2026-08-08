from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from app.config import settings
from app.exceptions import BizException, ErrorCode

_ALG = "HS256"


def _create(sub: str, expires: int, typ: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "typ": typ, "iat": int(now.timestamp()),
               "exp": int((now + timedelta(seconds=expires)).timestamp())}
    return jwt.encode(payload, settings.secret_key, algorithm=_ALG)


def create_access_token(user_id) -> str:
    return _create(str(user_id), settings.jwt_access_expire, "access")


def create_refresh_token(user_id) -> str:
    return _create(str(user_id), settings.jwt_refresh_expire, "refresh")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[_ALG])
    except JWTError:
        raise BizException(ErrorCode.UNAUTHORIZED, "token 无效或已过期")
