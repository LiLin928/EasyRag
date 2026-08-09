"""LangChain 模型工厂。

把 model_configs 中的配置桥接为 LangChain BaseChatModel / Embeddings。
因 get_default_model 走异步 DB，故本工厂为 async（调用方 await）。
所有 LLM/Embedding 调用经此层，settings 切默认模型即实时生效。
"""
from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from app.exceptions import BizException, ErrorCode
from app.security.crypto import decrypt
from app.services.settings_service import get_default_model


async def build_chat_model(use: str = "qa", **overrides) -> BaseChatModel:
    """构造对话模型。

    读取 (llm, use) 的默认配置，按 provider 分支经 init_chat_model 构造 LangChain ChatModel。
    支持 openai/dashscope/vllm/siliconflow（走 openai 兼容）、ollama、azure。

    Args:
        use: 用途（qa / summary / rewrite ...）。
        **overrides: 覆盖 config.params 的运行参数（如 temp / max_tokens）。

    Returns:
        构造好的 LangChain BaseChatModel。

    Raises:
        BizException: 未配置默认 LLM，或不支持的 provider。
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
            model_provider="openai", base_url=cfg.url,
            api_key=decrypt(cfg.api_key_enc) if cfg.api_key_enc else "",
            **common,
        )
    if cfg.prov == "ollama":
        return init_chat_model(model_provider="ollama", base_url=cfg.url, **common)
    if cfg.prov == "azure":
        return init_chat_model(
            model_provider="azure_openai", azure_endpoint=cfg.url,
            api_key=decrypt(cfg.api_key_enc) if cfg.api_key_enc else "",
            **common,
        )
    raise BizException(ErrorCode.PARAM_ERROR, f"不支持的 LLM provider: {cfg.prov}")


async def build_embeddings() -> Embeddings:
    """构造嵌入模型。

    读取 (embed, retrieval) 的默认配置（回退到 embed 任意默认），按 provider 分支构造。
    openai/dashscope/vllm/siliconflow 走 openai 兼容（可选 dimensions），ollama 走 ollama。

    Returns:
        构造好的 LangChain Embeddings。

    Raises:
        BizException: 未配置默认 Embedding 模型，或不支持的 provider。
    """
    cfg = await get_default_model("embed", "retrieval") or await get_default_model("embed")
    if not cfg:
        raise BizException(ErrorCode.DEPENDENCY_DOWN, "未配置默认 Embedding 模型，请在设置页配置")
    dim = (cfg.params or {}).get("dim")
    if cfg.prov in ("openai", "dashscope", "vllm", "siliconflow"):
        kw = dict(
            model_provider="openai", model=cfg.name, base_url=cfg.url,
            api_key=decrypt(cfg.api_key_enc) if cfg.api_key_enc else "",
        )
        if dim:
            kw["dimensions"] = int(dim)
        return init_embeddings(**kw)
    if cfg.prov == "ollama":
        return init_embeddings(model_provider="ollama", model=cfg.name, base_url=cfg.url)
    raise BizException(ErrorCode.PARAM_ERROR, f"不支持的 embedding provider: {cfg.prov}")
