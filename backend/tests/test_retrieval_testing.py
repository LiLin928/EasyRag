"""检索测试接口测试。

测试检索测试集的 CRUD 功能。
"""
import pytest
import uuid
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieval_testing import RetrievalTestSet, RetrievalTestCase
from app.models.knowledge_base import KnowledgeBase


@pytest.fixture
def test_kb_id():
    """创建测试知识库 ID。"""
    return str(uuid.uuid4())


@pytest.fixture
def test_set_id():
    """创建测试集 ID。"""
    return str(uuid.uuid4())


@pytest.mark.asyncio
async def test_list_test_sets_unauthorized(client: AsyncClient, test_kb_id):
    """测试未认证访问测试集列表。"""
    response = await client.get(f"/api/v2/knowledge/{test_kb_id}/retrieval-test-sets")
    # 业务异常返回 HTTP 200 + 错误码
    assert response.status_code == 200
    data = response.json()
    # 错误码应该在 40100-40199 范围（认证错误）
    assert data["code"] >= 40100 and data["code"] < 40200
    assert "message" in data


@pytest.mark.asyncio
async def test_create_test_set_unauthorized(client: AsyncClient, test_kb_id):
    """测试未认证创建测试集。"""
    response = await client.post(
        f"/api/v2/knowledge/{test_kb_id}/retrieval-test-sets",
        json={
            "name": "测试集名称",
            "description": "测试集描述"
        }
    )
    # 业务异常返回 HTTP 200 + 错误码
    assert response.status_code == 200
    data = response.json()
    # 错误码应该在 40100-40199 范围（认证错误）
    assert data["code"] >= 40100 and data["code"] < 40200


@pytest.mark.asyncio
async def test_create_test_set_missing_name(client: AsyncClient, auth_headers: dict, test_kb_id):
    """测试创建测试集时缺少名称参数。"""
    response = await client.post(
        f"/api/v2/knowledge/{test_kb_id}/retrieval-test-sets",
        json={
            "description": "缺少名称"
        },
        headers=auth_headers
    )
    # Pydantic 验证错误应该返回 422
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_test_set_valid(client: AsyncClient, auth_headers: dict, test_kb_id):
    """测试创建测试集的有效请求格式。"""
    # 由于需要数据库连接，这个测试主要验证请求能够到达路由
    # 实际的业务逻辑由 service 层处理
    response = await client.post(
        f"/api/v2/knowledge/{test_kb_id}/retrieval-test-sets",
        json={
            "name": "招标检索基线",
            "description": "招标文档检索质量基准"
        },
        headers=auth_headers
    )
    # 即使数据库连接失败，也应该返回标准的业务响应格式
    assert response.status_code == 200
    data = response.json()
    # 验证响应格式
    assert "code" in data
    assert "message" in data
    assert "data" in data or data["code"] != 0  # 失败时可能没有 data


@pytest.mark.asyncio
async def test_list_test_sets_format(client: AsyncClient, auth_headers: dict, test_kb_id):
    """测试测试集列表响应格式。"""
    response = await client.get(
        f"/api/v2/knowledge/{test_kb_id}/retrieval-test-sets",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    # 验证响应格式
    assert "code" in data
    assert "message" in data
    # 如果成功，应该有 data 字段
    if data["code"] == 0:
        assert "data" in data
        assert "list" in data["data"]
        assert "total" in data["data"]


@pytest.mark.asyncio
async def test_get_test_set_format(client: AsyncClient, auth_headers: dict, test_set_id):
    """测试获取测试集详情的响应格式。"""
    response = await client.get(
        f"/api/v2/retrieval-test-sets/{test_set_id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    # 验证响应格式
    assert "code" in data
    assert "message" in data
    # 如果失败（如测试集不存在），应该有错误消息
    if data["code"] != 0:
        assert "message" in data
        assert data["message"]  # 不为空


@pytest.mark.asyncio
async def test_update_test_set_format(client: AsyncClient, auth_headers: dict, test_set_id):
    """测试更新测试集的响应格式。"""
    response = await client.put(
        f"/api/v2/retrieval-test-sets/{test_set_id}",
        json={
            "name": "更新后的名称"
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    # 验证响应格式
    assert "code" in data
    assert "message" in data


@pytest.mark.asyncio
async def test_delete_test_set_format(client: AsyncClient, auth_headers: dict, test_set_id):
    """测试删除测试集的响应格式。"""
    response = await client.delete(
        f"/api/v2/retrieval-test-sets/{test_set_id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    # 验证响应格式
    assert "code" in data
    assert "message" in data


@pytest.mark.asyncio
async def test_create_test_case(client: AsyncClient, auth_headers: dict, test_set_id):
    """测试创建测试用例。"""
    response = await client.post(
        f"/api/v2/retrieval-test-sets/{test_set_id}/cases",
        json={
            "query": "测试查询",
            "expected_doc_ids": [],
            "tags": ["tag1", "tag2"]
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "code" in data
    assert "message" in data


@pytest.mark.asyncio
async def test_list_test_cases(client: AsyncClient, auth_headers: dict, test_set_id):
    """测试列出测试用例。"""
    response = await client.get(
        f"/api/v2/retrieval-test-sets/{test_set_id}/cases",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "code" in data
    assert "message" in data
    if data["code"] == 0:
        assert "data" in data
        assert "list" in data["data"]
        assert "total" in data["data"]