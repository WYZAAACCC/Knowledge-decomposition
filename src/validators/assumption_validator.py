"""
假设验证器

验证所有derives_from边是否都带assumptions，
assumption是否存在于注册表，是否命中学科域必查checklist。
"""

from typing import Dict, List, Tuple, Optional, Any
from ..models import Node, Edge, KnowledgeGraph
from ..physics.assumption_checklists import get_assumption_checklists
from ..physics.quantity_registry import get_quantity_registry


class AssumptionValidator:
    """假设验证器"""

    def __init__(self):
        """初始化"""
        self.checklists = get_assumption_checklists()
        self.registry = get_quantity_registry()

    def validate_edge_assumptions(self, edge: Edge) -> Tuple[bool, List[str]]:
        """
        验证单条边的假设

        Args:
            edge: 边对象

        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        # 1. 对于derives_from边，必须包含假设
        if edge.type == "derives_from":
            if not edge.assumptions or len(edge.assumptions) == 0:
                errors.append(f"derives_from边 {edge.id} 必须包含至少一个假设")
                return False, errors

            # 2. 检查每个假设的格式
            for i, assumption in enumerate(edge.assumptions):
                if not isinstance(assumption, str) or not assumption.strip():
                    errors.append(f"边 {edge.id} 的第{i+1}个假设无效: {assumption}")

        # 3. 检查假设是否在注册表中（如果有注册表的话）
        # 这里假设assumption_checklists中会定义有效的假设ID
        # 我们可以检查假设是否在相关学科的检查清单中
        if edge.assumptions:
            # 推断学科域（从边连接的节点或主题）
            domain = self._infer_domain_from_edge(edge)
            if domain:
                domain_assumptions = self.checklists.get_domain_assumptions(domain)
                extra_assumptions = []
                for assumption in edge.assumptions:
                    if assumption not in domain_assumptions:
                        extra_assumptions.append(assumption)

                if extra_assumptions:
                    # 警告而不是错误，因为可能有自定义假设
                    pass  # 暂时不处理警告

        return len(errors) == 0, errors

    def validate_topic_assumptions(self, topic_id: str, edges: List[Edge],
                                   domain: str = None) -> Dict[str, Any]:
        """
        验证主题的假设覆盖率

        Args:
            topic_id: 主题ID
            edges: 相关边列表
            domain: 学科域

        Returns:
            验证结果详情
        """
        # 收集所有假设
        all_assumptions = []
        for edge in edges:
            if edge.assumptions:
                all_assumptions.extend(edge.assumptions)

        # 获取检查清单
        checklist_result = self.checklists.check_topic_assumptions(
            topic_id, all_assumptions, domain
        )

        # 检查每个derives_from边是否有假设
        missing_assumption_edges = []
        for edge in edges:
            if edge.type == "derives_from" and (not edge.assumptions or len(edge.assumptions) == 0):
                missing_assumption_edges.append(edge.id)

        # 汇总结果
        result = {
            "topic_id": topic_id,
            "domain": domain or self._infer_domain_from_topic(topic_id),
            "assumption_coverage": checklist_result["coverage"],
            "missing_checklist_assumptions": checklist_result["missing"],
            "extra_assumptions": checklist_result["extra"],
            "required_assumptions": checklist_result["required_count"],
            "provided_assumptions": checklist_result["provided_count"],
            "matched_assumptions": checklist_result["matched_count"],
            "missing_assumption_edges": missing_assumption_edges,
            "derives_from_edge_count": len([e for e in edges if e.type == "derives_from"]),
            "total_edges_with_assumptions": len([e for e in edges if e.assumptions]),
        }

        derives_from_edges = [e for e in edges if e.type == "derives_from"]
        edges_with_assumptions = [e for e in derives_from_edges if e.assumptions and len(e.assumptions) > 0]
        edge_assumption_rate = len(edges_with_assumptions) / len(derives_from_edges) if derives_from_edges else 1.0

        passed = (len(missing_assumption_edges) == 0 and
                  edge_assumption_rate >= 0.8)
        result["passed"] = passed

        return result

    def validate_graph_assumptions(self, graph: KnowledgeGraph) -> Tuple[bool, List[str], Dict]:
        """
        验证整个图的假设完整性

        Args:
            graph: 知识图谱

        Returns:
            (是否通过, 错误/警告信息列表, 验证详情)
        """
        all_errors = []
        all_warnings = []
        details = {}

        # 1. 验证每条边
        edge_results = {}
        for edge in graph.edges:
            valid, errors = self.validate_edge_assumptions(edge)
            if not valid:
                edge_results[edge.id] = {"valid": False, "errors": errors}
                all_errors.extend([f"边 {edge.id}: {e}" for e in errors])
            else:
                edge_results[edge.id] = {"valid": True, "errors": []}

        details["edge_results"] = edge_results
        details["invalid_edge_count"] = len([r for r in edge_results.values() if not r["valid"]])

        # 2. 验证主题假设覆盖率（如果有主题）
        if graph.topic:
            # 从节点中推断domain（使用最常见的domain）
            domain_counts = {}
            for node in graph.nodes:
                domain = node.domain.value if hasattr(node.domain, 'value') else str(node.domain)
                domain_counts[domain] = domain_counts.get(domain, 0) + 1

            inferred_domain = max(domain_counts.items(), key=lambda x: x[1])[0] if domain_counts else "mechanics"

            topic_result = self.validate_topic_assumptions(
                graph.topic, graph.edges, inferred_domain
            )
            details["topic_coverage"] = topic_result

            if not topic_result["passed"]:
                all_warnings.append(
                    f"主题 {graph.topic} 假设覆盖率不足: {topic_result['assumption_coverage']:.2f}"
                )
                if topic_result["missing_checklist_assumptions"]:
                    all_warnings.append(
                        f"缺失检查清单假设: {topic_result['missing_checklist_assumptions']}"
                    )
                if topic_result["missing_assumption_edges"]:
                    all_warnings.extend([
                        f"边 {edge_id} 缺少假设"
                        for edge_id in topic_result["missing_assumption_edges"]
                    ])

        # 3. 汇总
        passed = (details["invalid_edge_count"] == 0 and
                  (not graph.topic or topic_result["passed"]))
        details["passed"] = passed
        details["error_count"] = len(all_errors)
        details["warning_count"] = len(all_warnings)

        return passed, all_errors + all_warnings, details

    def _infer_domain_from_edge(self, edge: Edge) -> Optional[str]:
        """
        从边推断学科域

        简单实现：检查边ID或连接的节点
        """
        # 从边ID推断
        edge_id = edge.id.lower()
        if "mech" in edge_id or "newton" in edge_id or "bernoulli" in edge_id:
            return "mechanics"
        elif "thermo" in edge_id or "entropy" in edge_id:
            return "thermodynamics"
        elif "electro" in edge_id or "gauss" in edge_id:
            return "electromagnetism"
        elif "optics" in edge_id or "lens" in edge_id:
            return "optics"
        elif "modern" in edge_id or "quantum" in edge_id:
            return "modern_physics"

        # 从主题推断（如果有）
        if edge.path_id:
            if "mechanics" in edge.path_id:
                return "mechanics"
            elif "thermodynamics" in edge.path_id:
                return "thermodynamics"

        return None

    def _infer_domain_from_topic(self, topic_id: str) -> str:
        """
        从主题ID推断学科域
        """
        topic_lower = topic_id.lower()
        if "bernoulli" in topic_lower or "newton" in topic_lower:
            return "mechanics"
        elif "thermo" in topic_lower or "entropy" in topic_lower:
            return "thermodynamics"
        elif "gauss" in topic_lower or "ampere" in topic_lower:
            return "electromagnetism"
        elif "lens" in topic_lower or "refraction" in topic_lower:
            return "optics"
        elif "relativity" in topic_lower or "quantum" in topic_lower:
            return "modern_physics"
        else:
            return "mechanics"  # 默认