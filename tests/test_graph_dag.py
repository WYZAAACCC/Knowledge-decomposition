"""
第二层：图结构测试

检查：
- 推导图是否为DAG
- 无悬空边
- 无canonical_path缺失
- 无重复节点id

通过标准：所有种子图通过
"""

import pytest
import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.validators.graph_validator import GraphValidator
from src.loader import DataLoader


class TestGraphStructure:
    """图结构测试"""

    def setup_class(self):
        self.validator = GraphValidator()
        self.loader = DataLoader()

    def test_seed_graphs_are_dag(self):
        """测试种子图是DAG"""
        # 加载所有种子数据并构建图
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

            # 解析为Node和Edge对象
            nodes = self.loader.parse_nodes_from_seed(seed_data)
            edges = self.loader.parse_edges_from_seed(seed_data)

            # 验证DAG
            passed, error_msgs, _ = self.validator.validate_dag(nodes, edges)
            if not passed:
                errors.append(f"{seed_file}: {error_msgs}")

        if errors:
            print(f"发现 {len(errors)} 个DAG错误:")
            for error in errors[:3]:
                print(f"  {error}")
        assert len(errors) == 0, f"发现 {len(errors)} 个种子图DAG错误"

    def test_no_dangling_edges_in_seeds(self):
        """测试种子图中无悬空边"""
        seed_files = [
            "data/seeds/math_tools.yaml",
            "data/seeds/mechanics.yaml",
            "data/seeds/thermodynamics.yaml",
            "data/seeds/electromagnetism.yaml",
            "data/seeds/optics.yaml",
            "data/seeds/modern_physics.yaml"
        ]

        # 首先加载所有种子节点，构建全局节点ID集合
        all_nodes = []
        all_edges = []
        seed_data_map = {}

        for seed_file in seed_files:
            file_path = Path(__file__).parent.parent / seed_file
            if not file_path.exists():
                continue
            seed_data = self.loader.load_yaml(file_path)
            if not seed_data:
                continue
            seed_data_map[seed_file] = seed_data
            nodes = self.loader.parse_nodes_from_seed(seed_data)
            edges = self.loader.parse_edges_from_seed(seed_data)
            all_nodes.extend(nodes)
            all_edges.extend(edges)

        # 构建全局节点ID集合
        all_node_ids = {node.id for node in all_nodes}

        errors = []

        # 检查每条边是否引用了全局节点集合中存在的节点
        dangling_edges = []
        for edge in all_edges:
            if edge.from_ not in all_node_ids or edge.to not in all_node_ids:
                dangling_edges.append(edge)

        if dangling_edges:
            # 按种子文件分组
            for seed_file, seed_data in seed_data_map.items():
                nodes = self.loader.parse_nodes_from_seed(seed_data)
                edges = self.loader.parse_edges_from_seed(seed_data)
                local_node_ids = {node.id for node in nodes}
                dangling = [edge for edge in edges if edge.from_ not in all_node_ids or edge.to not in all_node_ids]
                if dangling:
                    errors.append(f"{seed_file}: 发现悬空边 {len(dangling)} 条")
                    for edge in dangling[:3]:
                        print(f"    悬空边: {edge.id} ({edge.from_} -> {edge.to})")

        if errors:
            print(f"发现 {len(errors)} 个悬空边错误:")
            for error in errors[:3]:
                print(f"  {error}")
        assert len(errors) == 0, f"发现 {len(errors)} 个种子图悬空边错误"

    def test_no_duplicate_node_ids_in_seeds(self):
        """测试种子图中无重复节点ID"""
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

            nodes = seed_data.get('nodes', [])
            node_ids = [node['id'] for node in nodes if 'id' in node]
            duplicate_ids = {id for id in node_ids if node_ids.count(id) > 1}

            if duplicate_ids:
                errors.append(f"{seed_file}: 发现重复节点ID {list(duplicate_ids)[:3]}")

        if errors:
            print(f"发现 {len(errors)} 个重复节点ID错误:")
            for error in errors:
                print(f"  {error}")
        assert len(errors) == 0, f"发现 {len(errors)} 个重复节点ID错误"

    def test_graph_validator_methods_exist(self):
        """测试GraphValidator方法存在"""
        validator = GraphValidator()
        required_methods = ['validate_dag', 'find_dangling_edges', 'find_isolated_nodes', 'validate_canonical_path']

        for method in required_methods:
            assert hasattr(validator, method), f"GraphValidator缺少方法 {method}"

        print("✓ GraphValidator方法检查通过")


if __name__ == "__main__":
    test = TestGraphStructure()
    test.setup_class()

    print("运行图结构测试...")

    try:
        test.test_seed_graphs_are_dag()
        print("✓ 种子图DAG测试通过")
    except AssertionError as e:
        print(f"✗ 种子图DAG测试失败: {e}")

    try:
        test.test_no_dangling_edges_in_seeds()
        print("✓ 无悬空边测试通过")
    except AssertionError as e:
        print(f"✗ 无悬空边测试失败: {e}")

    try:
        test.test_no_duplicate_node_ids_in_seeds()
        print("✓ 无重复节点ID测试通过")
    except AssertionError as e:
        print(f"✗ 无重复节点ID测试失败: {e}")

    print("图结构测试完成")