\"\"\"工作流版本对比服务。\"\"\"
from typing import Any, Optional
from dataclasses import dataclass
from enum import Enum

from app.exceptions import BizException, ErrorCode
from app.models.workflow import Workflow, WorkflowVersion


class ChangeType(Enum):
    \"\"\"变更类型。\"\"\"
    ADDED = \"added\"
    REMOVED = \"removed\"
    MODIFIED = \"modified\"
    UNCHANGED = \"unchanged\"


@dataclass
class NodeChange:
    \"\"\"节点变更。\"\"\"
    node_id: str
    change_type: ChangeType
    old_config: Optional[dict] = None
    new_config: Optional[dict] = None
    diff_fields: list[str] = None


@dataclass
class EdgeChange:
    \"\"\"边变更。\"\"\"
    edge_id: str
    source: str
    target: str
    change_type: ChangeType


@dataclass
class WorkflowDiff:
    \"\"\"工作流版本对比结果。\"\"\"
    workflow_id: str
    old_version: int
    new_version: int
    nodes_added: list[dict]
    nodes_removed: list[dict]
    nodes_modified: list[NodeChange]
    edges_added: list[dict]
    edges_removed: list[dict]
    global_variables_changed: bool
    global_variables_diff: dict
    summary: str


class VersionDiffService:
    \"\"\"工作流版本对比服务。\"\"\"
    
    @staticmethod
    def _get_node_map(definition: dict) -> dict[str, dict]:
        \"\"\"获取节点ID到配置的映射。\"\"\"
        nodes = definition.get(\"nodes\", [])
        return {node.get(\"id\"): node for node in nodes if node.get(\"id\")}
    
    @staticmethod
    def _get_edge_map(definition: dict) -> dict[str, dict]:
        \"\"\"获取边ID到配置的映射。\"\"\"
        edges = definition.get(\"edges\", [])
        return {edge.get(\"id\"): edge for edge in edges if edge.get(\"id\")}
    
    @staticmethod
    def _compute_dict_diff(old_dict: dict, new_dict: dict) -> list[str]:
        \"\"\"计算两个字典的差异字段。\"\"\"
        all_keys = set(old_dict.keys()) | set(new_dict.keys())
        diff_fields = []
        
        for key in all_keys:
            old_val = old_dict.get(key)
            new_val = new_dict.get(key)
            
            # 简单比较，对于复杂嵌套结构可能需要递归
            if isinstance(old_val, (list, dict)) and isinstance(new_val, (list, dict)):
                if old_val != new_val:
                    diff_fields.append(key)
            elif old_val != new_val:
                diff_fields.append(key)
        
        return diff_fields
    
    @classmethod
    async def compare_versions(
        cls,
        workflow_id: str,
        old_version: int,
        new_version: int,
        db_session
    ) -> WorkflowDiff:
        \"\"\"对比两个工作流版本。
        
        Args:
            workflow_id: 工作流ID
            old_version: 旧版本号
            new_version: 新版本号
            db_session: 数据库会话
            
        Returns:
            版本对比结果
        \"\"\"
        # 查询版本
        from sqlalchemy import select
        result = await db_session.execute(
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .where(WorkflowVersion.version.in_([old_version, new_version]))
        )
        versions = result.scalars().all()
        
        if len(versions) != 2:
            raise BizException(
                ErrorCode.NOT_FOUND,
                f\"Version {old_version} or {new_version} not found for workflow {workflow_id}\"
            )
        
        # 获取定义
        version_map = {v.version: v for v in versions}
        old_def = version_map[old_version].definition_snapshot
        new_def = version_map[new_version].definition_snapshot
        
        # 对比节点
        old_nodes = cls._get_node_map(old_def)
        new_nodes = cls._get_node_map(new_def)
        
        nodes_added = []
        nodes_removed = []
        nodes_modified = []
        
        # 检查新增和修改的节点
        for node_id, new_node in new_nodes.items():
            if node_id not in old_nodes:
                nodes_added.append(new_node)
            else:
                old_node = old_nodes[node_id]
                diff_fields = cls._compute_dict_diff(old_node, new_node)
                if diff_fields:
                    nodes_modified.append(NodeChange(
                        node_id=node_id,
                        change_type=ChangeType.MODIFIED,
                        old_config=old_node,
                        new_config=new_node,
                        diff_fields=diff_fields
                    ))
        
        # 检查删除的节点
        for node_id, old_node in old_nodes.items():
            if node_id not in new_nodes:
                nodes_removed.append(old_node)
        
        # 对比边
        old_edges = cls._get_edge_map(old_def)
        new_edges = cls._get_edge_map(new_def)
        
        edges_added = []
        edges_removed = []
        
        for edge_id, new_edge in new_edges.items():
            if edge_id not in old_edges:
                edges_added.append(new_edge)
        
        for edge_id, old_edge in old_edges.items():
            if edge_id not in new_edges:
                edges_removed.append(old_edge)
        
        # 对比全局变量
        old_globals = old_def.get(\"global_variables\", {})
        new_globals = new_def.get(\"global_variables\", {})
        globals_diff = cls._compute_dict_diff(old_globals, new_globals)
        
        # 生成摘要
        summary = cls._generate_summary(
            len(nodes_added), len(nodes_removed), len(nodes_modified),
            len(edges_added), len(edges_removed), len(globals_diff)
        )
        
        return WorkflowDiff(
            workflow_id=workflow_id,
            old_version=old_version,
            new_version=new_version,
            nodes_added=nodes_added,
            nodes_removed=nodes_removed,
            nodes_modified=nodes_modified,
            edges_added=edges_added,
            edges_removed=edges_removed,
            global_variables_changed=len(globals_diff) > 0,
            global_variables_diff={\"changed\": globals_diff},
            summary=summary
        )
    
    @staticmethod
    def _generate_summary(
        nodes_added: int,
        nodes_removed: int,
        nodes_modified: int,
        edges_added: int,
        edges_removed: int,
        globals_changed: int
    ) -> str:
        \"\"\"生成变更摘要。\"\"\"
        parts = []
        if nodes_added:
            parts.append(f\"{nodes_added} node(s) added\")
        if nodes_removed:
            parts.append(f\"{nodes_removed} node(s) removed\")
        if nodes_modified:
            parts.append(f\"{nodes_modified} node(s) modified\")
        if edges_added:
            parts.append(f\"{edges_added} edge(s) added\")
        if edges_removed:
            parts.append(f\"{edges_removed} edge(s) removed\")
        if globals_changed:
            parts.append(f\"{globals_changed} global variable(s) changed\")
        
        if not parts:
            return \"No changes detected\"
        
        return \"; \".join(parts)
    
    @classmethod
    async def get_version_history(
        cls,
        workflow_id: str,
        db_session,
        limit: int = 10,
        offset: int = 0
    ) -> list[dict]:
        \"\"\"获取工作流版本历史。
        
        Args:
            workflow_id: 工作流ID
            db_session: 数据库会话
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            版本历史列表
        \"\"\"
        from sqlalchemy import select
        result = await db_session.execute(
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .order_by(WorkflowVersion.version.desc())
            .limit(limit)
            .offset(offset)
        )
        versions = result.scalars().all()
        
        return [
            {
                \"version\": v.version,
                \"published_at\": v.published_at.isoformat() if v.published_at else None,
                \"change_summary\": v.change_summary
            }
            for v in versions
        ]
