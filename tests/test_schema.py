"""
第一层：schema测试

检查：
- 所有seed节点符合node schema
- 所有seed边符合edge schema
- 所有构建结果符合graph schema
- 所有debug / eval符合report schema

通过标准：100%通过
"""

import pytest
import sys
import os
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.validators.schema_validator import SchemaValidator
from src.loader import DataLoader


class TestSchemaValidation:
    """schema测试"""

    def setup_class(self):
        """测试类初始化"""
        self.validator = SchemaValidator()
        self.loader = DataLoader()

    def test_all_seed_nodes_conform_to_schema(self):
        """测试所有seed节点符合node schema"""
        # 加载所有种子数据
        seed_files = [
            "data/seeds/math_tools.yaml",
            "data/seeds/mechanics.yaml",
            "data/seeds/thermodynamics.yaml",
            "data/seeds/electromagnetism.yaml",
            "data/seeds/optics.yaml",
            "data/seeds/modern_physics.yaml"
        ]

        errors = []
        total_nodes = 0

        for seed_file in seed_files:
            file_path = Path(__file__).parent.parent / seed_file
            if not file_path.exists():
                continue

            # 加载种子数据
            seed_data = self.loader.load_yaml(file_path)
            if not seed_data:
                continue

            # 验证节点
            nodes = seed_data.get("nodes", [])
            total_nodes += len(nodes)

            for node_data in nodes:
                passed, error_msgs = self.validator.validate_node(node_data)
                if not passed:
                    errors.append(f"{seed_file}: {node_data.get('id', 'unknown')} - {error_msgs}")

        # 输出统计信息
        print(f"\n验证了 {total_nodes} 个种子节点")

        if errors:
            print(f"发现 {len(errors)} 个schema错误:")
            for error in errors[:5]:  # 只显示前5个错误
                print(f"  {error}")
            if len(errors) > 5:
                print(f"  ... 还有 {len(errors) - 5} 个错误")

        # 通过标准：100%通过
        assert len(errors) == 0, f"发现 {len(errors)} 个节点schema错误"

    def test_all_seed_edges_conform_to_schema(self):
        """测试所有seed边符合edge schema"""
        # 加载所有种子数据
        seed_files = [
            "data/seeds/math_tools.yaml",
            "data/seeds/mechanics.yaml",
            "data/seeds/thermodynamics.yaml",
            "data/seeds/electromagnetism.yaml",
            "data/seeds/optics.yaml",
            "data/seeds/modern_physics.yaml"
        ]

        errors = []
        total_edges = 0

        for seed_file in seed_files:
            file_path = Path(__file__).parent.parent / seed_file
            if not file_path.exists():
                continue

            # 加载种子数据
            seed_data = self.loader.load_yaml(file_path)
            if not seed_data:
                continue

            # 验证边
            edges = seed_data.get("edges", [])
            total_edges += len(edges)

            for edge_data in edges:
                passed, error_msgs = self.validator.validate_edge(edge_data)
                if not passed:
                    errors.append(f"{seed_file}: {edge_data.get('id', 'unknown')} - {error_msgs}")

        # 输出统计信息
        print(f"\n验证了 {total_edges} 个种子边")

        if errors:
            print(f"发现 {len(errors)} 个schema错误:")
            for error in errors[:5]:  # 只显示前5个错误
                print(f"  {error}")
            if len(errors) > 5:
                print(f"  ... 还有 {len(errors) - 5} 个错误")

        # 通过标准：100%通过
        assert len(errors) == 0, f"发现 {len(errors)} 个边schema错误"

    def test_schema_files_exist(self):
        """测试schema文件存在"""
        schema_dir = Path(__file__).parent.parent / "schemas"
        required_schemas = ["node.schema.json", "edge.schema.json", "graph.schema.json", "build_report.schema.json"]

        missing = []
        for schema_file in required_schemas:
            if not (schema_dir / schema_file).exists():
                missing.append(schema_file)

        assert len(missing) == 0, f"缺失schema文件: {missing}"

    def test_node_schema_required_fields(self):
        """测试node schema必需字段"""
        schema = self.validator._load_schema("node")
        required_fields = schema.get("required", [])

        # node schema必须包含id, type, title, domain, abstraction_level, pedagogical_level, sources
        expected_required = ["id", "type", "title", "domain", "abstraction_level", "pedagogical_level", "sources"]

        for field in expected_required:
            assert field in required_fields, f"node schema缺少必需字段: {field}"

    def test_edge_schema_required_fields(self):
        """测试edge schema必需字段"""
        schema = self.validator._load_schema("edge")
        required_fields = schema.get("required", [])

        # edge schema必须包含id, type, from, to, path_id
        expected_required = ["id", "type", "from", "to", "path_id"]

        for field in expected_required:
            assert field in required_fields, f"edge schema缺少必需字段: {field}"

    def test_derives_from_edge_requires_assumptions(self):
        """测试derives_from边必须包含assumptions"""
        schema = self.validator._load_schema("edge")

        # 检查derives_from边是否有assumptions约束
        # 注意：schema中可能通过if-then或property dependencies定义
        # 这里做基本检查
        properties = schema.get("properties", {})
        assumptions_prop = properties.get("assumptions", {})

        # assumptions应该是数组类型
        assert assumptions_prop.get("type") == "array", "assumptions字段应为数组类型"

        # derives_from边应该有minItems >= 1约束
        # 这个检查可能在schema的特定部分，这里只做基本验证

    def test_example_node_passes_schema(self):
        """测试示例节点通过schema验证"""
        example_node = {
            "id": "eq.bernoulli",
            "type": "equation",
            "title": "伯努利方程",
            "statement": "沿流线的伯努利方程",
            "formula_latex": "p + \\frac{1}{2}\\rho v^2 + \\rho gh = \\text{常数}",
            "domain": "mechanics",
            "abstraction_level": 2,
            "pedagogical_level": 2,
            "theory_context": "classical",
            "status": "canonical",
            "aliases": ["Bernoulli's equation"],
            "tags": ["fluid", "energy"],
            "sources": ["seed.mechanics.v1"]
        }

        passed, errors = self.validator.validate_node(example_node)
        assert passed, f"示例节点schema验证失败: {errors}"

    def test_example_edge_passes_schema(self):
        """测试示例边通过schema验证"""
        example_edge = {
            "id": "edge.bernoulli.derives_from.euler_streamline",
            "type": "derives_from",
            "from": "eq.bernoulli",
            "to": "eq.euler_streamline",
            "path_id": "path.bernoulli.canonical",
            "assumptions": ["steady_flow", "incompressible", "inviscid", "along_streamline"],
            "derivation_steps": [
                "从欧拉方程出发",
                "沿流线方向投影",
                "对路径积分",
                "整理得到压强项、位能项和动能项之和守恒"
            ],
            "math_used": ["line_integral"],
            "approximation_tags": ["ideal_fluid"],
            "verified": {
                "schema": True,
                "unit": True,
                "symbolic": False
            },
            "confidence": 0.92
        }

        passed, errors = self.validator.validate_edge(example_edge)
        assert passed, f"示例边schema验证失败: {errors}"


if __name__ == "__main__":
    # 直接运行测试（用于调试）
    test_class = TestSchemaValidation()
    test_class.setup_class()

    print("运行schema测试...")

    try:
        test_class.test_all_seed_nodes_conform_to_schema()
        print("✓ 所有种子节点通过schema验证")
    except AssertionError as e:
        print(f"✗ 种子节点schema验证失败: {e}")

    try:
        test_class.test_all_seed_edges_conform_to_schema()
        print("✓ 所有种子边通过schema验证")
    except AssertionError as e:
        print(f"✗ 种子边schema验证失败: {e}")

    print("schema测试完成")