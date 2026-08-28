"""settings 路由：/settings/models（模型配置 CRUD）。

Task 9 将扩展 /settings/scenes（场景 CRUD）。响应统一为 {code,message,data}。
"""
from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import delete, select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.exceptions import BizException, ErrorCode
from app.models.model_config import ModelConfig
from app.models.scene import Scene
from app.schemas.settings import ModelDef, ModelOut, SceneIn, SceneOut, SceneUpdate
from app.schemas.settings import ModelDef, ModelOut, ModelResponse, SceneIn, SceneOut, SceneUpdate
from app.security.crypto import encrypt
from app.services.settings_service import set_default_model, upsert_model

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/models")
async def list_models(group: str | None = None, me=Depends(get_current_user)):
    """列出模型配置，按分组返回 {llm:[], embed:[], rerank:[]}；key 掩码。"""
    async with async_session() as s:
        q = select(ModelConfig)
        if group:
            q = q.where(ModelConfig.grp == group)
        rows = (await s.execute(q)).scalars().all()
    groups = {"llm": [], "embed": [], "rerank": []}
    for r in rows:
        entry = groups.setdefault(r.grp, [])
        entry.append(ModelResponse.from_model(r).model_dump(by_alias=True))
    return ok(groups)


@router.post("/models")
async def create_or_update_model(group: str = Query(...), body: ModelDef = Body(...), me=Depends(get_current_user)):
    """新增或更新（按 group+name upsert）模型配置；key 加密存储，is_default 时设为组内默认。"""
    params = dict(body.params or {})
    if body.temp is not None:
        params["temp"] = body.temp
    if body.ctx is not None:
        params["ctx"] = body.ctx
    if body.dim is not None:
        params["dim"] = body.dim
    m = ModelConfig(
        grp=group, name=body.name, prov=body.prov, use=body.use, url=body.url,
        api_key_enc=encrypt(body.key) if body.key else None,
        params=params, is_default=body.is_default,
    )
    saved = await upsert_model(m)
    if body.is_default:
        await set_default_model(group, body.name)
    return ok(ModelResponse.from_model(saved).model_dump(by_alias=True))


@router.put("/models/{group}/default")
async def set_default(group: str, name: str = Query(...), me=Depends(get_current_user)):
    """将指定 group+name 设为该组唯一默认（同组互斥）。"""
    await set_default_model(group, name)
    return ok({"success": True})


@router.delete("/models")
async def delete_model(group: str = Query(...), name: str = Query(...), me=Depends(get_current_user)):
    """删除指定 group+name 的模型配置。"""
    async with async_session() as s:
        await s.execute(delete(ModelConfig).where(ModelConfig.grp == group, ModelConfig.name == name))
        await s.commit()
    return ok({"success": True})


def _scene_out(s: Scene) -> dict:
    """构造场景响应字典。"""
    return SceneOut(id=str(s.id), code=s.code, name=s.name, description=s.description,
                    config=s.config, built_in=s.built_in).model_dump()


@router.get("/scenes")
async def list_scenes(me=Depends(get_current_user)):
    """列出全部场景，按创建时间排序。"""
    async with async_session() as s:
        rows = (await s.execute(select(Scene).order_by(Scene.created_at))).scalars().all()
    return ok([_scene_out(r) for r in rows])


@router.get("/scenes/{scene_id}")
async def get_scene(scene_id: str, me=Depends(get_current_user)):
    """获取单个场景详情。"""
    async with async_session() as s:
        sc = (await s.execute(select(Scene).where(Scene.id == scene_id))).scalar_one_or_none()
        if not sc:
            raise BizException(ErrorCode.NOT_FOUND, "场景不存在")
    return ok(_scene_out(sc))


@router.post("/scenes")
async def create_scene(body: SceneIn, me=Depends(get_current_user)):
    """新建场景；code 已存在则报错。"""
    async with async_session() as s:
        if (await s.execute(select(Scene).where(Scene.code == body.code))).scalar_one_or_none():
            raise BizException(ErrorCode.PARAM_ERROR, f"场景 {body.code} 已存在")
        sc = Scene(code=body.code, name=body.name, description=body.description, config=body.config)
        s.add(sc)
        await s.commit()
        await s.refresh(sc)
    return ok(_scene_out(sc))


@router.put("/scenes/{scene_id}")
async def update_scene(scene_id: str, body: SceneUpdate, me=Depends(get_current_user)):
    """更新场景（部分更新，不改 code）。"""
    async with async_session() as s:
        sc = (await s.execute(select(Scene).where(Scene.id == scene_id))).scalar_one_or_none()
        if not sc:
            raise BizException(ErrorCode.NOT_FOUND, "场景不存在")
        if body.name is not None:
            sc.name = body.name
        if body.description is not None:
            sc.description = body.description
        if body.config is not None:
            sc.config = body.config
        await s.commit()
        await s.refresh(sc)
    return ok(_scene_out(sc))


@router.delete("/scenes/{scene_id}")
async def delete_scene(scene_id: str, me=Depends(get_current_user)):
    """删除场景；内置场景（built_in）不可删除。"""
    async with async_session() as s:
        sc = (await s.execute(select(Scene).where(Scene.id == scene_id))).scalar_one_or_none()
        if not sc:
            raise BizException(ErrorCode.NOT_FOUND, "场景不存在")
        if sc.built_in:
            raise BizException(ErrorCode.FORBIDDEN, "内置场景不可删除")
        await s.delete(sc)
        await s.commit()
    return ok({"success": True})
