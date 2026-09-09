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
    # redis_url removed - using PostgreSQL queue

    jwt_access_expire: int = 7200
    jwt_refresh_expire: int = 604800

    init_admin_username: str = "admin"
    init_admin_password: str = Field(...)    # required

    cors_origins: str = "http://localhost:3000"

    # Tracing（可切换：langsmith / langfuse / none）
    tracing_provider: str = "none"
    langsmith_api_key: str | None = None
    langsmith_project: str = "easyrag"
    langsmith_endpoint: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3000"

    # 默认模型（seed 用，env 可不配 → 不 seed）
    llm_default_base_url: str | None = None
    llm_default_api_key: str | None = None
    llm_qa_model: str | None = None
    llm_fast_model: str | None = None
    embedding_model: str | None = None
    embedding_dim: int = 1024
    rerank_model: str | None = None

    # 对象存储（本地 FS → MinIO）
    storage_type: str = "local"        # local | minio
    \
    # MinIO 配置
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "easyrag"
    minio_secure: bool = False
    minio_public_url: str | None = None


settings = Settings()

