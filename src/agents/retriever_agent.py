"""
RetrieverAgent

仅从本地seed库与缓存中找候选节点、边、路径。
禁止自由生成新定律。
"""

from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
import networkx as nx

from ..loader import DataLoader
from ..models import Node, Edge


@dataclass
class RetrievalOutput:
    """RetrieverAgent输出"""
    candidate_nodes: List[Node]
    candidate_edges: List[Edge]
    candidate_paths: List[List[str]]
    retrieval_evidence: Dict[str, Any]
    seed_coverage: float
    max_nodes: int = 40


class RetrieverAgent:
    """RetrieverAgent"""

    def __init__(self, loader: Optional[DataLoader] = None):
        """
        初始化

        Args:
            loader: 数据加载器
        """
        self.loader = loader or DataLoader()
        self._load_all_seeds()

    def _load_all_seeds(self):
        """加载所有种子数据"""
        self.all_seeds = self.loader.load_all_seeds()

        # 构建全局图用于路径查找
        self.global_nodes: List[Node] = []
        self.global_edges: List[Edge] = []

        for domain, seed_data in self.all_seeds.items():
            nodes = self.loader.parse_nodes_from_seed(seed_data)
            edges = self.loader.parse_edges_from_seed(seed_data)
            self.global_nodes.extend(nodes)
            self.global_edges.extend(edges)

        # 构建networkx图
        self.G = nx.DiGraph()
        for node in self.global_nodes:
            self.G.add_node(node.id, node=node)
        for edge in self.global_edges:
            if edge.from_ in self.G and edge.to in self.G:
                self.G.add_edge(edge.from_, edge.to, edge=edge)

    def run(self, planner_output: Dict[str, Any]) -> RetrievalOutput:
        """
        运行RetrieverAgent

        Args:
            planner_output: PlannerAgent的输出

        Returns:
            RetrievalOutput对象
        """
        target = planner_output.get("target")
        expand_down = planner_output.get("expand_down", 2)
        expand_up = planner_output.get("expand_up", 1)
        max_nodes = planner_output.get("max_nodes", 40)
        domain = planner_output.get("domain", "mechanics")

        # 1. 查找目标节点
        original_target = target  # 保存原始路由结果
        target_node = self._find_node_by_id(target)
        if not target_node:
            similar_nodes = self._find_similar_nodes(target, domain)
            if similar_nodes:
                target_node = similar_nodes[0]
            else:
                from ..models import Node, NodeType, TheoryContext
                theory_ctx = TheoryContext.CLASSICAL
                domain_str = str(domain).lower() if domain else ""
                target_str = str(target).lower()
                if "relativ" in domain_str or "relativ" in target_str or "general_relativ" in target_str:
                    theory_ctx = TheoryContext.RELATIVISTIC
                elif "quantum" in domain_str or "quantum" in target_str or "schrodinger" in target_str:
                    theory_ctx = TheoryContext.QUANTUM_INTRO
                elif "statistic" in domain_str or "boltzmann" in target_str or "partition" in target_str:
                    theory_ctx = TheoryContext.STATISTICAL
                elif "modern" in domain_str:
                    if "relativ" in target_str:
                        theory_ctx = TheoryContext.RELATIVISTIC
                    elif "quantum" in target_str:
                        theory_ctx = TheoryContext.QUANTUM_INTRO
                target_node = Node(
                    id=target,
                    type=NodeType.EQUATION,
                    title=target.split('.')[-1].replace('_', ' '),
                    statement="待补充",
                    formula_latex="N/A",
                    domain=domain,
                    abstraction_level=5,
                    pedagogical_level=3,
                    theory_context=theory_ctx,
                    sources=["auto_generated"]
                )

        # 2. 收集候选节点（向下展开）
        down_nodes, down_edges = self._collect_downstream(target, expand_down, max_nodes // 2)

        # 3. 收集候选节点（向上展开）
        up_nodes, up_edges = self._collect_upstream(target, expand_up, max_nodes // 2)

        # 4. 合并节点和边（去重）
        all_nodes = self._merge_nodes([target_node] + down_nodes + up_nodes)
        all_edges = self._merge_edges(down_edges + up_edges)

        # 5. 查找候选路径
        candidate_paths = self._find_candidate_paths(target, all_nodes, all_edges)

        # 6. 计算种子覆盖率
        seed_coverage = self._calculate_seed_coverage(all_nodes, domain)

        # 7. 构建检索证据
        retrieval_evidence = {
            "target_found": True,
            "target_node": original_target,
            "domain": domain,
            "downstream_nodes_count": len(down_nodes),
            "upstream_nodes_count": len(up_nodes),
            "total_nodes_retrieved": len(all_nodes),
            "total_edges_retrieved": len(all_edges),
            "candidate_paths_count": len(candidate_paths),
            "seed_coverage": seed_coverage,
            "notes": []
        }

        # 检查是否达到最大节点限制
        if len(all_nodes) > max_nodes:
            retrieval_evidence["notes"].append(
                f"检索到的节点数({len(all_nodes)})超过最大限制({max_nodes})，将进行剪枝"
            )
            # 剪枝：优先保留与目标关系更近的节点
            all_nodes, all_edges = self._prune_graph(
                target, all_nodes, all_edges, max_nodes
            )

        return RetrievalOutput(
            candidate_nodes=all_nodes,
            candidate_edges=all_edges,
            candidate_paths=candidate_paths,
            retrieval_evidence=retrieval_evidence,
            seed_coverage=seed_coverage,
            max_nodes=max_nodes
        )

    def _find_node_by_id(self, node_id: str) -> Optional[Node]:
        """根据ID查找节点"""
        for node in self.global_nodes:
            if node.id == node_id:
                return node
        return None

    def _find_similar_nodes(self, query: str, domain: str) -> List[Node]:
        query_lower = query.lower()
        query_parts = query_lower.replace('.', ' ').replace('_', ' ').split()
        similar = []

        for node in self.global_nodes:
            node_id_lower = node.id.lower()

            if query_lower == node_id_lower:
                similar.append(node)
                continue

            if query_lower in node_id_lower:
                similar.append(node)
                continue

            if node_id_lower in query_lower:
                node_name_parts = node_id_lower.replace('.', ' ').replace('_', ' ').split()
                if len(node_name_parts) >= 2:
                    last_part = node_name_parts[-1]
                    if last_part in query_parts and len(query_parts) > 1:
                        query_without_last = [p for p in query_parts if p != last_part]
                        node_without_last = [p for p in node_name_parts if p != last_part]
                        if not any(q in node_without_last for q in query_without_last):
                            continue
                similar.append(node)
                continue

            if hasattr(node, 'title') and node.title:
                if query_lower in node.title.lower() or node.title.lower() in query_lower:
                    similar.append(node)
                    continue

            if hasattr(node, 'aliases') and node.aliases:
                for alias in node.aliases:
                    if query_lower in alias.lower() or alias.lower() in query_lower:
                        similar.append(node)
                        break

            if query_parts and hasattr(node, 'title') and node.title:
                title_lower = node.title.lower()
                match_count = sum(1 for p in query_parts if p in title_lower or p in node_id_lower)
                if match_count >= max(2, len(query_parts) * 0.5):
                    similar.append(node)

        return similar

    def _collect_downstream(self, target: str, depth: int, max_nodes: int) -> tuple[List[Node], List[Edge]]:
        """收集下游节点（目标依赖的节点）"""
        if depth <= 0 or max_nodes <= 0:
            return [], []

        visited_nodes = set()
        visited_edges = set()

        # BFS遍历下游
        queue = [(target, 0)]
        while queue and len(visited_nodes) < max_nodes:
            current, current_depth = queue.pop(0)

            if current_depth >= depth:
                continue

            # 查找指向当前节点的边（即当前节点依赖的节点）
            for edge in self.global_edges:
                if edge.to == current and edge.from_ not in visited_nodes:
                    from_node = self._find_node_by_id(edge.from_)
                    if from_node:
                        visited_nodes.add(from_node.id)
                        visited_edges.add(edge.id)
                        queue.append((edge.from_, current_depth + 1))

        # 转换为对象
        nodes = [self._find_node_by_id(nid) for nid in visited_nodes]
        nodes = [n for n in nodes if n is not None]

        edges = [e for e in self.global_edges if e.id in visited_edges]

        return nodes, edges

    def _collect_upstream(self, target: str, depth: int, max_nodes: int) -> tuple[List[Node], List[Edge]]:
        """收集上游节点（依赖目标的节点）"""
        if depth <= 0 or max_nodes <= 0:
            return [], []

        visited_nodes = set()
        visited_edges = set()

        # BFS遍历上游
        queue = [(target, 0)]
        while queue and len(visited_nodes) < max_nodes:
            current, current_depth = queue.pop(0)

            if current_depth >= depth:
                continue

            # 查找从当前节点出发的边（即依赖当前节点的节点）
            for edge in self.global_edges:
                if edge.from_ == current and edge.to not in visited_nodes:
                    to_node = self._find_node_by_id(edge.to)
                    if to_node:
                        visited_nodes.add(to_node.id)
                        visited_edges.add(edge.id)
                        queue.append((edge.to, current_depth + 1))

        # 转换为对象
        nodes = [self._find_node_by_id(nid) for nid in visited_nodes]
        nodes = [n for n in nodes if n is not None]

        edges = [e for e in self.global_edges if e.id in visited_edges]

        return nodes, edges

    def _find_candidate_paths(self, target: str, nodes: List[Node], edges: List[Edge]) -> List[List[str]]:
        """查找候选路径"""
        # 构建子图
        G = nx.DiGraph()
        node_ids = {node.id for node in nodes}

        for edge in edges:
            if edge.from_ in node_ids and edge.to in node_ids:
                G.add_edge(edge.from_, edge.to)

        if target not in G:
            return []

        # 查找所有从叶节点到目标节点的路径
        candidate_paths = []

        # 找到所有叶节点（入度为0的节点）
        leaves = [node for node in G.nodes() if G.in_degree(node) == 0]

        for leaf in leaves:
            try:
                # 查找从叶节点到目标的所有简单路径
                paths = list(nx.all_simple_paths(G, leaf, target))
                candidate_paths.extend(paths)
            except nx.NetworkXNoPath:
                continue

        # 限制路径数量
        max_paths = 10
        if len(candidate_paths) > max_paths:
            # 优先选择较短的路径
            candidate_paths.sort(key=len)
            candidate_paths = candidate_paths[:max_paths]

        return candidate_paths

    def _merge_nodes(self, nodes: List[Node]) -> List[Node]:
        """合并节点列表（去重）"""
        seen = set()
        merged = []

        for node in nodes:
            if node.id not in seen:
                seen.add(node.id)
                merged.append(node)

        return merged

    def _merge_edges(self, edges: List[Edge]) -> List[Edge]:
        """合并边列表（去重）"""
        seen = set()
        merged = []

        for edge in edges:
            if edge.id not in seen:
                seen.add(edge.id)
                merged.append(edge)

        return merged

    def _calculate_seed_coverage(self, nodes: List[Node], domain: str) -> float:
        """计算种子覆盖率"""
        # 计算该学科域的总节点数
        domain_nodes = [n for n in self.global_nodes
                       if hasattr(n, 'domain') and n.domain == domain]

        if not domain_nodes:
            return 0.0

        # 计算检索到的节点中属于该学科域的比例
        retrieved_domain_nodes = [n for n in nodes
                                 if hasattr(n, 'domain') and n.domain == domain]

        return len(retrieved_domain_nodes) / len(domain_nodes)

    def _prune_graph(self, target: str, nodes: List[Node], edges: List[Edge],
                    max_nodes: int) -> tuple[List[Node], List[Edge]]:
        """剪枝图"""
        if len(nodes) <= max_nodes:
            return nodes, edges

        # 构建图并计算节点重要性（基于到目标的距离）
        G = nx.DiGraph()
        for edge in edges:
            G.add_edge(edge.from_, edge.to)

        # 计算每个节点到目标的最短路径长度
        importance = {}
        for node in nodes:
            try:
                path_length = nx.shortest_path_length(G, node.id, target)
                importance[node.id] = 1.0 / (path_length + 1)  # 距离越近，重要性越高
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                importance[node.id] = 0.0

        # 按重要性排序节点
        sorted_nodes = sorted(nodes, key=lambda n: importance.get(n.id, 0.0), reverse=True)

        # 选择前max_nodes个节点
        selected_nodes = sorted_nodes[:max_nodes]
        selected_node_ids = {n.id for n in selected_nodes}

        # 选择连接这些节点的边
        selected_edges = [e for e in edges
                         if e.from_ in selected_node_ids and e.to in selected_node_ids]

        return selected_nodes, selected_edges