"""Per-KB retrieval settings resolution and validation tests."""
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, select

from app.db.session import async_session
from app.exceptions import BizException
from app.core.scenes import SceneConfig
from app.models.knowledge_base import KnowledgeBase
from app.models.model_config import ModelConfig
from app.models.user import User
from app.services.retrieval_settings_service import (
    get_effective_settings,
    save_retrieval_settings,
    validate_retrieval_config,
)


async def _admin_id() -> uuid.UUID:
    async with async_session() as s:
        return (await s.execute(select(User))).scalars().first().id


async def _model(name: str, grp: str, dim: int | None = None) -> ModelConfig:
    async with async_session() as s:
        await s.execute(delete(ModelConfig).where(
            ModelConfig.grp == grp, ModelConfig.name == name
        ))
        await s.commit()
        m = ModelConfig(
            grp=grp,
            name=name,
            prov="openai",
            use="retrieval" if grp == "embed" else "rerank",
            url="http://localhost",
            params={} if dim is None else {"dim": dim},
            is_default=False,
            enabled=True,
        )
        s.add(m)
        await s.commit()
        await s.refresh(m)
        return m


@pytest.mark.asyncio
async def test_effective_settings_map_scene_keys(monkeypatch):
    async def fake_scene(_code):
        return SceneConfig(
            code="scene",
            name="Scene",
            top_k=6,
            vector_top_k=11,
            trgm_top_k=15,
            vector_weight=0.6,
            keyword_weight=0.4,
            rerank_threshold=0.03,
        )

    monkeypatch.setattr(
        "app.services.retrieval_settings_service.get_scene_config", fake_scene
    )
    kb = KnowledgeBase(
        user_id=uuid.uuid4(),
        name="TransientResolutionKB",
        scene="scene",
        retrieval_top_k=7,
        retrieval_config={"vector_top_k": 12, "vector_weight": 0.8},
    )

    from app.services.retrieval_settings_service import _effective_for_kb

    effective = await _effective_for_kb(kb, {}, {"vector_top_k": 9})
    assert effective["values"]["vector_top_k"] == {"value": 9, "source": "override"}
    assert effective["values"]["vector_weight"] == {
        "value": 0.8,
        "source": "knowledge_base",
    }
    assert effective["values"]["final_top_k"] == {
        "value": 7,
        "source": "knowledge_base",
    }
    assert effective["values"]["keyword_top_k"] == {"value": 15, "source": "scene"}
    assert effective["values"]["rerank_trigger_threshold"] == {
        "value": 0.03,
        "source": "scene",
    }
    assert effective["values"]["method"]["source"] == "system_default"
    assert effective["resolved"]["vector_weight"] + effective["resolved"]["keyword_weight"] == 1


def test_config_validation_requires_compatible_cross_fields():
    assert validate_retrieval_config({"vector_weight": 0.8}) == {
        "vector_weight": 0.8
    }

    with pytest.raises(BizException):
        validate_retrieval_config({
            "vector_weight": 0.2,
            "keyword_weight": 0.5,
        })
    with pytest.raises(BizException):
        validate_retrieval_config({"method": "vector", "vector_weight": 0.0})
    with pytest.raises(BizException):
        validate_retrieval_config({
            "rerank_top_n": 101,
            "vector_top_k": 50,
            "keyword_top_k": 50,
        })
    with pytest.raises(BizException):
        validate_retrieval_config({"unknown_key": 1})


def test_config_validation_rejects_json_valid_non_string_methods():
    for malformed_method in ([], {}):
        with pytest.raises(BizException):
            validate_retrieval_config({"method": malformed_method})


@pytest.mark.asyncio
async def test_effective_settings_reject_incompatible_merged_overrides(monkeypatch):
    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, _model, object_id):
            return kb if object_id == kb.id else None

    user_id = uuid.uuid4()
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        user_id=user_id,
        name="MergedOverrideKB",
        scene="general",
        retrieval_config={
            "method": "vector",
            "vector_top_k": 10,
            "keyword_top_k": 10,
        },
    )

    async def fake_scene(_code):
        return SceneConfig(code="general", name="General")

    monkeypatch.setattr(
        "app.services.retrieval_settings_service.async_session", Session
    )
    monkeypatch.setattr(
        "app.services.retrieval_settings_service._load_models",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        "app.services.retrieval_settings_service.get_scene_config", fake_scene
    )

    with pytest.raises(BizException):
        await get_effective_settings(
            str(kb.id), user_id=user_id, override={"vector_weight": 0.0}
        )

    kb.retrieval_config["rerank_top_n"] = 20
    with pytest.raises(BizException):
        await get_effective_settings(
            str(kb.id), user_id=user_id, override={"rerank_top_n": 21}
        )


@pytest.mark.asyncio
async def test_save_semantics_and_rebuild_without_db(monkeypatch):
    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def get(self, _model, object_id):
            return kb if object_id == kb.id else None

        async def execute(self, _query):
            class Result:
                @staticmethod
                def first():
                    return object()

            return Result

        async def commit(self):
            return None

    kb_id = uuid.uuid4()
    user_id = uuid.uuid4()
    old_embed = ModelConfig(
        id=uuid.uuid4(), grp="embed", name="old", prov="openai",
        use="retrieval", url="http://localhost", params={"dim": 1024},
        enabled=True,
    )
    new_embed = ModelConfig(
        id=uuid.uuid4(), grp="embed", name="new", prov="openai",
        use="retrieval", url="http://localhost", params={}, enabled=True,
    )
    rerank = ModelConfig(
        id=uuid.uuid4(), grp="rerank", name="rerank", prov="openai",
        use="rerank", url="http://localhost", params={}, enabled=True,
    )
    bad_dim = ModelConfig(
        id=uuid.uuid4(), grp="embed", name="bad-dim", prov="openai",
        use="retrieval", url="http://localhost", params={"dim": 768},
        enabled=True,
    )
    wrong_group = ModelConfig(
        id=uuid.uuid4(), grp="llm", name="llm", prov="openai",
        use="qa", url="http://localhost", params={}, enabled=True,
    )
    kb = KnowledgeBase(
        id=kb_id,
        user_id=user_id,
        name="TransientSaveKB",
        scene="general",
        retrieval_top_k=7,
        embedding_model_id=old_embed.id,
        rerank_model_id=rerank.id,
        retrieval_config={
            "vector_top_k": 12,
            "vector_weight": 0.8,
            "keyword_weight": 0.2,
        },
    )
    model_map = {
        old_embed.id: old_embed,
        new_embed.id: new_embed,
        rerank.id: rerank,
        bad_dim.id: bad_dim,
        wrong_group.id: wrong_group,
    }

    async def fake_load_models(_session, *model_ids):
        return {model_id: model_map[model_id] for model_id in model_ids if model_id}

    async def fake_scene(_code):
        return SceneConfig(code="general", name="General")

    monkeypatch.setattr(
        "app.services.retrieval_settings_service.async_session", Session
    )
    monkeypatch.setattr(
        "app.services.retrieval_settings_service._load_models", fake_load_models
    )
    monkeypatch.setattr(
        "app.services.retrieval_settings_service.get_scene_config", fake_scene
    )

    saved = await save_retrieval_settings(
        kb_id=str(kb_id),
        user_id=user_id,
        embedding_model_id=new_embed.id,
        retrieval_config={"vector_top_k": 9},
        update_embedding_model=True,
        update_rerank_model=False,
        update_retrieval_config=True,
    )
    assert saved["embedding_model"]["id"] == str(new_embed.id)
    assert saved["rerank_model"]["id"] == str(rerank.id)
    assert saved["rebuild_required"] is True
    assert saved["values"]["vector_top_k"]["value"] == 9
    assert saved["values"]["vector_weight"]["value"] == 0.8

    for invalid_model in (bad_dim, wrong_group):
        with pytest.raises(BizException):
            await save_retrieval_settings(
                kb_id=str(kb_id),
                user_id=user_id,
                embedding_model_id=invalid_model.id,
                update_embedding_model=True,
            )
        assert kb.embedding_model_id == new_embed.id

    cleared = await save_retrieval_settings(
        kb_id=str(kb_id),
        user_id=user_id,
        embedding_model_id=None,
        update_embedding_model=True,
        update_rerank_model=False,
        update_retrieval_config=False,
    )
    assert cleared["embedding_model"] is None
    assert cleared["rerank_model"]["id"] == str(rerank.id)
    assert cleared["rebuild_required"] is False
    assert cleared["values"]["vector_top_k"]["value"] == 9

    reset = await save_retrieval_settings(
        kb_id=str(kb_id),
        user_id=user_id,
        retrieval_config=None,
        update_embedding_model=False,
        update_rerank_model=False,
        update_retrieval_config=True,
    )
    assert reset["embedding_model"] is None
    assert reset["rerank_model"]["id"] == str(rerank.id)
    assert reset["values"]["vector_top_k"]["source"] == "scene"
    assert reset["values"]["vector_weight"]["source"] == "scene"


@pytest.mark.asyncio
async def test_priority_is_override_kb_scene_then_default():
    user_id = await _admin_id()
    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(
            KnowledgeBase.name == "PlanSettingsPriorityKB"
        ))
        await s.commit()
        kb = KnowledgeBase(
            user_id=user_id,
            name="PlanSettingsPriorityKB",
            scene="general",
            retrieval_top_k=7,
            retrieval_config={"vector_top_k": 12, "vector_weight": 0.8},
        )
        s.add(kb)
        await s.commit()
        kb_id = str(kb.id)

    effective = await get_effective_settings(
        kb_id=kb_id,
        override={"vector_top_k": 9},
    )
    assert effective["values"]["vector_top_k"] == {
        "value": 9,
        "source": "override",
    }
    assert effective["values"]["vector_weight"] == {
        "value": 0.8,
        "source": "knowledge_base",
    }
    assert effective["values"]["final_top_k"] == {
        "value": 7,
        "source": "knowledge_base",
    }
    assert effective["values"]["method"]["source"] == "system_default"
    assert effective["resolved"]["vector_weight"] + effective["resolved"]["keyword_weight"] == 1


@pytest.mark.asyncio
async def test_save_rejects_wrong_model_group_dimension_and_weights():
    user_id = await _admin_id()
    embed = await _model("plan_embed_1024", "embed", 1024)
    rerank = await _model("plan_rerank", "rerank")
    llm = await _model("plan_llm", "llm")

    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(
            KnowledgeBase.name == "PlanSettingsValidationKB"
        ))
        await s.commit()
        kb = KnowledgeBase(user_id=user_id, name="PlanSettingsValidationKB", scene="general")
        s.add(kb)
        await s.commit()
        kb_id = str(kb.id)

    saved = await save_retrieval_settings(
        kb_id=kb_id,
        user_id=user_id,
        embedding_model_id=embed.id,
        rerank_model_id=rerank.id,
        retrieval_config={"method": "vector"},
        update_embedding_model=True,
        update_rerank_model=True,
        update_retrieval_config=True,
    )
    assert saved["embedding_model"]["id"] == str(embed.id)
    assert saved["rebuild_required"] is False

    with pytest.raises(BizException):
        await save_retrieval_settings(
            kb_id=kb_id,
            user_id=user_id,
            embedding_model_id=llm.id,
            update_embedding_model=True,
        )

    with pytest.raises(BizException):
        await save_retrieval_settings(
            kb_id=kb_id,
            user_id=user_id,
            embedding_model_id=embed.id,
            retrieval_config={"vector_weight": 0.2, "keyword_weight": 0.5},
            update_embedding_model=True,
            update_retrieval_config=True,
        )


@pytest.mark.asyncio
async def test_save_rejects_incompatible_dimension_before_changing_kb():
    user_id = await _admin_id()
    embed = await _model("plan_embed_before_bad", "embed", 1024)
    bad_dim = await _model("plan_embed_768", "embed", 768)

    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(
            KnowledgeBase.name == "PlanSettingsDimensionKB"
        ))
        await s.commit()
        kb = KnowledgeBase(user_id=user_id, name="PlanSettingsDimensionKB", scene="general")
        s.add(kb)
        await s.commit()
        kb_id = str(kb.id)

    await save_retrieval_settings(
        kb_id=kb_id,
        user_id=user_id,
        embedding_model_id=embed.id,
        update_embedding_model=True,
    )
    with pytest.raises(BizException):
        await save_retrieval_settings(
            kb_id=kb_id,
            user_id=user_id,
            embedding_model_id=bad_dim.id,
            update_embedding_model=True,
        )

    async with async_session() as s:
        saved_kb = await s.get(KnowledgeBase, kb_id)
    assert saved_kb.embedding_model_id == embed.id


@pytest.mark.asyncio
async def test_save_supports_omitted_fields_explicit_clear_and_partial_config():
    user_id = await _admin_id()
    embed = await _model("plan_embed_clear_1024", "embed", 1024)
    rerank = await _model("plan_rerank_clear", "rerank")

    async with async_session() as s:
        await s.execute(delete(KnowledgeBase).where(
            KnowledgeBase.name == "PlanSettingsPatchSemanticsKB"
        ))
        await s.commit()
        kb = KnowledgeBase(user_id=user_id, name="PlanSettingsPatchSemanticsKB", scene="general")
        s.add(kb)
        await s.commit()
        kb_id = str(kb.id)

    await save_retrieval_settings(
        kb_id=kb_id,
        user_id=user_id,
        embedding_model_id=embed.id,
        rerank_model_id=rerank.id,
        retrieval_config={
            "vector_top_k": 12,
            "vector_weight": 0.8,
            "keyword_weight": 0.2,
        },
        update_embedding_model=True,
        update_rerank_model=True,
        update_retrieval_config=True,
    )

    partial = await save_retrieval_settings(
        kb_id=kb_id,
        user_id=user_id,
        retrieval_config={"vector_top_k": 9},
        update_embedding_model=False,
        update_rerank_model=False,
        update_retrieval_config=True,
    )
    assert partial["embedding_model"]["id"] == str(embed.id)
    assert partial["rerank_model"]["id"] == str(rerank.id)
    assert partial["values"]["vector_top_k"]["value"] == 9
    assert partial["values"]["vector_weight"]["value"] == 0.8

    cleared_embed = await save_retrieval_settings(
        kb_id=kb_id,
        user_id=user_id,
        embedding_model_id=None,
        update_embedding_model=True,
        update_rerank_model=False,
        update_retrieval_config=False,
    )
    assert cleared_embed["embedding_model"] is None
    assert cleared_embed["rerank_model"]["id"] == str(rerank.id)

    reset = await save_retrieval_settings(
        kb_id=kb_id,
        user_id=user_id,
        retrieval_config=None,
        update_embedding_model=False,
        update_rerank_model=False,
        update_retrieval_config=True,
    )
    assert reset["values"]["vector_top_k"]["source"] == "system_default"
    assert reset["values"]["vector_weight"]["source"] == "system_default"
    assert reset["rerank_model"]["id"] == str(rerank.id)
