"""
第三层：assumption测试

检查：
- derives_from边assumptions不为空
- assumption命中checklist
- approximate推导有近似标签

通过标准：所有种子边通过
"""

import pytest
import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.validators.assumption_validator import AssumptionValidator
from src.loader import DataLoader
from src.models import Edge


class TestAssumptionValidation:
    """assumption测试"""

    def setup_class(self):
        self.validator = AssumptionValidator()
        self.loader = DataLoader()

    def test_derives_from_edges_have_assumptions(self):
        """测试derives_from边包含assumptions"""
        seed_files = [
            "data/seeds/math_tools.yaml",
            "data/seeds/mechanics.yaml",
            "data/seeds/thermodynamics.yaml",
            "data/seeds/electromagnetism.yaml",
            "data/seeds/optics.yaml",
            "data/seeds/modern_physics.yaml"
        ]

        errors = []

        for seed_file in seed_files:
            file_path = Path(__file__).parent.parent / seed_file
            if not file_path.exists():
                continue

            seed_data = self.loader.load_yaml(file_path)
            if not seed_data:
                continue

            edges = seed_data.get('edges', [])
            for edge in edges:
                if edge.get('type') == 'derives_from':
                    assumptions = edge.get('assumptions', [])
                    if not assumptions:
                        errors.append(f"{seed_file}: {edge.get('id', 'unknown')} 缺少assumptions")

        if errors:
            print(f"发现 {len(errors)} 个assumptions缺失错误:")
            for error in errors[:5]:
                print(f"  {error}")
        assert len(errors) == 0, f"发现 {len(errors)} 个derives_from边缺少assumptions"

    def test_assumption_validator_methods_exist(self):
        """测试AssumptionValidator方法存在"""
        validator = AssumptionValidator()
        required_methods = ['validate_edge_assumptions', 'validate_topic_assumptions', 'validate_graph_assumptions']

        for method in required_methods:
            assert hasattr(validator, method), f"AssumptionValidator缺少方法 {method}"

        print("✓ AssumptionValidator方法检查通过")

    def test_example_edge_with_assumptions(self):
        """测试示例边包含assumptions"""
        # 使用字典创建Edge对象，因为Edge模型的from字段有别名
        edge_dict = {
            "id": "edge.bernoulli.derives_from.euler_streamline",
            "type": "derives_from",
            "from": "eq.bernoulli",
            "to": "eq.euler_streamline",
            "path_id": "path.bernoulli.canonical",
            "assumptions": ["steady_flow", "incompressible", "inviscid", "along_streamline"],
            "derivation_steps": ["步骤1", "步骤2"],
            "math_used": ["line_integral"],
            "confidence": 0.9
        }
        example_edge = Edge(**edge_dict)

        # 验证边assumptions
        passed, errors = self.validator.validate_edge_assumptions(example_edge)
        assert passed, f"示例边assumptions验证失败: {errors}"

    def test_approximation_edges_have_approximation_tags(self):
        """测试approximation_of边包含approximation_tags"""
        seed_files = [
            "data/seeds/math_tools.yaml",
            "data/seeds/mechanics.yaml",
            "data/seeds/thermodynamics.yaml",
            "data/seeds/electromagnetism.yaml",
            "data/seeds/optics.yaml",
            "data/seeds/modern_physics.yaml"
        ]

        errors = []

        for seed_file in seed_files:
            file_path = Path(__file__).parent.parent / seed_file
            if not file_path.exists():
                continue

            seed_data = self.loader.load_yaml(file_path)
            if not seed_data:
                continue

            edges = seed_data.get('edges', [])
            for edge in edges:
                if edge.get('type') == 'approximation_of':
                    approximation_tags = edge.get('approximation_tags', [])
                    if not approximation_tags:
                        errors.append(f"{seed_file}: {edge.get('id', 'unknown')} 缺少approximation_tags")

        if errors:
            print(f"发现 {len(errors)} 个approximation_tags缺失错误:")
            for error in errors[:5]:
                print(f"  {error}")
        assert len(errors) == 0, f"发现 {len(errors)} 个approximation_of边缺少approximation_tags"


if __name__ == "__main__":
    test = TestAssumptionValidation()
    test.setup_class()

    print("运行assumption测试...")

    try:
        test.test_derives_from_edges_have_assumptions()
        print("✓ derives_from边assumptions测试通过")
    except AssertionError as e:
        print(f"✗ derives_from边assumptions测试失败: {e}")

    print("assumption测试完成")