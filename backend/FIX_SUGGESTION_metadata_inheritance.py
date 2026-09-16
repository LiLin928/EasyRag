"""修复建议：子分段切分时继承元素的 metadata

问题：parent_child_chunker.py 在切分子分段时，只设置了 parent_title 和 parent_level，
没有继承元素的 metadata 字段，导致元数据过滤失效。

修复：从元素中继承所有 metadata 字段。
"""

# 在 parent_child_chunker.py 中修改 chunk 方法：

async def chunk(
    self,
    tree_nodes: List[dict],
    elements: List[DocumentElement],
    doc_id: str,
    kb_id: str
) -> List[dict]:
    """生成父子分段"""

    child_chunks = []

    for node in tree_nodes:
        # 1. 获取该节点的所有元素
        node_elements = self._get_elements_by_node(node, elements)

        if not node_elements:
            continue

        # 2. 合并元素 metadata（修复点）
        element_metadata = {}
        for elem in node_elements:
            if elem.metadata:
                element_metadata.update(elem.metadata)

        # 3. 生成父分段内容
        parent_content = '\n\n'.join(
            elem.content for elem in node_elements if elem.content
        )

        if not parent_content.strip():
            continue

        # 4. 判断是否需要切分
        if len(parent_content) <= self.child_chunk_size:
            # 短章节：单个子分段
            child_chunks.append({
                'doc_id': doc_id,
                'kb_id': kb_id,
                'tree_node_id': node['node_id'],
                'position': 1,
                'content': parent_content,
                'char_count': len(parent_content),
                'metadata': {
                    'parent_title': node['title'],
                    'parent_level': node['level'],
                    **element_metadata,  # ← 修复：继承元素的 metadata
                }
            })
        else:
            # 长章节：切分为多个子分段
            sub_chunks = self._split_parent_content(parent_content)

            for i, sub_content in enumerate(sub_chunks, start=1):
                child_chunks.append({
                    'doc_id': doc_id,
                    'kb_id': kb_id,
                    'tree_node_id': node['node_id'],
                    'position': i,
                    'content': sub_content,
                    'char_count': len(sub_content),
                    'metadata': {
                        'parent_title': node['title'],
                        'parent_level': node['level'],
                        **element_metadata,  # ← 修复：继承元素的 metadata
                    }
                })

    logger.info(f"Generated {len(child_chunks)} child chunks")
    return child_chunks