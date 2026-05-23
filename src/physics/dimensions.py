"""
量纲系统

基于SymPy的量纲验证和转换。
"""

import re
from typing import Dict, Optional, Tuple, Union
import sympy as sp


class DimensionSystem:
    """量纲系统"""

    # 基本量纲符号
    BASE_DIMENSIONS = {
        'M': '质量',
        'L': '长度',
        'T': '时间',
        'I': '电流',
        'Θ': '温度',
        'N': '物质的量',
        'J': '发光强度'
    }

    # 常用物理量的量纲
    COMMON_DIMENSIONS = {
        # 力学
        'velocity': 'L T^-1',
        'acceleration': 'L T^-2',
        'force': 'M L T^-2',
        'energy': 'M L^2 T^-2',
        'power': 'M L^2 T^-3',
        'pressure': 'M L^-1 T^-2',
        'density': 'M L^-3',

        # 电磁学
        'charge': 'I T',
        'voltage': 'M L^2 T^-3 I^-1',
        'resistance': 'M L^2 T^-3 I^-2',
        'capacitance': 'M^-1 L^-2 T^4 I^2',
        'magnetic_field': 'M T^-2 I^-1',

        # 热学
        'temperature': 'Θ',
        'entropy': 'M L^2 T^-2 Θ^-1',

        # 光学
        'intensity': 'M T^-3',
    }

    def __init__(self):
        """初始化量纲系统"""
        self._sympy_dimensions = {}
        self._setup_sympy_dimensions()

    def _setup_sympy_dimensions(self):
        """设置SymPy量纲对象"""
        # 创建基本量纲
        self.M = sp.Symbol('M', positive=True)  # 质量
        self.L = sp.Symbol('L', positive=True)  # 长度
        self.T = sp.Symbol('T', positive=True)  # 时间
        self.I = sp.Symbol('I', positive=True)  # 电流
        self.Θ = sp.Symbol('Θ', positive=True)  # 温度
        self.N = sp.Symbol('N', positive=True)  # 物质的量
        self.J = sp.Symbol('J', positive=True)  # 发光强度

        # 常用物理量量纲表达式
        self._sympy_dimensions = {
            'M': self.M,
            'L': self.L,
            'T': self.T,
            'I': self.I,
            'Θ': self.Θ,
            'N': self.N,
            'J': self.J,
        }

    def parse_dimension_string(self, dim_str: str) -> Optional[sp.Expr]:
        """
        解析量纲字符串

        Args:
            dim_str: 量纲字符串，如 "M L^2 T^-2"

        Returns:
            SymPy表达式或None（解析失败）
        """
        if not dim_str or dim_str.strip() == '1':
            return 1  # 无量纲

        try:
            expr = 1
            # 正则匹配模式：字母可选后跟指数
            pattern = r'([A-ZΘ])\^?([+-]?\d*)'
            matches = re.findall(pattern, dim_str)

            if not matches:
                return None

            for base, exp_str in matches:
                if base not in self._sympy_dimensions:
                    return None

                base_sym = self._sympy_dimensions[base]
                if exp_str == '' or exp_str == '+1':
                    exp = 1
                elif exp_str == '-1':
                    exp = -1
                else:
                    exp = int(exp_str)

                expr *= base_sym ** exp

            return expr
        except Exception:
            return None

    def are_dimensions_compatible(self, dim1: str, dim2: str) -> bool:
        """
        检查两个量纲是否兼容（相同）

        Args:
            dim1: 第一个量纲字符串
            dim2: 第二个量纲字符串

        Returns:
            是否兼容
        """
        expr1 = self.parse_dimension_string(dim1)
        expr2 = self.parse_dimension_string(dim2)

        if expr1 is None or expr2 is None:
            return False

        # 简化并比较
        simplified = sp.simplify(expr1 / expr2)
        return simplified == 1

    def get_dimension_from_latex(self, latex_str: str,
                                 quantity_registry: Dict) -> Optional[str]:
        """
        从LaTeX公式推断量纲（简单实现）

        Args:
            latex_str: LaTeX公式字符串
            quantity_registry: 物理量注册表

        Returns:
            推断的量纲字符串或None
        """
        # 简化实现：查找已知物理量的组合
        # 实际实现需要更复杂的解析

        # 示例：如果公式是 "F = ma"，且知道 F 和 a 的量纲，可以验证
        # 这里只返回None，实际实现需要符号计算
        return None

    def validate_equation_dimensions(self, lhs_dim: str, rhs_dim: str) -> Tuple[bool, str]:
        """
        验证方程量纲一致性

        Args:
            lhs_dim: 左边量纲
            rhs_dim: 右边量纲

        Returns:
            (是否一致, 错误信息)
        """
        if not lhs_dim or not rhs_dim:
            return True, "缺少量纲信息，跳过验证"

        compatible = self.are_dimensions_compatible(lhs_dim, rhs_dim)

        if compatible:
            return True, "量纲一致"
        else:
            return False, f"量纲不一致: {lhs_dim} ≠ {rhs_dim}"

    def get_common_dimension(self, dim_str: str) -> Optional[Dict]:
        """
        获取常见物理量的量纲信息

        Args:
            dim_str: 量纲字符串

        Returns:
            包含信息的字典或None
        """
        for name, common_dim in self.COMMON_DIMENSIONS.items():
            if self.are_dimensions_compatible(dim_str, common_dim):
                return {
                    'name': name,
                    'common_dimension': common_dim,
                    'description': self._get_dimension_description(common_dim)
                }
        return None

    def _get_dimension_description(self, dim_str: str) -> str:
        """获取量纲描述"""
        descriptions = {
            'M L^2 T^-2': '能量量纲',
            'M L T^-2': '力量纲',
            'L T^-1': '速度量纲',
            'L T^-2': '加速度量纲',
            'M L^-1 T^-2': '压力量纲',
            'I T': '电荷量纲',
            'M L^2 T^-3 I^-1': '电压量纲',
            'Θ': '温度量纲',
        }
        return descriptions.get(dim_str, '未知量纲')


# 全局实例
_dim_system: Optional[DimensionSystem] = None

def get_dimension_system() -> DimensionSystem:
    """获取全局量纲系统实例"""
    global _dim_system
    if _dim_system is None:
        _dim_system = DimensionSystem()
    return _dim_system