"""
Improvement 9: 评分体系升级

分层评分，阻止"总分超过0.5就放行"。
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class QualityReport:
    """多维质量报告"""
    # 结构性评分
    structural_score: float = 0.0       # Schema + DAG + connectivity
    # 语义评分
    semantic_score: float = 0.0         # Topic match + derivation validity
    # 假设评分
    assumption_score: float = 0.0       # Assumption coverage + registry match
    # 量纲评分
    dimension_score: float = 0.0        # Dimension consistency
    # 溯源评分
    provenance_score: float = 0.0       # Source trust + no LLM in verified
    # 渲染评分
    rendering_score: float = 0.0        # Artifact completeness
    # 确定性评分
    deterministic_score: float = 0.0    # Reproducibility

    # 总评
    overall_score: float = 0.0

    # 阻塞性错误
    blocking_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def is_passed(self) -> bool:
        """Improvement 9: 严格通过规则"""
        return (
            not self.blocking_errors
            and self.structural_score >= 0.95
            and self.semantic_score >= 0.80
            and self.assumption_score >= 0.90
            and self.provenance_score >= 0.90
        )

    def compute_overall(self):
        """计算加权总评"""
        weights = {
            "structural": 0.20,
            "semantic": 0.20,
            "assumption": 0.20,
            "dimension": 0.15,
            "provenance": 0.10,
            "rendering": 0.10,
            "deterministic": 0.05,
        }
        self.overall_score = (
            self.structural_score * weights["structural"]
            + self.semantic_score * weights["semantic"]
            + self.assumption_score * weights["assumption"]
            + self.dimension_score * weights["dimension"]
            + self.provenance_score * weights["provenance"]
            + self.rendering_score * weights["rendering"]
            + self.deterministic_score * weights["deterministic"]
        )


class QualityEvaluator:
    """计算各维度质量分数"""

    @staticmethod
    def evaluate(graph, verification_output) -> QualityReport:
        report = QualityReport()

        if not graph or not graph.nodes:
            report.blocking_errors.append("空图谱")
            return report

        # 结构性: 基于 Schema + DAG
        vs = verification_output.validation_results if verification_output else {}
        schema_ok = vs.get("schema", {}).get("passed", False)
        graph_ok = vs.get("graph_structure", {}).get("passed", False)
        dag_ok = vs.get("graph_structure", {}).get("details", {}).get("dag_valid", False)

        report.structural_score = (
            0.40 if schema_ok else 0.0
            + 0.30 if dag_ok else 0.0
            + 0.20 if graph_ok else 0.0
            + 0.10  # baseline
        )

        # 语义: Topic可达 + 推导有效
        details = vs.get("graph_structure", {}).get("details", {})
        target_reachable = details.get("target_reachable_from_primitives", None)
        topic_exists = details.get("topic_exists", False)
        report.semantic_score = (
            0.50 if topic_exists else 0.0
            + 0.30 if target_reachable is True else 0.0
            + 0.20  # baseline
        )

        # 假设: 覆盖率
        assumption_data = vs.get("assumptions", {})
        report.assumption_score = assumption_data.get("score", 0.5)

        # 量纲
        dimension_data = vs.get("dimensions", {})
        report.dimension_score = dimension_data.get("score", 0.5)

        # 溯源: 无LLM污染
        llm_nodes = sum(
            1 for n in graph.nodes
            if getattr(n, 'trust_level', None)
            and getattr(n, 'trust_level', None).value in {'llm_proposal', 'auto_generated', 'unknown'}
        ) if graph.nodes else 0
        total_nodes = len(graph.nodes) if graph.nodes else 1
        report.provenance_score = 1.0 - (llm_nodes / total_nodes)

        # 渲染: graph_json 存在
        report.rendering_score = 0.8  # baseline

        # 确定性
        report.deterministic_score = 0.7  # baseline (需要多次构建比较)

        if verification_output:
            report.warnings = verification_output.warnings or []
            if verification_output.critical_errors:
                report.blocking_errors.extend(verification_output.critical_errors)

        report.compute_overall()
        return report
