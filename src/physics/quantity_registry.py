"""
物理量注册表

维护物理量的标准符号、量纲和单位。
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass


@dataclass
class QuantityInfo:
    """物理量信息"""
    id: str  # 物理量ID，如 "quantity.force"
    symbol: str  # 标准符号，如 "F", "v", "p"
    dimension: str  # 量纲字符串，如 "M L T^-2"
    unit: str  # 标准单位，如 "N", "m/s", "Pa"
    domain: str  # 学科域
    description: str = ""  # 描述
    aliases: List[str] = None  # 别名

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


class QuantityRegistry:
    """物理量注册表"""

    def __init__(self):
        self._registry: Dict[str, QuantityInfo] = {}
        self._symbol_to_id: Dict[str, str] = {}  # 符号到ID的映射
        self._load_default_quantities()

    def _load_default_quantities(self):
        """加载默认物理量"""
        default_quantities = [
            # 力学
            QuantityInfo(
                id="quantity.force",
                symbol="F",
                dimension="M L T^-2",
                unit="N",
                domain="mechanics",
                description="力",
                aliases=["force"]
            ),
            QuantityInfo(
                id="quantity.mass",
                symbol="m",
                dimension="M",
                unit="kg",
                domain="mechanics",
                description="质量",
                aliases=["mass"]
            ),
            QuantityInfo(
                id="quantity.acceleration",
                symbol="a",
                dimension="L T^-2",
                unit="m/s²",
                domain="mechanics",
                description="加速度",
                aliases=["acceleration"]
            ),
            QuantityInfo(
                id="quantity.velocity",
                symbol="v",
                dimension="L T^-1",
                unit="m/s",
                domain="mechanics",
                description="速度",
                aliases=["velocity", "speed"]
            ),
            QuantityInfo(
                id="quantity.momentum",
                symbol="p",
                dimension="M L T^-1",
                unit="kg·m/s",
                domain="mechanics",
                description="动量",
                aliases=["momentum"]
            ),
            QuantityInfo(
                id="quantity.kinetic_energy",
                symbol="K",
                dimension="M L^2 T^-2",
                unit="J",
                domain="mechanics",
                description="动能",
                aliases=["kinetic energy"]
            ),
            QuantityInfo(
                id="quantity.potential_energy",
                symbol="U",
                dimension="M L^2 T^-2",
                unit="J",
                domain="mechanics",
                description="势能",
                aliases=["potential energy"]
            ),
            QuantityInfo(
                id="quantity.pressure",
                symbol="p",
                dimension="M L^-1 T^-2",
                unit="Pa",
                domain="mechanics",
                description="压强",
                aliases=["pressure"]
            ),
            QuantityInfo(
                id="quantity.density",
                symbol="ρ",
                dimension="M L^-3",
                unit="kg/m³",
                domain="mechanics",
                description="密度",
                aliases=["density"]
            ),

            # 热学
            QuantityInfo(
                id="quantity.temperature",
                symbol="T",
                dimension="Θ",
                unit="K",
                domain="thermodynamics",
                description="温度",
                aliases=["temperature"]
            ),
            QuantityInfo(
                id="quantity.heat",
                symbol="Q",
                dimension="M L^2 T^-2",
                unit="J",
                domain="thermodynamics",
                description="热量",
                aliases=["heat"]
            ),
            QuantityInfo(
                id="quantity.work",
                symbol="W",
                dimension="M L^2 T^-2",
                unit="J",
                domain="thermodynamics",
                description="功",
                aliases=["work"]
            ),
            QuantityInfo(
                id="quantity.internal_energy",
                symbol="U",
                dimension="M L^2 T^-2",
                unit="J",
                domain="thermodynamics",
                description="内能",
                aliases=["internal energy"]
            ),
            QuantityInfo(
                id="quantity.entropy",
                symbol="S",
                dimension="M L^2 T^-2 Θ^-1",
                unit="J/K",
                domain="thermodynamics",
                description="熵",
                aliases=["entropy"]
            ),

            # 电磁学
            QuantityInfo(
                id="quantity.electric_charge",
                symbol="q",
                dimension="I T",
                unit="C",
                domain="electromagnetism",
                description="电荷",
                aliases=["electric charge"]
            ),
            QuantityInfo(
                id="quantity.electric_field",
                symbol="E",
                dimension="M L T^-3 I^-1",
                unit="N/C or V/m",
                domain="electromagnetism",
                description="电场强度",
                aliases=["electric field"]
            ),
            QuantityInfo(
                id="quantity.magnetic_field",
                symbol="B",
                dimension="M T^-2 I^-1",
                unit="T",
                domain="electromagnetism",
                description="磁感应强度",
                aliases=["magnetic field"]
            ),
            QuantityInfo(
                id="quantity.electric_potential",
                symbol="V",
                dimension="M L^2 T^-3 I^-1",
                unit="V",
                domain="electromagnetism",
                description="电势",
                aliases=["electric potential", "voltage"]
            ),
            QuantityInfo(
                id="quantity.electric_current",
                symbol="I",
                dimension="I",
                unit="A",
                domain="electromagnetism",
                description="电流",
                aliases=["electric current"]
            ),
            QuantityInfo(
                id="quantity.resistance",
                symbol="R",
                dimension="M L^2 T^-3 I^-2",
                unit="Ω",
                domain="electromagnetism",
                description="电阻",
                aliases=["resistance"]
            ),

            # 光学
            QuantityInfo(
                id="quantity.wavelength",
                symbol="λ",
                dimension="L",
                unit="m",
                domain="optics",
                description="波长",
                aliases=["wavelength"]
            ),
            QuantityInfo(
                id="quantity.frequency",
                symbol="f",
                dimension="T^-1",
                unit="Hz",
                domain="optics",
                description="频率",
                aliases=["frequency"]
            ),
            QuantityInfo(
                id="quantity.refractive_index",
                symbol="n",
                dimension="1",
                unit="1",
                domain="optics",
                description="折射率",
                aliases=["refractive index"]
            ),
            QuantityInfo(
                id="quantity.focal_length",
                symbol="f",
                dimension="L",
                unit="m",
                domain="optics",
                description="焦距",
                aliases=["focal length"]
            ),

            # 近代物理
            QuantityInfo(
                id="quantity.planck_constant",
                symbol="h",
                dimension="M L^2 T^-1",
                unit="J·s",
                domain="modern_physics",
                description="普朗克常数",
                aliases=["Planck constant"]
            ),
            QuantityInfo(
                id="quantity.speed_of_light",
                symbol="c",
                dimension="L T^-1",
                unit="m/s",
                domain="modern_physics",
                description="光速",
                aliases=["speed of light"]
            ),
        ]

        for q in default_quantities:
            self.register(q.id, q)

    def register(self, quantity_id: str, info: QuantityInfo):
        """注册物理量"""
        # 使用info.id作为键，确保一致性
        if quantity_id != info.id:
            print(f"警告: 注册ID不匹配: quantity_id={quantity_id}, info.id={info.id}")
        self._registry[info.id] = info
        self._symbol_to_id[info.symbol] = info.id

    def get(self, quantity_id: str) -> Optional[QuantityInfo]:
        """获取物理量信息"""
        return self._registry.get(quantity_id)

    def get_by_symbol(self, symbol: str) -> Optional[QuantityInfo]:
        """通过符号获取物理量信息"""
        quantity_id = self._symbol_to_id.get(symbol)
        if quantity_id:
            return self._registry.get(quantity_id)
        return None

    def find_by_dimension(self, dimension: str) -> List[QuantityInfo]:
        """通过量纲查找物理量"""
        from .dimensions import get_dimension_system
        dim_system = get_dimension_system()

        results = []
        for info in self._registry.values():
            if dim_system.are_dimensions_compatible(info.dimension, dimension):
                results.append(info)
        return results

    def get_domain_quantities(self, domain: str) -> List[QuantityInfo]:
        """获取特定学科域的物理量"""
        return [info for info in self._registry.values() if info.domain == domain]

    def validate_quantity(self, quantity_id: str, symbol: str,
                          dimension: str) -> Tuple[bool, str]:
        """
        验证物理量信息

        Returns:
            (是否有效, 错误信息)
        """
        info = self.get(quantity_id)
        if not info:
            return False, f"未知物理量ID: {quantity_id}"

        # 检查符号
        if info.symbol != symbol:
            return False, f"符号不匹配: 期望 {info.symbol}, 得到 {symbol}"

        # 检查量纲
        from .dimensions import get_dimension_system
        dim_system = get_dimension_system()

        if not dim_system.are_dimensions_compatible(info.dimension, dimension):
            return False, f"量纲不匹配: 期望 {info.dimension}, 得到 {dimension}"

        return True, "验证通过"


# 全局注册表实例
_registry: Optional[QuantityRegistry] = None

def get_quantity_registry() -> QuantityRegistry:
    """获取全局物理量注册表实例"""
    global _registry
    if _registry is None:
        _registry = QuantityRegistry()
    return _registry

QUANTITY_REGISTRY = get_quantity_registry()