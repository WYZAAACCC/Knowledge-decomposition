"""
VerifierAgent

串行调用所有本地验证器。
"""

from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

from ..validators.schema_validator import SchemaValidator
from ..validators.graph_validator import GraphValidator
from ..validators.assumption_validator import AssumptionValidator
from ..validators.dimension_validator import DimensionValidator
from ..validators.duplicate_validator import DuplicateValidator
from ..models import KnowledgeGraph


@dataclass
class VerificationOutput:
    """VerifierAgent输出"""
    passed: bool
    validation_results: Dict[str, Dict[str, Any]]
    overall_score: float
    critical_errors: List[str]
    warnings: List[str]
    suggested_actions: List[str]


class VerifierAgent:
    """VerifierAgent"""

    def __init__(self):
        """初始化"""
        self.schema_validator = SchemaValidator()
        self.graph_validator = GraphValidator()
        self.assumption_validator = AssumptionValidator()
        self.dimension_validator = DimensionValidator()
        self.duplicate_validator = DuplicateValidator()

    def run(self, decomposer_output: Dict[str, Any]) -> VerificationOutput:
        """
        运行VerifierAgent

        Args:
            decomposer_output: DecomposerAgent的输出

        Returns:
            VerificationOutput对象
        """
        subgraph = decomposer_output.get("subgraph")

        if not isinstance(subgraph, KnowledgeGraph):
            # 尝试转换
            try:
                subgraph = KnowledgeGraph(**subgraph)
            except Exception as e:
                return VerificationOutput(
                    passed=False,
                    validation_results={"error": {"message": f"无效的图谱数据: {e}"}},
                    overall_score=0.0,
                    critical_errors=[f"图谱数据无效: {e}"],
                    warnings=[],
                    suggested_actions=["检查DecomposerAgent输出格式"]
                )

        # 执行所有验证
        validation_results = {}

        # 1. Schema验证
        try:
            schema_passed, schema_errors, schema_details = self.schema_validator.validate_graph(subgraph)
            validation_results["schema"] = {
                "passed": schema_passed,
                "errors": schema_errors,
                "details": schema_details,
                "score": 1.0 if schema_passed else 0.0
            }
        except Exception as e:
            validation_results["schema"] = {
                "passed": False,
                "errors": [f"Schema验证异常: {e}"],
                "details": {"exception": str(e)},
                "score": 0.0
            }

        # 2. 图结构验证
        try:
            graph_passed, graph_errors, graph_details = self.graph_validator.validate_complete(subgraph)
            graph_score = 0.0
            if graph_details.get("dag_valid"):
                graph_score += 0.4
            if graph_details.get("dangling_edge_count", 1) == 0:
                graph_score += 0.3
            if graph_details.get("canonical_path_valid"):
                graph_score += 0.2
            if graph_details.get("isolated_node_count", 999) == 0:
                graph_score += 0.1
            validation_results["graph_structure"] = {
                "passed": graph_passed,
                "errors": graph_errors,
                "details": graph_details,
                "score": graph_score
            }
        except Exception as e:
            validation_results["graph_structure"] = {
                "passed": False,
                "errors": [f"图结构验证异常: {e}"],
                "details": {"exception": str(e)},
                "score": 0.0
            }

        # 3. 假设验证
        try:
            assumption_passed, assumption_errors, assumption_details = self.assumption_validator.validate_graph_assumptions(subgraph)
            derives_from_count = len([e for e in subgraph.edges if e.type == "derives_from"])
            edges_with_assumptions = len([e for e in subgraph.edges if e.type == "derives_from" and e.assumptions])
            assumption_rate = edges_with_assumptions / derives_from_count if derives_from_count > 0 else 1.0
            validation_results["assumptions"] = {
                "passed": assumption_passed,
                "errors": assumption_errors,
                "details": assumption_details,
                "score": assumption_rate
            }
        except Exception as e:
            validation_results["assumptions"] = {
                "passed": False,
                "errors": [f"假设验证异常: {e}"],
                "details": {"exception": str(e)},
                "score": 0.0
            }

        # 4. 量纲验证
        try:
            dimension_passed, dimension_errors, dimension_details = self.dimension_validator.validate_graph_dimensions(subgraph)
            validation_results["dimensions"] = {
                "passed": dimension_passed,
                "errors": dimension_errors,
                "details": dimension_details,
                "score": 1.0 if dimension_passed else 0.0
            }
        except Exception as e:
            validation_results["dimensions"] = {
                "passed": False,
                "errors": [f"量纲验证异常: {e}"],
                "details": {"exception": str(e)},
                "score": 0.0
            }

        # 5. 重复验证
        try:
            duplicate_passed, duplicate_warnings, duplicate_details = self.duplicate_validator.validate_graph_uniqueness(subgraph)
            validation_results["duplicates"] = {
                "passed": duplicate_passed,
                "warnings": duplicate_warnings,
                "details": duplicate_details,
                "score": 1.0 if duplicate_passed else 0.8  # 重复通常不是致命错误
            }
        except Exception as e:
            validation_results["duplicates"] = {
                "passed": False,
                "warnings": [f"重复验证异常: {e}"],
                "details": {"exception": str(e)},
                "score": 0.0
            }

        # 汇总结果
        all_errors = []
        all_warnings = []
        suggested_actions = []

        for validator_name, result in validation_results.items():
            all_errors.extend(result.get("errors", []))
            all_warnings.extend(result.get("warnings", []))

            if not result.get("passed", True):
                # 生成修复建议
                if validator_name == "schema":
                    suggested_actions.append("修复JSON schema不一致")
                elif validator_name == "graph_structure":
                    suggested_actions.append("修复图结构问题（环、悬空边等）")
                elif validator_name == "assumptions":
                    suggested_actions.append("补充缺失的假设")
                elif validator_name == "dimensions":
                    suggested_actions.append("修复量纲不一致")
                elif validator_name == "duplicates":
                    suggested_actions.append("合并重复节点")

        # 计算总体分数
        weights = {
            "schema": 0.30,
            "graph_structure": 0.30,
            "assumptions": 0.20,
            "dimensions": 0.10,
            "duplicates": 0.10
        }

        overall_score = 0.0
        for validator_name, result in validation_results.items():
            weight = weights.get(validator_name, 0.0)
            score = result.get("score", 0.0)
            overall_score += weight * score

        critical_passed = (
            validation_results["schema"]["passed"] and
            validation_results["graph_structure"]["passed"]
        )

        critical_errors = []
        if not validation_results["schema"]["passed"]:
            critical_errors.append("Schema验证失败")
        if not validation_results["graph_structure"]["passed"]:
            critical_errors.append("图结构验证失败")

        passed = critical_passed and overall_score >= 0.5

        return VerificationOutput(
            passed=passed,
            validation_results=validation_results,
            overall_score=overall_score,
            critical_errors=critical_errors,
            warnings=all_warnings,
            suggested_actions=suggested_actions
        )

    def validate_single_topic(self, topic: str, graph: KnowledgeGraph) -> Dict[str, Any]:
        """
        验证单个主题（用于benchmark测试）

        Args:
            topic: 主题
            graph: 知识图谱

        Returns:
            验证结果
        """
        # 执行假设验证（针对特定主题）
        assumption_result = self.assumption_validator.validate_topic_assumptions(
            topic, graph.edges, graph.domain
        )

        # 执行量纲验证（针对canonical path）
        dimension_result = self.dimension_validator.validate_canonical_path_dimensions(graph)

        return {
            "assumption_coverage": assumption_result.get("assumption_coverage", 0.0),
            "dimension_passed": dimension_result[0],
            "dimension_details": dimension_result[2]
        }