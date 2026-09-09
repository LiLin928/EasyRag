"""LangChain 模型工厂。

把 model_configs 中的配置桥接为 LangChain BaseChatModel / Embeddings。
因 get_default_model 走异步 DB，故本工厂为 async（调用方 await）。
所有 LLM/Embedding 调用经此层，settings 切默认模型即实时生效。
"""
import uuid

from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.model_config import ModelConfig
from app.providers.rerank.api_reranker import ApiReranker
from app.security.crypto import decrypt
from app.services.settings_service import get_default_model


def _api_key(cfg: ModelConfig) -> str:
    return decrypt(cfg.api_key_enc) if cfg.api_key_enc else ""


async def build_chat_model(use: str = "qa", **overrides) -> BaseChatModel:
    """构造对话模型。

    读取 (llm, use) 的默认配置，按 provider 分支经 init_chat_model 构造 LangChain ChatModel。
    支持 openai/dashscope/vllm/siliconflow（走 openai 兼容）、ollama、azure。
    """
    cfg = await get_default_model("llm", use)
    if not cfg:
        raise BizException(ErrorCode.DEPENDENCY_DOWN, f"未配置默认 LLM 模型（用途 {use}），请在设置页配置")
    params = {**(cfg.params or {}), **overrides}
    common = {
        "model": cfg.name,
        "temperature": params.get("temp", 0.7),
        "max_tokens": int(params["max_tokens"]) if params.get("max_tokens") else None,
    }
    common = {k: v for k, v in common.items() if v is not None}
    if cfg.prov in ("openai", "dashscope", "vllm", "siliconflow"):
        return init_chat_model(
            model_provider="openai",
            base_url=cfg.url,
            api_key=_api_key(cfg),
            **common,
        )
    if cfg.prov == "ollama":
        return init_chat_model(model_provider="ollama", base_url=cfg.url, **common)
    if cfg.prov == "azure":
        return init_chat_model(
            model_provider="azure_openai",
            azure_endpoint=cfg.url,
            api_key=_api_key(cfg),
            **common,
        )
    raise BizException(ErrorCode.PARAM_ERROR, f"不支持的 LLM provider: {cfg.prov}")


async def get_model_by_id(model_id, expected_group: str) -> ModelConfig:
    """Load an enabled model and enforce its expected model group."""
    try:
        model_uuid = model_id if isinstance(model_id, uuid.UUID) else uuid.UUID(model_id)
    except (TypeError, ValueError):
        raise BizException(ErrorCode.PARAM_ERROR, "Invalid model ID")

    async with async_session() as session:
        cfg = await session.get(ModelConfig, model_uuid)
    if not cfg:
        raise BizException(ErrorCode.NOT_FOUND, "Model not found")
    if not cfg.enabled:
        raise BizException(ErrorCode.PARAM_ERROR, "Model is disabled")
    if cfg.grp != expected_group:
        raise BizException(ErrorCode.PARAM_ERROR, f"Model must be in the {expected_group} group")
    return cfg


def _build_embedding(cfg: ModelConfig) -> Embeddings:
    dim = (cfg.params or {}).get("dim")
    if cfg.prov in ("openai", "dashscope", "vllm", "siliconflow"):
        kwargs = {
            "model_provider": "openai",
            "model": cfg.name,
            "base_url": cfg.url,
            "api_key": _api_key(cfg),
        }
        if dim:
            kwargs["dimensions"] = int(dim)
        return init_embeddings(**kwargs)
    if cfg.prov == "ollama":
        return init_embeddings(
            model_provider="ollama", model=cfg.name, base_url=cfg.url
        )
    raise BizException(
        ErrorCode.PARAM_ERROR, f"Unsupported embedding provider: {cfg.prov}"
    )


async def build_embeddings_from_config(cfg: ModelConfig) -> Embeddings:
    """Build embeddings from one explicit model configuration."""
    if not cfg.enabled:
        raise BizException(ErrorCode.PARAM_ERROR, "Embedding model is disabled")
    if cfg.grp != "embed":
        raise BizException(ErrorCode.PARAM_ERROR, "Model must be in the embed group")
    dim = (cfg.params or {}).get("dim")
    if dim is not None and dim != 1024:
        raise BizException(
            ErrorCode.PARAM_ERROR, "Embedding model dimension must be 1024"
        )
    return _build_embedding(cfg)


async def build_reranker_from_config(cfg: ModelConfig) -> ApiReranker:
    """Build an API reranker from one explicit model configuration."""
    if not cfg.enabled:
        raise BizException(ErrorCode.PARAM_ERROR, "Rerank model is disabled")
    if cfg.grp != "rerank":
        raise BizException(ErrorCode.PARAM_ERROR, "Model must be in the rerank group")
    return ApiReranker(
        url=cfg.url,
        api_key=_api_key(cfg),
        model=cfg.name,
    )


async def build_embeddings() -> Embeddings:
    """构造嵌入模型。

    读取 (embed, retrieval) 的默认配置（回退到 embed 任意默认），按 provider 分支构造。
    openai/dashscope/vllm/siliconflow 走 openai 兼容（可选 dimensions），ollama 走 ollama。
    """
    cfg = await get_default_model("embed", "retrieval") or await get_default_model("embed")
    if not cfg:
        raise BizException(ErrorCode.DEPENDENCY_DOWN, "未配置默认 Embedding 模型，请在设置页配置")
    return await build_embeddings_from_config(cfg)
