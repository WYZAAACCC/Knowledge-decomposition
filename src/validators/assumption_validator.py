"""
假设验证器

Fix 6: 从"非空检查"升级为"注册表检查"。
"""
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set
from ..models import Node, Edge, KnowledgeGraph
from ..physics.assumption_checklists import get_assumption_checklists


class AssumptionValidator:
    """Fix 6: 假设验证器 — 检查注册表"""

    def __init__(self):
        self.checklists = get_assumption_checklists()
        self._registry: Optional[Dict[str, dict]] = None
        self._registry_ids: Optional[Set[str]] = None

    @property
    def registry(self) -> Dict[str, dict]:
        """Fix 6: 加载 assumption registry"""
        if self._registry is None:
            self._registry = {}
            self._registry_ids = set()
            registry_path = Path(__file__).parent.parent.parent / "data" / "ontology" / "assumptions.json"
            try:
                if registry_path.exists():
                    with open(registry_path, encoding='utf-8') as f:
                        data = json.load(f)
                    for item in data:
                        aid = item.get("id", "")
                        if aid:
                            self._registry[aid] = item
                            self._registry_ids.add(aid)
            except Exception:
                pass
        return self._registry

    @property
    def registry_ids(self) -> Set[str]:
        if self._registry_ids is None:
            _ = self.registry  # trigger load
        return self._registry_ids or set()

    def validate_edge_assumptions(self, edge: Edge) -> Tuple[bool, List[str]]:
        """Fix 6: 验证边假设（检查注册表）"""
        errors = []

        # 检查 derives/derives_from 边必须有假设
        if edge.type.value in {"derives", "derives_from"}:
            has_free_text = edge.assumptions and len(edge.assumptions) > 0
            has_registry = getattr(edge, 'assumption_ids', None) and len(edge.assumption_ids) > 0
            if not has_free_text and not has_registry:
                errors.append(f"{edge.type.value}边 {edge.id} 必须包含assumptions或assumption_ids")
                return False, errors

        # Fix 6: 检查 assumption_ids 是否在注册表中
        assumption_ids = getattr(edge, 'assumption_ids', []) or []
        for aid in assumption_ids:
            if aid not in self.registry_ids:
                errors.append(f"边 {edge.id}: assumption_id '{aid}' 不在注册表中")
            else:
                entry = self.registry.get(aid, {})
                # 检查 domain 兼容性
                applies_to = entry.get("applies_to_edge_types", [])
                if edge.type.value not in applies_to:
                    errors.append(
                        f"边 {edge.id}: assumption '{aid}' "
                        f"不适用于 {edge.type.value} 类型边"
                        f"（适用于: {applies_to}）"
                    )

        # 检查自由文本假设（应逐步淘汰，用assumption_ids替代）
        if edge.assumptions:
            for i, assumption in enumerate(edge.assumptions):
                if not isinstance(assumption, str) or not assumption.strip():
                    errors.append(f"边 {edge.id} 的第{i+1}个假设无效: {assumption}")
                # 检查domain相关的checklist
                domain = self._infer_domain_from_edge(edge)

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