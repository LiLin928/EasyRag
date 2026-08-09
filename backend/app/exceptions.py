"""业务异常与错误码模块。

定义统一的错误码枚举和 BizException 业务异常，用于在请求链路中携带业务错误信息。
"""
from enum import IntEnum


class ErrorCode(IntEnum):
    """业务错误码枚举（按区段划分）。"""

    SUCCESS = 0
    # 40001-40099 参数/请求错误
    PARAM_ERROR = 40001
    FILE_TOO_LARGE = 40002
    PRECISION_UNAVAILABLE = 40003
    UNSUPPORTED_FILE = 40004
    LOGIN_FAILED = 40103           # 登录失败（落在认证段；前端 refresh 失败会跳登录，行为可接受）
    # 40100-40199 认证（40101/40102 触发前端 refresh）
    UNAUTHORIZED = 40101           # access token 过期
    REFRESH_INVALID = 40102        # refresh token 无效
    FORBIDDEN = 40300
    NOT_FOUND = 40400
    CONCURRENCY = 42901
    # 50001+
    LLM_TIMEOUT = 50001
    PARSE_FAILED = 50002
    DB_ERROR = 50003
    DEPENDENCY_DOWN = 50301


class BizException(Exception):
    """业务异常。

    携带错误码与可读消息，由全局异常处理器统一转成 ApiResponse 结构。
    """

    def __init__(self, code: ErrorCode, message: str | None = None):
        """初始化业务异常。

        Args:
            code: 错误码（ErrorCode 枚举）。
            message: 可读消息，未提供时使用错误码名称。
        """
        self.code = int(code)
        self.message = message or code.name
        super().__init__(self.message)
