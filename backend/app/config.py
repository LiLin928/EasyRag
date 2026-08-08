from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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
