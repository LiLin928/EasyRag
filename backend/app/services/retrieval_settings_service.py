"""Per-knowledge-base retrieval settings resolution and persistence."""
import math
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scenes import get_scene_config
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.chunk import Chunk
from app.models.knowledge_base import KnowledgeBase
from app.models.model_config import ModelConfig


RETRIEVAL_METHODS = {"vector", "keyword", "hybrid"}

SYSTEM_DEFAULTS = {
    "method": "hybrid",
    "final_top_k": 5,
    "vector_top_k": 20,
    "keyword_top_k": 20,
    "similarity_threshold": 0.0,
    "vector_weight": 0.7,
    "keyword_weight": 0.3,
    "rrf_k": 60,
    "rerank_enabled": True,
    "rerank_top_n": 10,
    "rerank_trigger_threshold": 0.02,
    "navigation_enabled": True,
    "nav_anchor_count": 3,
    "nav_confidence_threshold": 0.15,
}

SCENE_KEY_MAP = {
    "final_top_k": "top_k",
    "keyword_top_k": "trgm_top_k",
    "rerank_trigger_threshold": "rerank_threshold",
}

_INTEGER_FIELDS = {
    "final_top_k": (1, 100),
    "vector_top_k": (1, 100),
    "keyword_top_k": (1, 100),
    "rerank_top_n": (1, 100),
    "nav_anchor_count": (1, 100),
    "rrf_k": (1, None),
}
_UNIT_RANGE_FIELDS = {
    "similarity_threshold",
    "rerank_trigger_threshold",
    "nav_confidence_threshold",
}
_BOOLEAN_FIELDS = {"rerank_enabled", "navigation_enabled"}


def _uuid(value: uuid.UUID | str, label: str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        raise BizException(ErrorCode.PARAM_ERROR, f"Invalid {label}")


def _number(config: dict, key: str, *, integer: bool = False) -> int | float:
    value = config[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BizException(ErrorCode.PARAM_ERROR, f"{key} must be a number")
    if integer and not isinstance(value, int):
        raise BizException(ErrorCode.PARAM_ERROR, f"{key} must be an integer")
    if not math.isfinite(value):
        raise BizException(ErrorCode.PARAM_ERROR, f"{key} must be finite")
    return value


def validate_retrieval_config(config: dict, *, partial: bool = True) -> dict:
    """Validate retrieval overrides and return the normalized supplied keys."""
    if not isinstance(config, dict):
        raise BizException(ErrorCode.PARAM_ERROR, "retrieval_config must be an object")

    unknown = set(config) - set(SYSTEM_DEFAULTS)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise BizException(ErrorCode.PARAM_ERROR, f"Unknown retrieval setting: {names}")

    for key in config:
        if key in _INTEGER_FIELDS:
            value = _number(config, key, integer=True)
            low, high = _INTEGER_FIELDS[key]
            if value < low or (high is not None and value > high):
                upper = high or "unlimited"
                raise BizException(ErrorCode.PARAM_ERROR, f"{key} must be between {low} and {upper}")
        elif key in _UNIT_RANGE_FIELDS:
            value = _number(config, key)
            if not 0 <= value <= 1:
                raise BizException(ErrorCode.PARAM_ERROR, f"{key} must be between 0 and 1")
        elif key in ("vector_weight", "keyword_weight"):
            value = _number(config, key)
            if not 0 <= value <= 1:
                raise BizException(ErrorCode.PARAM_ERROR, f"{key} must be between 0 and 1")
        elif key == "method":
            if not isinstance(config[key], str) or config[key] not in RETRIEVAL_METHODS:
                methods = ", ".join(sorted(RETRIEVAL_METHODS))
                raise BizException(ErrorCode.PARAM_ERROR, f"method must be one of {methods}")
        elif key in _BOOLEAN_FIELDS:
            if not isinstance(config[key], bool):
                raise BizException(ErrorCode.PARAM_ERROR, f"{key} must be a boolean")
        else:
            raise BizException(ErrorCode.PARAM_ERROR, f"Unsupported retrieval setting: {key}")

    # Cross-field rules use supplied keys plus defaults. A single supplied
    # weight remains valid because resolution complements it at read time.
    resolved = dict(SYSTEM_DEFAULTS)
    resolved.update(config)
    vector_weight = resolved["vector_weight"]
    keyword_weight = resolved["keyword_weight"]
    if (
        "vector_weight" in config
        and "keyword_weight" in config
        and not math.isclose(vector_weight + keyword_weight, 1.0, abs_tol=1e-9)
    ):
        raise BizException(ErrorCode.PARAM_ERROR, "vector_weight and keyword_weight must sum to 1")
    method = resolved["method"]
    if method == "vector" and vector_weight <= 0:
        raise BizException(ErrorCode.PARAM_ERROR, "vector_weight must be greater than 0 for vector retrieval")
    if method == "keyword" and keyword_weight <= 0:
        raise BizException(ErrorCode.PARAM_ERROR, "keyword_weight must be greater than 0 for keyword retrieval")
    if resolved["rerank_top_n"] > resolved["vector_top_k"] + resolved["keyword_top_k"]:
        raise BizException(ErrorCode.PARAM_ERROR, "rerank_top_n cannot exceed the candidate TopK sum")
    return dict(config)


def _model_out(model: ModelConfig | None) -> dict | None:
    if model is None:
        return None
    return {
        "id": str(model.id),
        "grp": model.grp,
        "name": model.name,
        "prov": model.prov,
        "use": model.use,
        "url": model.url,
        "enabled": bool(model.enabled),
    }


async def _load_models(
    session: AsyncSession, *model_ids: uuid.UUID | None
) -> dict[uuid.UUID, ModelConfig]:
    ids = {model_id for model_id in model_ids if model_id is not None}
    if not ids:
        return {}
    rows = (
        await session.execute(select(ModelConfig).where(ModelConfig.id.in_(ids)))
    ).scalars().all()
    return {model.id: model for model in rows}


async def _get_kb(
    kb_id: str, user_id: uuid.UUID | str | None, session: AsyncSession
) -> KnowledgeBase:
    kb_uuid = _uuid(kb_id, "knowledge base ID")
    kb = await session.get(KnowledgeBase, kb_uuid)
    if not kb:
        raise BizException(ErrorCode.NOT_FOUND, "Knowledge base not found")
    if user_id is not None and kb.user_id != _uuid(user_id, "user ID"):
        raise BizException(ErrorCode.FORBIDDEN, "Knowledge base not accessible")
    return kb


def _reconcile_weights(values: dict[str, dict]) -> None:
    vector = values["vector_weight"]
    keyword = values["keyword_weight"]
    source_rank = {"override": 3, "knowledge_base": 2, "scene": 1}
    vector_rank = source_rank.get(vector["source"], 0)
    keyword_rank = source_rank.get(keyword["source"], 0)
    if vector_rank == keyword_rank and vector_rank != 0:
        if not math.isclose(vector["value"] + keyword["value"], 1.0, abs_tol=1e-9):
            raise BizException(ErrorCode.PARAM_ERROR, "vector_weight and keyword_weight must sum to 1")
    elif vector_rank > keyword_rank:
        keyword["value"] = 1 - vector["value"]
    elif keyword_rank > vector_rank:
        vector["value"] = 1 - keyword["value"]


async def _effective_for_kb(
    kb: KnowledgeBase,
    models: dict[uuid.UUID, ModelConfig],
    override: dict | None = None,
) -> dict:
    override = validate_retrieval_config(override or {}, partial=True)
    stored_config = kb.retrieval_config or {}
    scene = await get_scene_config(kb.scene)

    values: dict[str, dict] = {}
    for key, default_value in SYSTEM_DEFAULTS.items():
        if key in override:
            value, source = override[key], "override"
        elif key == "final_top_k" and "final_top_k" not in stored_config and kb.retrieval_top_k is not None:
            value, source = kb.retrieval_top_k, "knowledge_base"
        elif key in stored_config and stored_config[key] is not None:
            value, source = stored_config[key], "knowledge_base"
        elif key in SCENE_KEY_MAP and getattr(scene, SCENE_KEY_MAP[key], None) is not None:
            value, source = getattr(scene, SCENE_KEY_MAP[key]), "scene"
        elif getattr(scene, key, None) is not None:
            value, source = getattr(scene, key), "scene"
        else:
            value, source = default_value, "system_default"
        values[key] = {"value": value, "source": source}

    _reconcile_weights(values)
    resolved = resolved_values({"values": values})
    validate_retrieval_config(resolved, partial=False)
    embedding_model = models.get(kb.embedding_model_id)
    rerank_model = models.get(kb.rerank_model_id)
    return {
        "values": values,
        "resolved": resolved,
        "embedding_model": _model_out(embedding_model),
        "rerank_model": _model_out(rerank_model),
        "rebuild_required": False,
    }


async def get_effective_settings(
    kb_id: str,
    user_id: uuid.UUID | str | None = None,
    override: dict | None = None,
) -> dict:
    """Resolve retrieval settings field by field for one knowledge base."""
    async with async_session() as session:
        kb = await _get_kb(kb_id, user_id, session)
        models = await _load_models(session, kb.embedding_model_id, kb.rerank_model_id)
        return await _effective_for_kb(kb, models, override)


def resolved_values(effective: dict) -> dict:
    """Return scalar values from an effective-settings response."""
    return {key: item["value"] for key, item in effective["values"].items()}


def _validate_embedding_model(model: ModelConfig | None) -> ModelConfig:
    if model is None:
        raise BizException(ErrorCode.NOT_FOUND, "Embedding model not found")
    if not model.enabled:
        raise BizException(ErrorCode.PARAM_ERROR, "Embedding model is disabled")
    if model.grp != "embed":
        raise BizException(ErrorCode.PARAM_ERROR, "Model must be in the embed group")
    dim = (model.params or {}).get("dim")
    if dim is not None and dim != 1024:
        raise BizException(ErrorCode.PARAM_ERROR, "Embedding model dimension must be 1024")
    return model


def _validate_rerank_model(model: ModelConfig | None) -> ModelConfig:
    if model is None:
        raise BizException(ErrorCode.NOT_FOUND, "Rerank model not found")
    if not model.enabled:
        raise BizException(ErrorCode.PARAM_ERROR, "Rerank model is disabled")
    if model.grp != "rerank":
        raise BizException(ErrorCode.PARAM_ERROR, "Model must be in the rerank group")
    return model


async def save_retrieval_settings(
    *,
    kb_id: str,
    user_id: uuid.UUID | str,
    embedding_model_id: uuid.UUID | str | None = None,
    rerank_model_id: uuid.UUID | str | None = None,
    retrieval_config: dict | None = None,
    update_embedding_model: bool = False,
    update_rerank_model: bool = False,
    update_retrieval_config: bool = False,
) -> dict:
    """Validate and save explicit model bindings and retrieval overrides."""
    async with async_session() as session:
        kb = await _get_kb(kb_id, user_id, session)
        embedding_uuid = (
            _uuid(embedding_model_id, "embedding model ID")
            if update_embedding_model and embedding_model_id is not None
            else None
        )
        rerank_uuid = (
            _uuid(rerank_model_id, "rerank model ID")
            if update_rerank_model and rerank_model_id is not None
            else None
        )
        models = await _load_models(session, embedding_uuid, rerank_uuid)
        embedding_model = _validate_embedding_model(models.get(embedding_uuid)) if embedding_uuid else None
        rerank_model = _validate_rerank_model(models.get(rerank_uuid)) if rerank_uuid else None

        stored_config = kb.retrieval_config or {}
        new_config = stored_config
        if update_retrieval_config:
            if retrieval_config is None:
                new_config = {}
            else:
                supplied = validate_retrieval_config(retrieval_config, partial=True)
                merged = {**stored_config, **supplied}
                validate_retrieval_config(merged, partial=False)
                new_config = dict(stored_config)
                new_config.update({key: merged[key] for key in supplied})

        rebuild_required = False
        if embedding_model is not None and kb.embedding_model_id != embedding_model.id:
            has_embeddings = (
                await session.execute(
                    select(Chunk.id)
                    .where(Chunk.kb_id == str(kb.id), Chunk.embedding.is_not(None))
                    .limit(1)
                )
            ).first() is not None
            rebuild_required = has_embeddings

        if update_embedding_model:
            kb.embedding_model_id = embedding_model.id if embedding_model else None
        if update_rerank_model:
            kb.rerank_model_id = rerank_model.id if rerank_model else None
        if update_retrieval_config:
            kb.retrieval_config = new_config
        await session.commit()

        models = await _load_models(session, kb.embedding_model_id, kb.rerank_model_id)
        effective = await _effective_for_kb(kb, models)
        effective["rebuild_required"] = rebuild_required
        return effective
