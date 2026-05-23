"""
Improvement 8: 图索引

预计算常用查询，避免每次全图 NetworkX 重建。
"""
from typing import Dict, List, Optional, Set
import networkx as nx

from ..models import Node, Edge, DERIVATION_EDGE_TYPES


class GraphIndex:
    """预计算图索引"""

    def __init__(self, nodes: List[Node] = None, edges: List[Edge] = None):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}

        # 邻接关系
        self.incoming: Dict[str, List[Edge]] = {}   # target → edges that point to it
        self.outgoing: Dict[str, List[Edge]] = {}   # source → edges that originate from it

        # 分类索引
        self.nodes_by_type: Dict[str, List[str]] = {}
        self.nodes_by_domain: Dict[str, List[str]] = {}
        self.nodes_by_alias: Dict[str, str] = {}

        # 推导DAG（只含 derivation edges）
        self.nx_derivation_dag: Optional[nx.DiGraph] = None
        # 应用图（只含 applies_to edges）
        self.nx_application_graph: Optional[nx.DiGraph] = None
        # 全图
        self.nx_full_graph: Optional[nx.DiGraph] = None

        if nodes and edges:
            self.build(nodes, edges)

    def build(self, nodes: List[Node], edges: List[Edge]):
        """构建所有索引"""
        # 节点映射
        for node in nodes:
            self.nodes[node.id] = node
            # 按类型索引
            t = node.type.value if hasattr(node.type, 'value') else str(node.type)
            self.nodes_by_type.setdefault(t, []).append(node.id)
            # 按领域索引
            d = node.domain.value if hasattr(node.domain, 'value') else str(node.domain)
            self.nodes_by_domain.setdefault(d, []).append(node.id)
            # 别名索引
            for alias in getattr(node, 'aliases', []) or []:
                self.nodes_by_alias[alias.lower()] = node.id
            self.nodes_by_alias[node.title.lower()] = node.id

        # 边映射和邻接索引
        for edge in edges:
            self.edges[edge.id] = edge
            self.outgoing.setdefault(edge.from_, []).append(edge)
            self.incoming.setdefault(edge.to, []).append(edge)

        # 构建NetworkX图
        self._build_nx_graphs()

    def _build_nx_graphs(self):
        """构建NetworkX图（derivation only, application only, full）"""
        self.nx_derivation_dag = nx.DiGraph()
        self.nx_application_graph = nx.DiGraph()
        self.nx_full_graph = nx.DiGraph()

        for node_id in self.nodes:
            self.nx_derivation_dag.add_node(node_id)
            self.nx_application_graph.add_node(node_id)
            self.nx_full_graph.add_node(node_id)

        deriv_types = {et.value for et in DERIVATION_EDGE_TYPES}

        for edge in self.edges.values():
            from_id = edge.from_
            to_id = edge.to

            if from_id in self.nx_full_graph and to_id in self.nx_full_graph:
                self.nx_full_graph.add_edge(from_id, to_id)

                if edge.type.value in deriv_types:
                    self.nx_derivation_dag.add_edge(from_id, to_id)
                elif edge.type.value == "applies_to":
                    self.nx_application_graph.add_edge(from_id, to_id)

    def get_prerequisites(self, node_id: str) -> List[Edge]:
        """获取某个节点的所有前驱边"""
        return self.incoming.get(node_id, [])

    def get_dependents(self, node_id: str) -> List[Edge]:
        """获取某个节点的所有后继边"""
        return self.outgoing.get(node_id, [])

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def is_reachable(self, from_id: str, to_id: str) -> bool:
        """检查 from_id 是否可到达 to_id"""
        if self.nx_derivation_dag and from_id in self.nx_derivation_dag:
            return nx.has_path(self.nx_derivation_dag, from_id, to_id)
        return False

    def find_path(self, from_id: str, to_id: str) -> Optional[List[str]]:
        """查找最短推导路径"""
        if self.nx_derivation_dag:
            try:
                return nx.shortest_path(self.nx_derivation_dag, from_id, to_id)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                return None
        return None

    def get_nodes_by_type(self, node_type: str) -> List[str]:
        return self.nodes_by_type.get(node_type, [])
