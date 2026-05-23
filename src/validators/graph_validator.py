"""
图结构验证器

验证推导图是否为DAG，检查悬空边、孤立节点等。
"""

from typing import Dict, List, Set, Tuple, Optional, Any
import networkx as nx

from ..models import Node, Edge, KnowledgeGraph, DERIVATION_EDGE_TYPES


class GraphValidator:
    """图结构验证器"""

    def __init__(self):
        """初始化"""
        pass

    def validate_dag(self, nodes: List[Node], edges: List[Edge]) -> Tuple[bool, List[str], Optional[nx.DiGraph]]:
        """
        验证推导图是否为DAG

        Args:
            nodes: 节点列表
            edges: 边列表

        Returns:
            (是否为DAG, 错误信息列表, 有向图对象)
        """
        errors = []

        # 创建有向图
        G = nx.DiGraph()

        # 添加节点
        for node in nodes:
            G.add_node(node.id, node_type=node.type)

        # Fix 7: 只对推导类边检查DAG
        derivation_edges = []
        for edge in edges:
            if edge.type in {e.value for e in DERIVATION_EDGE_TYPES}:
                if edge.from_ not in G or edge.to not in G:
                    errors.append(f"边 {edge.id} 引用了不存在的节点: {edge.from_} -> {edge.to}")
                else:
                    G.add_edge(edge.from_, edge.to, edge_id=edge.id, edge_type=edge.type)
                    derivation_edges.append(edge)

        # 检查环
        try:
            cycles = list(nx.simple_cycles(G))
            if cycles:
                for cycle in cycles:
                    cycle_str = " -> ".join(cycle)
                    errors.append(f"发现环: {cycle_str}")
                return False, errors, G
        except Exception as e:
            errors.append(f"检查环时出错: {str(e)}")
            return False, errors, G

        return True, errors, G

    def find_dangling_edges(self, nodes: List[Node], edges: List[Edge]) -> List[Edge]:
        """
        查找悬空边（引用了不存在的节点）

        Args:
            nodes: 节点列表
            edges: 边列表

        Returns:
            悬空边列表
        """
        node_ids = {node.id for node in nodes}
        dangling_edges = []

        for edge in edges:
            if edge.from_ not in node_ids:
                dangling_edges.append(edge)
            elif edge.to not in node_ids:
                dangling_edges.append(edge)

        return dangling_edges

    def find_isolated_nodes(self, nodes: List[Node], edges: List[Edge]) -> List[Node]:
        """
        查找孤立节点（没有边连接）

        Args:
            nodes: 节点列表
            edges: 边列表

        Returns:
            孤立节点列表
        """
        if not edges:
            return nodes.copy()  # 所有节点都是孤立的

        connected_nodes = set()
        for edge in edges:
            connected_nodes.add(edge.from_)
            connected_nodes.add(edge.to)

        isolated = []
        for node in nodes:
            if node.id not in connected_nodes:
                isolated.append(node)

        return isolated

    def validate_canonical_path(self, graph: KnowledgeGraph) -> Tuple[bool, List[str]]:
        """
        验证canonical path是否存在且有效

        Args:
            graph: 知识图谱

        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        # 检查canonical_path字段
        if not graph.canonical_path:
            errors.append("canonical_path字段为空")
            return False, errors

        # 检查路径ID格式
        if not graph.canonical_path.startswith("path."):
            errors.append(f"canonical_path格式不正确: {graph.canonical_path}")

        # 检查图中是否有边引用该路径
        path_edges = [edge for edge in graph.edges if edge.path_id == graph.canonical_path]
        if not path_edges:
            errors.append(f"没有边引用canonical_path: {graph.canonical_path}")

        # 检查路径是否连通
        if path_edges:
            path_node_ids = set()
            for edge in path_edges:
                path_node_ids.add(edge.from_)
                path_node_ids.add(edge.to)

            G = nx.DiGraph()
            for edge in path_edges:
                G.add_edge(edge.from_, edge.to)

            try:
                cycles = list(nx.simple_cycles(G))
                if cycles:
                    for cycle in cycles:
                        errors.append(f"路径 {graph.canonical_path} 中存在环: {' -> '.join(cycle)}")
            except Exception:
                pass

        return len(errors) == 0, errors

    def validate_graph_connectivity(self, nodes: List[Node], edges: List[Edge]) -> Tuple[bool, List[str], Dict]:
        """
        验证图连通性

        Args:
            nodes: 节点列表
            edges: 边列表

        Returns:
            (是否连通, 警告信息列表, 连通性详情)
        """
        warnings = []
        details = {
            "total_nodes": len(nodes),
            "connected_components": 0,
            "largest_component_size": 0,
            "isolated_nodes": 0
        }

        if not edges:
            warnings.append("图没有边，所有节点都是孤立的")
            details["isolated_nodes"] = len(nodes)
            details["connected_components"] = len(nodes)
            return False, warnings, details

        # 创建无向图（用于连通性分析）
        G = nx.Graph()

        # 添加节点
        for node in nodes:
            G.add_node(node.id)

        # 添加边
        for edge in edges:
            if edge.from_ in G and edge.to in G:
                G.add_edge(edge.from_, edge.to)

        # 计算连通分量
        components = list(nx.connected_components(G))
        details["connected_components"] = len(components)

        if components:
            largest = max(components, key=len)
            details["largest_component_size"] = len(largest)

        # 孤立节点
        isolated = self.find_isolated_nodes(nodes, edges)
        details["isolated_nodes"] = len(isolated)

        # 生成警告
        if len(components) > 1:
            warnings.append(f"图有 {len(components)} 个连通分量，可能不完整")
        if isolated:
            warnings.append(f"有 {len(isolated)} 个孤立节点")

        # 如果只有一个连通分量且没有孤立节点，则认为连通
        is_connected = (len(components) == 1 and len(isolated) == 0)

        return is_connected, warnings, details

    def validate_complete(self, graph: KnowledgeGraph) -> Tuple[bool, List[str], Dict]:
        """
        完整图结构验证

        Args:
            graph: 知识图谱

        Returns:
            (是否通过, 错误/警告信息列表, 验证详情)
        """
        all_errors = []
        all_warnings = []
        details = {}

        # 1. 验证DAG
        dag_valid, dag_errors, nx_graph = self.validate_dag(graph.nodes, graph.edges)
        if not dag_valid:
            all_errors.extend(dag_errors)
        details["dag_valid"] = dag_valid

        # 2. 检查悬空边
        dangling_edges = self.find_dangling_edges(graph.nodes, graph.edges)
        if dangling_edges:
            for edge in dangling_edges:
                all_errors.append(f"悬空边: {edge.id} ({edge.from_} -> {edge.to})")
        details["dangling_edge_count"] = len(dangling_edges)

        # 3. 检查孤立节点
        isolated_nodes = self.find_isolated_nodes(graph.nodes, graph.edges)
        if isolated_nodes:
            for node in isolated_nodes[:5]:  # 只显示前5个
                all_warnings.append(f"孤立节点: {node.id}")
            if len(isolated_nodes) > 5:
                all_warnings.append(f"... 还有 {len(isolated_nodes) - 5} 个孤立节点")
        details["isolated_node_count"] = len(isolated_nodes)

        # 4. 验证canonical path
        path_valid, path_errors = self.validate_canonical_path(graph)
        if not path_valid:
            all_errors.extend(path_errors)
        details["canonical_path_valid"] = path_valid

        # 5. 验证连通性
        connected, connectivity_warnings, connectivity_details = self.validate_graph_connectivity(
            graph.nodes, graph.edges
        )
        all_warnings.extend(connectivity_warnings)
        details.update(connectivity_details)
        details["connected"] = connected

        # Fix 7: 新增语义检查
        # 7.1 topic必须在节点中
        topic_in_nodes = any(n.id == graph.topic for n in graph.nodes)
        if not topic_in_nodes:
            all_errors.append(f"Topic节点 '{graph.topic}' 不存在于图中")
        details["topic_exists"] = topic_in_nodes

        # 7.2 每条边端点必须存在
        node_ids = {n.id for n in graph.nodes}
        for edge in graph.edges:
            if edge.from_ not in node_ids:
                all_errors.append(f"边 {edge.id}: from节点 '{edge.from_}' 不存在")
            if edge.to not in node_ids:
                all_errors.append(f"边 {edge.id}: to节点 '{edge.to}' 不存在")

        # 7.3 target必须可由基础节点到达（derivation DAG）
        try:
            derivation_G = nx.DiGraph()
            for n in graph.nodes:
                derivation_G.add_node(n.id)
            for e in graph.edges:
                if e.type in {et.value for et in DERIVATION_EDGE_TYPES}:
                    if e.from_ in derivation_G and e.to in derivation_G:
                        derivation_G.add_edge(e.from_, e.to)

            primitive_types = {"concept", "definition", "quantity", "math_tool"}
            primitive_nodes = [n.id for n in graph.nodes if n.type.value in primitive_types]
            if primitive_nodes and graph.topic in derivation_G:
                reachable = any(
                    nx.has_path(derivation_G, p, graph.topic)
                    for p in primitive_nodes
                    if p in derivation_G
                )
                if not reachable:
                    all_errors.append(
                        f"Topic '{graph.topic}' 不可从基础节点（{primitive_types}）到达"
                    )
                details["target_reachable_from_primitives"] = reachable
        except Exception:
            details["target_reachable_from_primitives"] = "error"

        # 7.5 不允许孤立节点（application和warning除外）
        if isolated_nodes:
            non_allowed_isolated = [
                n.id for n in isolated_nodes
                if n.type.value not in {"application", "warning"}
            ]
            if non_allowed_isolated:
                all_errors.append(f"非应用/警告类孤立节点: {non_allowed_isolated[:5]}")

        # 总结
        passed = (
            dag_valid and path_valid and topic_in_nodes
            and len(dangling_edges) == 0
            and details.get("target_reachable_from_primitives", True) is not False
        )
        details["passed"] = passed
        details["error_count"] = len(all_errors)
        details["warning_count"] = len(all_warnings)

        return passed, all_errors + all_warnings, details