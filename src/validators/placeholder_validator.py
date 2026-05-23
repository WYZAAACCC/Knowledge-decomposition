"""
Fix 5: 占位内容验证器

检测并拒绝任何包含占位文本的节点、边、假设、推导步骤。
"""
import json
import re
from typing import Any, Dict, List

PLACEHOLDER_PATTERNS = [
    r"待补充",
    r"TODO",
    r"TBD",
    r"N/?A",
    r"unknown",
    r"未定义",
    r"暂无",
    r"placeholder",
    r"假设条件待补充",
    r"推导步骤待补充",
    r"证明步骤待补充",
]


def contains_placeholder(value: Any) -> bool:
    """递归检查值是否包含占位文本"""
    if isinstance(value, str):
        return any(re.search(p, value, re.IGNORECASE) for p in PLACEHOLDER_PATTERNS)
    if isinstance(value, dict):
        return any(contains_placeholder(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(contains_placeholder(v) for v in value)
    return False


def check_node_for_placeholders(node) -> List[str]:
    """检查节点是否包含占位内容"""
    errors = []
    fields_to_check = [
        ("title", node.title if hasattr(node, "title") else ""),
        ("statement", node.statement if hasattr(node, "statement") else ""),
        ("formula_latex", node.formula_latex if hasattr(node, "formula_latex") else ""),
    ]
    if hasattr(node, "assumptions"):
        for i, a in enumerate(getattr(node, "assumptions", [])):
            fields_to_check.append((f"assumptions[{i}]", a))
    if hasattr(node, "derivation_steps"):
        for i, s in enumerate(getattr(node, "derivation_steps", [])):
            fields_to_check.append((f"derivation_steps[{i}]", s))

    for field_name, value in fields_to_check:
        if value and contains_placeholder(value):
            errors.append(f"节点 {getattr(node, 'id', '?')} 的 {field_name} 包含占位文本")
    return errors


def check_edge_for_placeholders(edge) -> List[str]:
    """检查边是否包含占位内容"""
    errors = []
    if hasattr(edge, "assumptions"):
        for i, a in enumerate(edge.assumptions or []):
            if contains_placeholder(a):
                errors.append(f"边 {getattr(edge, 'id', '?')} 的 assumptions[{i}] 包含占位文本")
    if hasattr(edge, "assumption_ids"):
        for i, a in enumerate(edge.assumption_ids or []):
            if contains_placeholder(a):
                errors.append(f"边 {getattr(edge, 'id', '?')} 的 assumption_ids[{i}] 包含占位文本")
    if hasattr(edge, "derivation_steps"):
        for i, s in enumerate(edge.derivation_steps or []):
            if contains_placeholder(s):
                errors.append(f"边 {getattr(edge, 'id', '?')} 的 derivation_steps[{i}] 包含占位文本")
    if hasattr(edge, "proof_step_ids"):
        for i, s in enumerate(edge.proof_step_ids or []):
            if contains_placeholder(s):
                errors.append(f"边 {getattr(edge, 'id', '?')} 的 proof_step_ids[{i}] 包含占位文本")
    return errors


class PlaceholderValidator:
    """Fix 5: 占位内容验证器"""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate(self, graph) -> Dict[str, Any]:
        """验证图谱中无占位内容"""
        self.errors = []
        self.warnings = []

        if not graph:
            return {
                "passed": True,
                "errors": [],
                "warnings": [],
                "details": ["空图谱，无需检查"],
            }

        nodes = getattr(graph, "nodes", [])
        edges = getattr(graph, "edges", [])

        for node in nodes:
            node_errors = check_node_for_placeholders(node)
            self.errors.extend(node_errors)

        for edge in edges:
            edge_errors = check_edge_for_placeholders(edge)
            self.errors.extend(edge_errors)

        # 检查 proof_steps
        if hasattr(graph, "proof_steps"):
            for ps in graph.proof_steps or []:
                if hasattr(ps, "explanation_zh") and contains_placeholder(ps.explanation_zh):
                    self.errors.append(f"ProofStep {getattr(ps, 'id', '?')} 的 explanation_zh 包含占位文本")
                if hasattr(ps, "input_expressions"):
                    for i, expr in enumerate(ps.input_expressions or []):
                        if contains_placeholder(expr):
                            self.errors.append(f"ProofStep {getattr(ps, 'id', '?')} 的 input_expressions[{i}] 包含占位文本")

        passed = len(self.errors) == 0
        return {
            "passed": passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "details": [
                f"检查了 {len(nodes)} 个节点, {len(edges)} 条边",
                f"发现 {len(self.errors)} 个占位内容错误",
            ],
        }
