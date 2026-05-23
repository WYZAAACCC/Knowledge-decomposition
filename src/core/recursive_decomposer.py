"""
Improvement 4: 递归分解算法

真正实现"分层递归推导知识分解图"，而不是仅检索邻域。
"""
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from ..models import Node, Edge, KnowledgeGraph, NodeType, DERIVATION_EDGE_TYPES


# 递归终止条件：这些类型不需要进一步分解
STOP_TYPES = {
    NodeType.CONCEPT.value,
    NodeType.DEFINITION.value,
    NodeType.QUANTITY.value,
    NodeType.MATH_TOOL.value,
    NodeType.ASSUMPTION.value,
}


@dataclass
class DerivationTreeNode:
    """递归分解树的节点"""
    node_id: str
    node_type: str
    title: str
    children: List['DerivationTreeNode'] = field(default_factory=list)
    edge_ids: List[str] = field(default_factory=list)
    assumption_ids: List[str] = field(default_factory=list)
    proof_step_ids: List[str] = field(default_factory=list)
    depth: int = 0


class RecursiveDecomposer:
    """Improvement 4: 递归分解器

    从目标节点开始，递归向下分解到基础概念。
    """

    def __init__(self, nodes: Dict[str, Node], edges: List[Edge], max_depth: int = 5):
        self.nodes = nodes
        self.edges = edges
        self.max_depth = max_depth
        self._incoming: Dict[str, List[Edge]] = {}
        self._outgoing: Dict[str, List[Edge]] = {}
        self._build_index()

    def _build_index(self):
        """构建边索引"""
        for edge in self.edges:
            from_id = getattr(edge, 'from_', '')
            to_id = getattr(edge, 'to', '')
            if from_id and to_id:
                self._outgoing.setdefault(from_id, []).append(edge)
                self._incoming.setdefault(to_id, []).append(edge)

    def decompose(self, target_id: str, depth: int = 0) -> Optional[DerivationTreeNode]:
        """递归分解目标节点

        Args:
            target_id: 目标节点ID
            depth: 当前深度

        Returns:
            DerivationTreeNode 或 None
        """
        if target_id not in self.nodes:
            return None

        node = self.nodes[target_id]
        node_type = getattr(node, 'type', None)
        type_value = node_type.value if hasattr(node_type, 'value') else str(node_type)

        # 终止条件
        if depth >= self.max_depth or type_value in STOP_TYPES:
            return DerivationTreeNode(
                node_id=target_id,
                node_type=type_value,
                title=getattr(node, 'title', target_id),
                depth=depth,
            )

        # 获取所有前驱边（prerequisites）
        incoming = self._incoming.get(target_id, [])
        derivation_edges = [
            e for e in incoming
            if getattr(e, 'type', None) and e.type.value in {et.value for et in DERIVATION_EDGE_TYPES}
        ]

        if not derivation_edges:
            return DerivationTreeNode(
                node_id=target_id,
                node_type=type_value,
                title=getattr(node, 'title', target_id),
                depth=depth,
            )

        # 递归分解所有前驱
        children = []
        all_assumption_ids = []
        all_proof_ids = []
        all_edge_ids = []

        for edge in derivation_edges:
            prereq_id = getattr(edge, 'from_', '')
            if prereq_id and prereq_id != target_id:
                child = self.decompose(prereq_id, depth + 1)
                if child:
                    children.append(child)

            edge_id = getattr(edge, 'id', '')
            if edge_id:
                all_edge_ids.append(edge_id)

            for aid in getattr(edge, 'assumption_ids', []) or []:
                all_assumption_ids.append(aid)
            for pid in getattr(edge, 'proof_step_ids', []) or []:
                all_proof_ids.append(pid)

        return DerivationTreeNode(
            node_id=target_id,
            node_type=type_value,
            title=getattr(node, 'title', target_id),
            children=children,
            edge_ids=all_edge_ids,
            assumption_ids=all_assumption_ids,
            proof_step_ids=all_proof_ids,
            depth=depth,
        )

    def get_topological_order(self, tree: DerivationTreeNode) -> List[str]:
        """从分解树获取拓扑排序（基础→高层）"""
        order = []

        def _visit(t: DerivationTreeNode):
            for child in t.children:
                _visit(child)
            if t.node_id not in order:
                order.append(t.node_id)

        _visit(tree)
        return order

    def get_leaves(self, tree: DerivationTreeNode) -> Set[str]:
        """获取分解树的所有叶子节点（基础概念）"""
        if not tree.children:
            return {tree.node_id}
        leaves = set()
        for child in tree.children:
            leaves.update(self.get_leaves(child))
        return leaves

    def get_all_assumptions(self, tree: DerivationTreeNode) -> List[str]:
        """收集分解树中所有假设"""
        assumptions = list(tree.assumption_ids)
        for child in tree.children:
            assumptions.extend(self.get_all_assumptions(child))
        return list(set(assumptions))
