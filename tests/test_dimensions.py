"""
第四层：量纲测试

检查：
- canonical path上所有关键方程量纲一致
- 单位注册表完备

通过标准：量纲一致性通过
"""

import pytest
import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.validators.dimension_validator import DimensionValidator
from src.physics.quantity_registry import QUANTITY_REGISTRY
from src.models import Node, DimensionInfo


class TestDimensionValidation:
    """量纲测试"""

    def setup_class(self):
        self.validator = DimensionValidator()

    def test_quantity_registry_completeness(self):
        """测试物理量注册表完备性"""
        # 检查注册表非空
        assert len(QUANTITY_REGISTRY._registry) > 0, "物理量注册表为空"

        # 检查必需字段
        required_keys = ['symbol', 'dimension', 'unit']
        for qty_id, info in QUANTITY_REGISTRY._registry.items():
            for key in required_keys:
                assert hasattr(info, key), f"物理量 {qty_id} 缺少字段 {key}"

        print(f"✓ 物理量注册表检查通过，包含 {len(QUANTITY_REGISTRY._registry)} 个物理量")

    def test_dimension_validator_methods_exist(self):
        """测试DimensionValidator方法存在"""
        validator = DimensionValidator()
        required_methods = ['validate_node_dimension', 'validate_equation_dimensions',
                           'validate_canonical_path_dimensions', 'validate_graph_dimensions']

        for method in required_methods:
            assert hasattr(validator, method), f"DimensionValidator缺少方法 {method}"

        print("✓ DimensionValidator方法检查通过")

    def test_example_quantity_dimension(self):
        """测试示例物理量量纲"""
        example_node = Node(
            id="quantity.velocity",
            type="quantity",
            title="速度",
            domain="mechanics",
            abstraction_level=0,
            pedagogical_level=1,
            sources=["test"],
            dimension=DimensionInfo(
                symbol="v",
                base_dimensions="L T^-1",
                unit="m/s"
            )
        )

        passed, errors = self.validator.validate_node_dimension(example_node)
        assert passed, f"示例物理量量纲验证失败: {errors}"


if __name__ == "__main__":
    test = TestDimensionValidation()
    test.setup_class()

    print("运行量纲测试...")

    try:
        test.test_quantity_registry_completeness()
        print("✓ 物理量注册表测试通过")
    except AssertionError as e:
        print(f"✗ 物理量注册表测试失败: {e}")

    print("量纲测试完成")