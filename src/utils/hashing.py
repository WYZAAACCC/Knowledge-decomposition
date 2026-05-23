"""
哈希工具

用于计算图哈希，支持确定性测试。
"""

import hashlib
import json
from typing import Any, Dict, List, Union, Tuple


def compute_graph_hash(graph_data: Dict[str, Any]) -> str:
    """
    计算知识图谱的确定性哈希

    步骤:
    1. 对节点和边进行规范化排序
    2. 移除非确定性字段（如时间戳、随机ID）
    3. 计算SHA256哈希

    Args:
        graph_data: 图谱数据字典

    Returns:
        16进制哈希字符串
    """
    # 创建规范化副本
    normalized = _normalize_graph_data(graph_data)

    # 转换为规范的JSON字符串
    # 使用sort_keys确保顺序一致
    json_str = json.dumps(normalized, sort_keys=True, ensure_ascii=False)

    # 计算哈希
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()


def _normalize_graph_data(graph_data: Dict[str, Any]) -> Dict[str, Any]:
    """规范化图谱数据"""
    normalized = {}

    # 复制确定性的字段
    for key in ['topic', 'build_version', 'nodes', 'edges',
                'canonical_path', 'alternate_paths']:
        if key in graph_data:
            normalized[key] = graph_data[key]

    # 规范化节点
    if 'nodes' in normalized:
        normalized['nodes'] = _normalize_nodes(normalized['nodes'])

    # 规范化边
    if 'edges' in normalized:
        normalized['edges'] = _normalize_edges(normalized['edges'])

    # 规范化路径列表（排序）
    if 'alternate_paths' in normalized:
        normalized['alternate_paths'] = sorted(normalized['alternate_paths'])

    # 移除非确定性字段
    if 'build_metadata' in graph_data:
        # 保留种子来源信息，移除时间戳
        metadata = graph_data['build_metadata'].copy()
        metadata.pop('build_timestamp', None)
        metadata.pop('build_duration_seconds', None)
        if metadata:  # 只添加非空元数据
            normalized['build_metadata'] = metadata

    return normalized


def _normalize_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """规范化节点列表"""
    normalized_nodes = []

    for node in nodes:
        norm_node = node.copy()

        # 移除可能非确定性的字段
        norm_node.pop('validity', None)  # validity.notes可能包含非确定性文本

        # 规范化列表字段（排序）
        for list_field in ['aliases', 'tags', 'sources']:
            if list_field in norm_node and norm_node[list_field]:
                norm_node[list_field] = sorted(norm_node[list_field])

        normalized_nodes.append(norm_node)

    # 按ID排序
    normalized_nodes.sort(key=lambda x: x.get('id', ''))

    return normalized_nodes


def _normalize_edges(edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """规范化边列表"""
    normalized_edges = []

    for edge in edges:
        norm_edge = edge.copy()

        # 移除可能非确定性的字段
        norm_edge.pop('verified', None)
        norm_edge.pop('confidence', None)
        norm_edge.pop('failure_conditions', None)

        # 规范化列表字段（排序）
        for list_field in ['assumptions', 'derivation_steps', 'math_used',
                          'approximation_tags']:
            if list_field in norm_edge and norm_edge[list_field]:
                norm_edge[list_field] = sorted(norm_edge[list_field])

        normalized_edges.append(norm_edge)

    # 按ID排序
    normalized_edges.sort(key=lambda x: x.get('id', ''))

    return normalized_edges


def hash_strings(strings: List[str]) -> str:
    """计算字符串列表的哈希"""
    # 排序确保顺序一致
    sorted_strings = sorted(strings)
    combined = "|".join(sorted_strings)
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def are_graphs_equivalent(graph1: Dict[str, Any], graph2: Dict[str, Any],
                          tolerance: float = 0.9) -> Tuple[bool, float]:
    """
    比较两个图谱的等价性

    Args:
        graph1: 第一个图谱
        graph2: 第二个图谱
        tolerance: 相似度容忍度（0-1）

    Returns:
        (是否等价, 相似度)
    """
    hash1 = compute_graph_hash(graph1)
    hash2 = compute_graph_hash(graph2)

    if hash1 == hash2:
        return True, 1.0

    # 如果哈希不同，计算更细致的相似度
    similarity = _calculate_graph_similarity(graph1, graph2)
    return similarity >= tolerance, similarity


def _calculate_graph_similarity(graph1: Dict[str, Any],
                                graph2: Dict[str, Any]) -> float:
    """计算图谱相似度"""
    # 简单实现：基于共同节点的比例
    nodes1 = set(node['id'] for node in graph1.get('nodes', []))
    nodes2 = set(node['id'] for node in graph2.get('nodes', []))

    if not nodes1 and not nodes2:
        return 1.0

    intersection = nodes1 & nodes2
    union = nodes1 | nodes2

    return len(intersection) / len(union)


class DeterministicHasher:
    """确定性哈希器"""

    def __init__(self):
        self._cache: Dict[str, str] = {}

    def hash(self, data: Any) -> str:
        """计算数据的确定性哈希"""
        if isinstance(data, (dict, list)):
            # 规范化并序列化
            if isinstance(data, dict):
                normalized = _normalize_graph_data(data)
            else:
                normalized = data  # 简单列表

            json_str = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(json_str.encode('utf-8')).hexdigest()
        else:
            # 简单类型
            str_repr = str(data)
            return hashlib.sha256(str_repr.encode('utf-8')).hexdigest()

    def cached_hash(self, key: str, data: Any) -> str:
        """带缓存的哈希计算"""
        if key in self._cache:
            return self._cache[key]

        hash_value = self.hash(data)
        self._cache[key] = hash_value
        return hash_value

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()