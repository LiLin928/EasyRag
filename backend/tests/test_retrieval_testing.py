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


@pytest.fixture
def mock_test_set(test_kb_id):
    """创建模拟测试集对象。"""
    test_set = MagicMock(spec=RetrievalTestSet)
    test_set.id = uuid.uuid4()
    test_set.kb_id = uuid.UUID(test_kb_id)
    test_set.name = "招标检索基线"
    test_set.description = "招标文档检索质量基准"
    test_set.archived = False
    test_set.created_at = None
    test_set.updated_at = None
    return test_set


@pytest.fixture
def mock_test_case(test_set_id):
    """创建模拟测试用例对象。"""
    case = MagicMock(spec=RetrievalTestCase)
    case.id = uuid.uuid4()
    case.test_set_id = uuid.UUID(test_set_id)
    case.query = "测试查询"
    case.expected_doc_ids = []
    case.expected_chunk_ids = []
    case.tags = ["tag1", "tag2"]
    case.enabled = True
    case.sort_order = 0
    case.created_at = None
    case.updated_at = None
    return case


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
async def test_create_test_set_valid(client: AsyncClient, auth_headers: dict, test_kb_id, mock_test_set):
    """测试创建测试集的有效请求格式。"""
    # Mock 服务层函数
    with patch('app.services.retrieval_test_service.create_test_set', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_test_set

        response = await client.post(
            f"/api/v2/knowledge/{test_kb_id}/retrieval-test-sets",
            json={
                "name": "招标检索基线",
                "description": "招标文档检索质量基准"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        # 验证响应格式
        assert data["code"] == 0
        assert "message" in data
        assert "data" in data
        assert data["data"]["name"] == mock_test_set.name


@pytest.mark.asyncio
async def test_list_test_sets_format(client: AsyncClient, auth_headers: dict, test_kb_id, mock_test_set):
    """测试测试集列表响应格式。"""
    # Mock 服务层函数
    with patch('app.services.retrieval_test_service.list_test_sets', new_callable=AsyncMock) as mock_list:
        mock_list.return_value = ([mock_test_set], 1)

        response = await client.get(
            f"/api/v2/knowledge/{test_kb_id}/retrieval-test-sets",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # 验证响应格式
        assert data["code"] == 0
        assert "message" in data
        assert "data" in data
        assert "list" in data["data"]
        assert "total" in data["data"]
        assert data["data"]["total"] == 1
        assert len(data["data"]["list"]) == 1


@pytest.mark.asyncio
async def test_get_test_set_format(client: AsyncClient, auth_headers: dict, test_set_id, mock_test_set):
    """测试获取测试集详情的响应格式。"""
    # Mock 服务层函数
    with patch('app.services.retrieval_test_service.get_test_set', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_test_set

        response = await client.get(
            f"/api/v2/retrieval-test-sets/{test_set_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # 验证响应格式
        assert data["code"] == 0
        assert "message" in data
        assert "data" in data


@pytest.mark.asyncio
async def test_update_test_set_format(client: AsyncClient, auth_headers: dict, test_set_id, mock_test_set):
    """测试更新测试集的响应格式。"""
    # Mock 服务层函数
    with patch('app.services.retrieval_test_service.update_test_set', new_callable=AsyncMock) as mock_update:
        mock_update.return_value = mock_test_set

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
        assert data["code"] == 0
        assert "message" in data


@pytest.mark.asyncio
async def test_delete_test_set_format(client: AsyncClient, auth_headers: dict, test_set_id):
    """测试删除测试集的响应格式。"""
    # Mock 服务层函数
    with patch('app.services.retrieval_test_service.delete_test_set', new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = None

        response = await client.delete(
            f"/api/v2/retrieval-test-sets/{test_set_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # 验证响应格式
        assert data["code"] == 0
        assert "message" in data


@pytest.mark.asyncio
async def test_create_test_case(client: AsyncClient, auth_headers: dict, test_set_id, mock_test_case):
    """测试创建测试用例。"""
    # Mock 服务层函数
    with patch('app.services.retrieval_test_service.create_case', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_test_case

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
        assert data["code"] == 0
        assert "message" in data


@pytest.mark.asyncio
async def test_list_test_cases(client: AsyncClient, auth_headers: dict, test_set_id, mock_test_case):
    """测试列出测试用例。"""
    # Mock 服务层函数
    with patch('app.services.retrieval_test_service.list_cases', new_callable=AsyncMock) as mock_list:
        mock_list.return_value = ([mock_test_case], 1)

        response = await client.get(
            f"/api/v2/retrieval-test-sets/{test_set_id}/cases",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "message" in data
        assert "data" in data
        assert "list" in data["data"]
        assert "total" in data["data"]