\"\"\"版本对比 API 端点。\"\"\"
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db.database import get_db
from app.exceptions import BizException, ErrorCode
from app.schemas.base import resp_ok
from app.services.version_diff_service import VersionDiffService

router = APIRouter(prefix=\"/workflows\", tags=[\"workflow-versions\"])


class VersionCompareRequest(BaseModel):
    old_version: int = Field(..., ge=1, description=\"旧版本号\")
    new_version: int = Field(..., ge=1, description=\"新版本号\")


class VersionHistoryResponse(BaseModel):
    version: int
    published_at: Optional[str]
    change_summary: Optional[dict]


@router.get(\"/versions/{workflow_id}/history\")
async def get_version_history(
    workflow_id: str,
    limit: int = 10,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    \"\"\"获取工作流版本历史。\"\"\"
    history = await VersionDiffService.get_version_history(
        workflow_id=workflow_id,
        db_session=db,
        limit=limit,
        offset=offset
    )
    return resp_ok({\"versions\": history})


@router.post(\"/versions/{workflow_id}/compare\")
async def compare_versions(
    workflow_id: str,
    data: VersionCompareRequest,
    db: AsyncSession = Depends(get_db)
):
    \"\"\"对比两个工作流版本。\"\"\"
    diff = await VersionDiffService.compare_versions(
        workflow_id=workflow_id,
        old_version=data.old_version,
        new_version=data.new_version,
        db_session=db
    )
    
    # 转换为响应格式
    return resp_ok({
        \"workflow_id\": diff.workflow_id,
        \"old_version\": diff.old_version,
        \"new_version\": diff.new_version,
        \"summary\": diff.summary,
        \"nodes\": {
            \"added\": diff.nodes_added,
            \"removed\": diff.nodes_removed,
            \"modified\": [
                {
                    \"node_id\": n.node_id,
                    \"change_type\": n.change_type.value,
                    \"old_config\": n.old_config,
                    \"new_config\": n.new_config,
                    \"diff_fields\": n.diff_fields
                }
                for n in diff.nodes_modified
            ]
        },
        \"edges\": {
            \"added\": diff.edges_added,
            \"removed\": diff.edges_removed
        },
        \"global_variables\": {
            \"changed\": diff.global_variables_changed,
            \"diff\": diff.global_variables_diff
        }
    })
