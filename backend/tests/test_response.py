import pytest
from app.exceptions import BizException, ErrorCode
from app.api.response import ok, err


def test_ok_shape():
    assert ok({"a": 1}) == {"code": 0, "message": "success", "data": {"a": 1}}


def test_err_shape():
    e = err(ErrorCode.PARAM_ERROR, "坏请求")
    assert e == {"code": 40001, "message": "坏请求", "data": None}


def test_biz_exception():
    with pytest.raises(BizException) as ex:
        raise BizException(ErrorCode.UNAUTHORIZED, "token 过期")
    assert ex.value.code == 40101
    assert ex.value.message == "token 过期"
