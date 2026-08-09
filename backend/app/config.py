"""应用配置模块。

基于 pydantic-settings 从 .env 文件读取配置，集中暴露全局 settings 单例。
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局应用配置。

    所有字段均可通过 .env 文件或环境变量覆盖；标注 ``Field(...)`` 的为必填项。
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"
    secret_key: str = Field(...)             # required
    api_prefix: str = "/api/v2"
    log_level: str = "INFO"

    database_url: str = Field(...)           # required
    redis_url: str = "redis://localhost:6379/0"

    jwt_access_expire: int = 7200
    jwt_refresh_expire: int = 604800

    init_admin_username: str = "admin"
    init_admin_password: str = Field(...)    # required

    cors_origins: str = "http://localhost:3000"


settings = Settings()
