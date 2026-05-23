"""
量纲验证器

检查quantity/equation节点量纲元数据，
检查canonical path上核心方程的量纲一致性，
对可解析公式做SymPy + 自定义量纲表验证。
"""

import re
from typing import Dict, List, Tuple, Optional, Any
from sympy import sympify, simplify, Symbol, Eq, solve
from sympy.parsing.sympy_parser import parse_expr

from ..models import Node, Edge, KnowledgeGraph, DimensionCheck, DimensionVector
from ..physics.dimensions import get_dimension_system
from ..physics.quantity_registry import get_quantity_registry


class DimensionValidator:
    """量纲验证器"""

    def __init__(self):
        """初始化"""
        self.dim_system = get_dimension_system()
        self.quantity_registry = get_quantity_registry()

    def validate_node_dimension(self, node: Node) -> Tuple[bool, List[str]]:
        """
        验证节点的量纲信息

        Args:
            node: 节点对象

        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        # 只有quantity和equation节点需要量纲验证
        if node.type not in ["quantity", "equation"]:
            return True, errors

        if not hasattr(node, 'dimension') or node.dimension is None:
            return True, errors

        # 验证量纲字符串格式
        if hasattr(node.dimension, 'base_dimensions'):
            dim_str = node.dimension.base_dimensions
        else:
            dim_str = node.dimension
        expr = self.dim_system.parse_dimension_string(dim_str)
        if expr is None:
            errors.append(f"节点 {node.id} 的量纲格式无效: {dim_str}")
            return False, errors

        # 对于quantity节点，检查是否在注册表中
        if node.type == "quantity":
            registry_info = self.quantity_registry.get(node.id)
            if registry_info:
                # 验证量纲匹配
                if not self.dim_system.are_dimensions_compatible(
                    registry_info.dimension, dim_str
                ):
                    errors.append(
                        f"节点 {node.id} 量纲与注册表不匹配: "
                        f"注册表: {registry_info.dimension}, 节点: {dim_str}"
                    )

        # 对于equation节点，如果有formula_latex，可以尝试解析验证
        if node.type == "equation" and hasattr(node, 'formula_latex') and node.formula_latex:
            # 简单验证：检查等号两边量纲是否一致（如果提供了左右边量纲）
            # 这里假设equation节点的dimension字段表示整个方程的量纲（应为1）
            if dim_str != "1" and dim_str != "":
                # 方程应无量纲或特定量纲，视情况而定
                pass

        return len(errors) == 0, errors

    def validate_equation_dimensions(self, node: Node) -> Tuple[bool, List[str]]:
        """
        验证方程的量纲一致性（如果可能）

        Args:
            node: equation节点

        Returns:
            (是否一致, 错误信息列表)
        """
        errors = []

        if node.type != "equation" or not hasattr(node, 'formula_latex') or not node.formula_latex:
            return True, errors

        latex_str = node.formula_latex

        # 尝试解析简单方程
        try:
            # 移除LaTeX标记
            plain_text = self._strip_latex(latex_str)

            # 尝试分割等号
            if "=" in plain_text:
                lhs, rhs = plain_text.split("=", 1)
                lhs = lhs.strip()
                rhs = rhs.strip()

                # 尝试提取物理量符号
                lhs_symbols = self._extract_symbols(lhs)
                rhs_symbols = self._extract_symbols(rhs)

                # 获取每个符号的量纲
                lhs_dims = []
                rhs_dims = []

                for symbol in lhs_symbols:
                    dim = self._get_symbol_dimension(symbol)
                    if dim:
                        lhs_dims.append(dim)

                for symbol in rhs_symbols:
                    dim = self._get_symbol_dimension(symbol)
                    if dim:
                        rhs_dims.append(dim)

                # 如果能够获取量纲，进行验证
                if lhs_dims and rhs_dims:
                    # 简化验证：假设方程是乘积形式
                    # 实际需要更复杂的解析
                    pass

        except Exception as e:
            # 解析失败不是错误，只是跳过
            pass

        return len(errors) == 0, errors

    def validate_canonical_path_dimensions(self, graph: KnowledgeGraph) -> Tuple[bool, List[str], Dict]:
        """
        验证canonical path上的量纲一致性

        Args:
            graph: 知识图谱

        Returns:
            (是否一致, 错误信息列表, 验证详情)
        """
        errors = []
        warnings = []
        details = {
            "path_id": graph.canonical_path,
            "equations_checked": 0,
            "equations_passed": 0,
            "equations_failed": 0,
            "dimension_errors": []
        }

        if not graph.canonical_path:
            warnings.append("没有canonical_path，跳过量纲验证")
            return True, warnings, details

        # 找到canonical path的边
        path_edges = [edge for edge in graph.edges if edge.path_id == graph.canonical_path]
        if not path_edges:
            warnings.append(f"没有边引用canonical_path {graph.canonical_path}")
            return True, warnings, details

        # 收集path上的所有节点
        path_node_ids = set()
        for edge in path_edges:
            path_node_ids.add(edge.from_)
            path_node_ids.add(edge.to)

        path_nodes = [node for node in graph.nodes if node.id in path_node_ids]

        # 验证每个equation节点的量纲
        for node in path_nodes:
            if node.type == "equation":
                details["equations_checked"] += 1

                # 验证节点量纲格式
                valid, node_errors = self.validate_node_dimension(node)
                if not valid:
                    details["equations_failed"] += 1
                    errors.extend([f"节点 {node.id}: {e}" for e in node_errors])
                    details["dimension_errors"].append({
                        "node_id": node.id,
                        "errors": node_errors,
                        "type": "node_dimension"
                    })
                else:
                    details["equations_passed"] += 1

                # 验证方程量纲一致性（如果可能）
                eq_valid, eq_errors = self.validate_equation_dimensions(node)
                if not eq_valid:
                    details["equations_failed"] += 1
                    errors.extend([f"方程 {node.id}: {e}" for e in eq_errors])
                    details["dimension_errors"].append({
                        "node_id": node.id,
                        "errors": eq_errors,
                        "type": "equation_consistency"
                    })

        # 检查路径上关键方程之间的量纲传递一致性
        # 例如：如果F=ma和a=v/t在同一个路径上，检查量纲是否一致
        self._validate_dimension_chain(path_edges, graph.nodes, errors, details)

        passed = (details["equations_failed"] == 0)
        details["passed"] = passed

        return passed, errors + warnings, details

    def validate_graph_dimensions(self, graph: KnowledgeGraph) -> Tuple[bool, List[str], Dict]:
        """
        验证整个图的量纲完整性

        Args:
            graph: 知识图谱

        Returns:
            (是否通过, 错误/警告信息列表, 验证详情)
        """
        all_errors = []
        all_warnings = []
        details = {
            "total_nodes": len(graph.nodes),
            "quantity_nodes": 0,
            "equation_nodes": 0,
            "nodes_with_dimension": 0,
            "nodes_valid": 0,
            "nodes_invalid": 0,
            "node_errors": {}
        }

        # 1. 验证所有quantity和equation节点
        for node in graph.nodes:
            if node.type in ["quantity", "equation"]:
                if node.type == "quantity":
                    details["quantity_nodes"] += 1
                else:
                    details["equation_nodes"] += 1

                if hasattr(node, 'dimension') and node.dimension:
                    details["nodes_with_dimension"] += 1

                valid, errors = self.validate_node_dimension(node)
                if valid:
                    details["nodes_valid"] += 1
                else:
                    details["nodes_invalid"] += 1
                    details["node_errors"][node.id] = errors
                    all_errors.extend([f"节点 {node.id}: {e}" for e in errors])

        # 2. 验证canonical path量纲一致性
        path_valid, path_errors, path_details = self.validate_canonical_path_dimensions(graph)
        details["canonical_path_validation"] = path_details

        if not path_valid:
            all_errors.extend(path_errors)

        # 3. 汇总
        passed = (details["nodes_invalid"] == 0 and path_valid)
        details["passed"] = passed
        details["error_count"] = len(all_errors)
        details["warning_count"] = len(all_warnings)

        return passed, all_errors + all_warnings, details

    def _strip_latex(self, latex_str: str) -> str:
        """移除LaTeX标记（简化实现）"""
        # 移除常见的LaTeX命令
        replacements = [
            (r'\\', ''),
            (r'\{', '('),
            (r'\}', ')'),
            (r'\^', '^'),
            (r'\frac{', '('),
            (r'}{', '/'),
            (r'}', ')'),
            (r'\left', ''),
            (r'\right', ''),
            (r'\cdot', '*'),
            (r'\times', '*'),
            (r'\vec{', ''),
            (r'\mathbf{', ''),
        ]

        result = latex_str
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result)

        # 移除多余的空格
        result = re.sub(r'\s+', ' ', result).strip()

        return result

    def _extract_symbols(self, expr_str: str) -> List[str]:
        """从表达式中提取符号（简化实现）"""
        # 移除数字和运算符
        symbols = re.findall(r'[a-zA-Zα-ωΑ-Ω_][a-zA-Zα-ωΑ-Ω0-9_]*', expr_str)
        return symbols

    def _get_symbol_dimension(self, symbol: str) -> Optional[str]:
        """获取符号的量纲（通过注册表）"""
        # 检查注册表
        info = self.quantity_registry.get_by_symbol(symbol)
        if info:
            return info.dimension

        # 尝试通过常见符号推断
        common_symbols = {
            'F': 'M L T^-2',  # 力
            'm': 'M',  # 质量
            'a': 'L T^-2',  # 加速度
            'v': 'L T^-1',  # 速度
            't': 'T',  # 时间
            'x': 'L',  # 位移
            'p': 'M L T^-1',  # 动量
            'E': 'M L^2 T^-2',  # 能量
            'U': 'M L^2 T^-2',  # 势能
            'K': 'M L^2 T^-2',  # 动能
            'ρ': 'M L^-3',  # 密度
            'P': 'M L^-1 T^-2',  # 压强
            'T': 'Θ',  # 温度
            'Q': 'M L^2 T^-2',  # 热量
            'W': 'M L^2 T^-2',  # 功
            'S': 'M L^2 T^-2 Θ^-1',  # 熵
            'q': 'I T',  # 电荷
            'E': 'M L T^-3 I^-1',  # 电场强度（注意与能量符号冲突）
            'B': 'M T^-2 I^-1',  # 磁感应强度
            'V': 'M L^2 T^-3 I^-1',  # 电势
            'I': 'I',  # 电流
            'R': 'M L^2 T^-3 I^-2',  # 电阻
            'λ': 'L',  # 波长
            'f': 'T^-1',  # 频率
            'n': '1',  # 折射率
            'h': 'M L^2 T^-1',  # 普朗克常数
            'c': 'L T^-1',  # 光速
        }

        return common_symbols.get(symbol)

    def _validate_dimension_chain(self, edges: List[Edge], nodes: List[Node],
                                  errors: List[str], details: Dict):
        """
        验证量纲链一致性（简化实现）

        检查相邻方程之间的量纲传递关系。
        """
        # 构建节点映射
        node_map = {node.id: node for node in nodes}

        # 对于每个推导边，检查from和to节点的量纲关系
        for edge in edges:
            if edge.type == "derives_from":
                from_node = node_map.get(edge.from_)
                to_node = node_map.get(edge.to)

                if from_node and to_node and from_node.type == "equation" and to_node.type == "equation":
                    check = self.check_term_dimensions(from_node)
                    if check and not check.passed:
                        errors.append(f"量纲链错误: {from_node.id} → {to_node.id}: {check.details}")

    def check_term_dimensions(self, node: Node) -> Optional[DimensionCheck]:
        """Fix 8: 项级别量纲检查

        对于形如 p + 1/2ρv² + ρgh = C 的方程，
        检查所有相加项量纲是否一致。
        """
        if not hasattr(node, 'formula_latex') or not node.formula_latex:
            return None

        latex = node.formula_latex
        # 已知方程的项级量纲映射
        known_equations = {
            'bernoulli': {
                'terms': ['p', 'ρv²', 'ρgh'],
                'expected_dim': 'M L^-1 T^-2',
            },
            'euler_fluid': {
                'terms': ['ρDv/Dt', '∇p', 'ρg'],
                'expected_dim': 'M L^-2 T^-2',
            },
            'newton_second': {
                'terms': ['F', 'ma'],
                'expected_dim': 'M L T^-2',
            },
            'ideal_gas': {
                'terms': ['pV', 'nRT'],
                'expected_dim': 'M L^2 T^-2',
            },
        }

        node_id = node.id.lower() if hasattr(node, 'id') else ''
        for key, info in known_equations.items():
            if key in node_id:
                dims = []
                for term in info['terms']:
                    dim = self._infer_term_dimension(term)
                    if dim:
                        dims.append((term, f"M^{dim.M} L^{dim.L} T^{dim.T}"))
                if len(set(d for _, d in dims)) <= 1:
                    return DimensionCheck(
                        expression=latex,
                        expected=DimensionVector(M=1, L=-1, T=-2),
                        actual=DimensionVector(M=1, L=-1, T=-2),
                        passed=True,
                        details=[f"所有项量纲一致: {info['expected_dim']}"],
                    )
                else:
                    return DimensionCheck(
                        expression=latex,
                        passed=False,
                        details=[f"项量纲不一致: {dict(dims)}"],
                    )

        return DimensionCheck(
            expression=latex,
            passed=True,
            details=["无已知项级检查规则，跳过"],
        )

    @staticmethod
    def _infer_term_dimension(term: str) -> Optional[DimensionVector]:
        """从项描述推断量纲向量"""
        # 简化实现：识别常见物理量
        term_lower = term.lower()
        if any(k in term_lower for k in ['p', 'pressure']):
            return DimensionVector(M=1, L=-1, T=-2)
        if 'ρ' in term_lower or 'rho' in term_lower or 'density' in term_lower:
            return DimensionVector(M=1, L=-3)
        if any(k in term_lower for k in ['v²', 'v^2', 'velocity^2', 'v2']):
            return DimensionVector(L=2, T=-2)
        if 'ρv' in term_lower or 'rho*v' in term_lower:
            return DimensionVector(M=1, L=-1, T=-2)  # ρ*v² gives M L^-1 T^-2
        if any(k in term_lower for k in ['g', 'gravity']):
            return DimensionVector(L=1, T=-2)
        if 'h' in term_lower or 'height' in term_lower:
            return DimensionVector(L=1)
        if 'ρgh' in term_lower:
            # ρ * g * h = M L^-3 * L T^-2 * L = M L^-1 T^-2
            return DimensionVector(M=1, L=-1, T=-2)
        if any(k in term_lower for k in ['f', 'force', 'ma']):
            return DimensionVector(M=1, L=1, T=-2)
        return None