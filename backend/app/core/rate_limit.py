"""速率限制配置。"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

_key_func = get_remote_address

LOGIN_RATE_LIMIT = "5/minute"
CHAT_RATE_LIMIT = "20/minute"
UPLOAD_RATE_LIMIT = "10/minute"

limiter = Limiter(key_func=_key_func, storage_uri=settings.redis_url)
