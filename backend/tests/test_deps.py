import pytest
from app.security.jwt import create_access_token, create_refresh_token
from app.api.deps import get_current_user, _claims_from_header
from app.exceptions import BizException, ErrorCode


def test_missing_prefix():
    with pytest.raises(BizException):
        _claims_from_header("Token abc")


def test_refresh_token_rejected_for_access():
    refresh = create_refresh_token("u1")
    with pytest.raises(BizException) as ex:
        _claims_from_header("Bearer " + refresh, expect_typ="access")
    assert ex.value.code == int(ErrorCode.UNAUTHORIZED)
