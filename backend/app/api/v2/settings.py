"""settings 路由：/settings/models（模型配置 CRUD）。

Task 9 将扩展 /settings/scenes（场景 CRUD）。响应统一为 {code,message,data}。
"""
from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import delete, select

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import async_session
from app.models.model_config import ModelConfig
from app.schemas.settings import ModelDef, ModelOut
from app.security.crypto import encrypt
from app.services.settings_service import set_default_model, upsert_model

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/models")
async def list_models(group: str | None = None, me=Depends(get_current_user)):
    """列出模型配置，可选按 group 过滤；不回传 key，仅返回 has_key。"""
    async with async_session() as s:
        q = select(ModelConfig)
        if group:
            q = q.where(ModelConfig.grp == group)
        rows = (await s.execute(q)).scalars().all()
    return ok([ModelOut(
        id=str(r.id), grp=r.grp, name=r.name, prov=r.prov, use=r.use,
        url=r.url, has_key=bool(r.api_key_enc), is_default=r.is_default,
        params=r.params,
    ).model_dump() for r in rows])


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
    return ok({"name": saved.name, "grp": group})


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
