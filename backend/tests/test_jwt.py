import pytest
from app.security.jwt import create_access_token, create_refresh_token, decode_token
from app.exceptions import BizException, ErrorCode


def test_access_roundtrip():
    t = create_access_token("user-123")
    claims = decode_token(t)
    assert claims["sub"] == "user-123"
    assert claims["typ"] == "access"


def test_refresh_typ():
    t = create_refresh_token("user-123")
    assert decode_token(t)["typ"] == "refresh"


def test_invalid_token_raises():
    with pytest.raises(BizException) as ex:
        decode_token("not-a-jwt")
    assert ex.value.code == int(ErrorCode.UNAUTHORIZED)
