"""
规范化器

负责节点、边和路径的规范化，确保一致性。
"""

from typing import Dict, List, Optional, Set, Tuple
from .models import Node, Edge
from .loader import DataLoader


class Canonicalizer:
    """规范化器"""

    def __init__(self, loader: Optional[DataLoader] = None):
        """
        初始化

        Args:
            loader: 数据加载器
        """
        self.loader = loader or DataLoader()
        self._aliases_cache: Optional[Dict[str, List[str]]] = None

    def normalize_topic(self, topic_text: str) -> Tuple[str, float]:
        """
        规范化主题文本

        Args:
            topic_text: 原始主题文本

        Returns:
            (规范化主题ID, 置信度)
        """
        if not topic_text:
            return "", 0.0

        # 加载别名映射
        aliases = self._get_aliases()

        # 精确匹配
        for topic_id, alias_list in aliases.items():
            if topic_text == topic_id:
                return topic_id, 1.0

            # 检查别名
            for alias in alias_list:
                if topic_text.lower() == alias.lower():
                    return topic_id, 0.95

        # 部分匹配（包含关系）
        for topic_id, alias_list in aliases.items():
            if topic_text.lower() in topic_id.lower():
                return topic_id, 0.8

            for alias in alias_list:
                if topic_text.lower() in alias.lower():
                    return topic_id, 0.7

        # 无法识别
        return "", 0.0

    def _get_aliases(self) -> Dict[str, List[str]]:
        """获取别名映射（带缓存）"""
        if self._aliases_cache is None:
            self._aliases_cache = self.loader.load_aliases()
        return self._aliases_cache

    def normalize_node(self, node_data: Dict) -> Dict:
        """
        规范化节点数据

        Args:
            node_data: 原始节点数据

        Returns:
            规范化后的节点数据
        """
        normalized = node_data.copy()

        # 确保必需字段
        if "abstraction_level" not in normalized:
            normalized["abstraction_level"] = 0
        if "pedagogical_level" not in normalized:
            normalized["pedagogical_level"] = 1
        if "theory_context" not in normalized:
            normalized["theory_context"] = "classical"
        if "status" not in normalized:
            normalized["status"] = "canonical"

        # 规范化列表字段
        for list_field in ["aliases", "tags", "sources"]:
            if list_field in normalized:
                if isinstance(normalized[list_field], str):
                    normalized[list_field] = [normalized[list_field]]
                elif not isinstance(normalized[list_field], list):
                    normalized[list_field] = []

        # 排序列表字段（确保一致性）
        for list_field in ["aliases", "tags", "sources"]:
            if list_field in normalized and normalized[list_field]:
                normalized[list_field] = sorted(set(normalized[list_field]))

        return normalized

    def normalize_edge(self, edge_data: Dict) -> Dict:
        """
        规范化边数据

        Args:
            edge_data: 原始边数据

        Returns:
            规范化后的边数据
        """
        normalized = edge_data.copy()

        # 确保必需字段
        if "assumptions" not in normalized:
            normalized["assumptions"] = []
        if "derivation_steps" not in normalized:
            normalized["derivation_steps"] = []
        if "math_used" not in normalized:
            normalized["math_used"] = []
        if "approximation_tags" not in normalized:
            normalized["approximation_tags"] = []

        # 规范化列表字段
        for list_field in ["assumptions", "derivation_steps", "math_used",
                          "approximation_tags", "failure_conditions"]:
            if list_field in normalized:
                if isinstance(normalized[list_field], str):
                    normalized[list_field] = [normalized[list_field]]
                elif not isinstance(normalized[list_field], list):
                    normalized[list_field] = []

        # 排序列表字段（确保一致性）
        for list_field in ["assumptions", "math_used", "approximation_tags",
                          "failure_conditions"]:
            if list_field in normalized and normalized[list_field]:
                normalized[list_field] = sorted(set(normalized[list_field]))

        return normalized

    def deduplicate_nodes(self, nodes: List[Node]) -> List[Node]:
        """
        去重节点

        Args:
            nodes: 节点列表

        Returns:
            去重后的节点列表
        """
        seen_ids: Set[str] = set()
        unique_nodes: List[Node] = []

        for node in nodes:
            if node.id not in seen_ids:
                seen_ids.add(node.id)
                unique_nodes.append(node)
            else:
                # 可以选择合并或跳过
                # 当前实现：跳过重复项
                pass

        return unique_nodes

    def deduplicate_edges(self, edges: List[Edge]) -> List[Edge]:
        """
        去重边

        Args:
            edges: 边列表

        Returns:
            去重后的边列表
        """
        seen_keys: Set[Tuple[str, str, str]] = set()
        unique_edges: List[Edge] = []

        for edge in edges:
            key = (edge.from_, edge.to, edge.type)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_edges.append(edge)
            else:
                # 可以选择合并或跳过
                # 当前实现：跳过重复项
                pass

        return unique_edges

    def sort_nodes_for_determinism(self, nodes: List[Node]) -> List[Node]:
        """
        为确定性排序节点

        Args:
            nodes: 节点列表

        Returns:
            排序后的节点列表
        """
        return sorted(nodes, key=lambda n: n.id)

    def sort_edges_for_determinism(self, edges: List[Edge]) -> List[Edge]:
        """
        为确定性排序边

        Args:
            edges: 边列表

        Returns:
            排序后的边列表
        """
        return sorted(edges, key=lambda e: (e.from_, e.to, e.type))

    def generate_path_id(self, nodes: List[str], prefix: str = "path") -> str:
        """
        生成路径ID

        Args:
            nodes: 路径上的节点ID列表
            prefix: 前缀

        Returns:
            路径ID
        """
        if not nodes:
            return f"{prefix}.empty"

        # 使用前几个节点的哈希作为后缀
        from .utils.hashing import hash_strings
        nodes_str = "_".join(nodes[:3])  # 使用前3个节点
        if len(nodes) > 3:
            nodes_str += f"_and_{len(nodes)-3}_more"

        # 清理特殊字符
        nodes_str = nodes_str.replace(".", "_").replace("-", "_")

        return f"{prefix}.{nodes_str}"

    def validate_node_consistency(self, node: Node, seeds: Dict) -> Tuple[bool, List[str]]:
        """
        验证节点与种子数据的一致性

        Args:
            node: 要验证的节点
            seeds: 种子数据

        Returns:
            (是否一致, 警告列表)
        """
        warnings = []

        # 检查节点是否在种子中存在
        seed_node = self.loader.get_node_by_id(node.id, seeds)
        if seed_node:
            # 验证字段一致性
            if node.type != seed_node.type:
                warnings.append(f"节点类型不一致: {node.type} vs {seed_node.type}")

            if node.domain != seed_node.domain:
                warnings.append(f"学科域不一致: {node.domain} vs {seed_node.domain}")

        return len(warnings) == 0, warnings