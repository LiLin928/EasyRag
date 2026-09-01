\"\"\"测试版本对比服务。\"\"\"
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.version_diff_service import VersionDiffService, ChangeType


class TestVersionDiffService:
    \"\"\"测试版本对比服务。\"\"\"
    
    def test_get_node_map(self):
        definition = {
            \"nodes\": [
                {\"id\": \"node1\", \"type\": \"start\"},
                {\"id\": \"node2\", \"type\": \"end\"}
            ]
        }
        result = VersionDiffService._get_node_map(definition)
        assert \"node1\" in result
        assert \"node2\" in result
        assert result[\"node1\"][\"type\"] == \"start\"
    
    def test_get_edge_map(self):
        definition = {
            \"edges\": [
                {\"id\": \"edge1\", \"source\": \"node1\", \"target\": \"node2\"}
            ]
        }
        result = VersionDiffService._get_edge_map(definition)
        assert \"edge1\" in result
        assert result[\"edge1\"][\"source\"] == \"node1\"
    
    def test_compute_dict_diff(self):
        old = {\"a\": 1, \"b\": 2, \"c\": [1, 2]}
        new = {\"a\": 1, \"b\": 3, \"d\": 4}
        result = VersionDiffService._compute_dict_diff(old, new)
        assert \"b\" in result  # 修改
        assert \"c\" in result  # 删除
        assert \"d\" in result  # 新增
    
    def test_generate_summary(self):
        summary = VersionDiffService._generate_summary(1, 2, 3, 4, 5, 6)
        assert \"1 node(s) added\" in summary
        assert \"2 node(s) removed\" in summary
        assert \"3 node(s) modified\" in summary
    
    def test_generate_summary_empty(self):
        summary = VersionDiffService._generate_summary(0, 0, 0, 0, 0, 0)
        assert \"No changes\" in summary
